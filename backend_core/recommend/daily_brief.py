"""每日推荐简报生成器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_core.analysis.trade_advice import build_trade_advice
from backend_core.recommend.candidates import (
    collect_strategy_buy_candidates,
    merge_candidates_by_code,
)
from backend_core.recommend.config import (
    DAILY_TOP_EXECUTABLE,
    DAILY_TOP_WATCH,
    brief_config_snapshot,
)
from backend_core.recommend.env import (
    evaluate_market_stance,
    load_board_env_bundle,
    load_quotes_snapshot,
    load_stock_names,
    map_stocks_to_ths_industry,
    resolve_asof_date,
)
from backend_core.recommend.scoring import (
    action_to_stance,
    apply_anti_chase,
    apply_diversification,
    compute_recommend_score,
    pick_role_from_tags,
)
from backend_core.recommend.store import upsert_brief

logger = logging.getLogger(__name__)


def _attach_roles(
    db: Session, codes: List[str], board_map: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """批量板角色 → code -> role_tags。"""
    from backend_core.board_roles.service import enrich_screening_results_with_role_tags

    boards = sorted(
        {
            str(v.get("board_code")).strip()
            for v in board_map.values()
            if v.get("board_code")
        }
    )
    if not boards:
        return {c: [] for c in codes}
    results = [{"code": c} for c in codes]
    try:
        enrich_screening_results_with_role_tags(
            db, results, board_type="industry", board_codes=boards
        )
    except Exception as e:
        logger.warning("attach roles failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {c: [] for c in codes}
    return {str(r.get("code")): list(r.get("role_tags") or []) for r in results}


def _load_weekly_pool_codes(db: Session, asof: str) -> Optional[set]:
    """若存在有效周报，返回观察池代码集合（日报可执行优先池内）。"""
    from backend_core.recommend.store import get_brief

    weekly = get_brief(db, horizon="weekly", asof_date=None)
    if not weekly:
        return None
    # 周报 asof 不应晚于日报 asof 太多；简单：只要周报 asof <= 日报 asof
    w_asof = str(weekly.get("asof_date") or "")
    if w_asof and w_asof > asof:
        return None
    codes = set()
    for it in weekly.get("items") or []:
        c = str(it.get("code") or "").strip()
        if c:
            codes.add(c.zfill(6) if c.isdigit() and len(c) < 6 else c)
    for board in (weekly.get("summary") or {}).get("main_boards") or []:
        for role_list_key in ("leaders", "mids", "watch_codes"):
            for x in board.get(role_list_key) or []:
                if isinstance(x, dict):
                    c = str(x.get("code") or "").strip()
                else:
                    c = str(x).strip()
                if c:
                    codes.add(c.zfill(6) if c.isdigit() and len(c) < 6 else c)
    return codes or None


def _build_risk_observe(db: Session, asof: str) -> List[Dict[str, Any]]:
    """轻量结构风险观察：正式交易持仓关注（尽力而为）。"""
    out: List[Dict[str, Any]] = []
    try:
        from backend_api.models import FormalTrade

        trades = (
            db.query(FormalTrade)
            .filter(FormalTrade.status == "open")
            .order_by(FormalTrade.updated_at.desc())
            .limit(50)
            .all()
        )
        for t in trades:
            out.append(
                {
                    "code": t.code,
                    "name": t.name,
                    "source": t.source,
                    "kind": "formal_open",
                    "note": "持仓中，关注支撑与板环境",
                    "asof_date": asof,
                    "extra": {"entry_price": t.entry_price},
                }
            )
            if len(out) >= 20:
                break
    except Exception as e:
        logger.debug("risk observe formal skipped: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out[:20]


def generate_daily_brief(
    db: Session,
    *,
    asof_date: Optional[str] = None,
    late_run: bool = False,
    persist: bool = True,
) -> Dict[str, Any]:
    asof = resolve_asof_date(db, asof_date)
    market = evaluate_market_stance(db, asof)
    market_stance = market.get("stance") or "neutral"

    by_strat = collect_strategy_buy_candidates(db, asof)
    merged = merge_candidates_by_code(by_strat)
    codes = list(merged.keys())
    board_map = map_stocks_to_ths_industry(db, codes)
    name_map = load_stock_names(db, codes)
    for code, nm in name_map.items():
        bm0 = board_map.setdefault(code, {})
        if nm and not bm0.get("stock_name"):
            bm0["stock_name"] = nm
        bucket0 = merged.get(code)
        if bucket0 is not None and nm and not bucket0.get("name"):
            bucket0["name"] = nm
    board_codes = [
        str(v.get("board_code"))
        for v in board_map.values()
        if v.get("board_code")
    ]
    board_env = load_board_env_bundle(db, board_codes, asof)
    quotes = load_quotes_snapshot(db, codes, asof)
    role_map = _attach_roles(db, codes, board_map)
    weekly_pool = _load_weekly_pool_codes(db, asof)

    items: List[Dict[str, Any]] = []
    for code, bucket in merged.items():
        primary = bucket.get("primary_strategy") or "urt"
        row = dict((bucket.get("strategy_rows") or {}).get(primary) or {})
        quote = quotes.get(code) or {}
        if quote.get("close") is not None and row.get("close") is None:
            row["close"] = quote["close"]
        bm = board_map.get(code) or {}
        board_code = bm.get("board_code")
        env = board_env.get(board_code or "") or {}
        board_weak = bool(env.get("board_weak"))
        if board_weak:
            row["board_weak"] = True

        advice = build_trade_advice(primary, row)
        action = str(advice.get("action") or "watch")
        if market_stance == "bear" and action == "buy":
            action = "watch"
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；大盘偏空，降为观察"
        if board_weak and action == "buy":
            action = "watch"
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；板弱否决，降为观察"

        action, chase_reasons = apply_anti_chase(
            action=action, quote=quote, advice=advice
        )
        if chase_reasons and action == "watch":
            advice = dict(advice)
            advice["action"] = "watch"

        # 周池约束：池外强信号默认观察
        out_of_weekly_pool = False
        if weekly_pool is not None and code not in weekly_pool and action == "buy":
            action = "watch"
            out_of_weekly_pool = True
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；周观察池外，降为观察"

        # 无买区/止损不进可执行
        if action == "buy":
            if not advice.get("buy_zone") or not advice.get("stop_zone"):
                action = "watch"
                chase_reasons = list(chase_reasons) + ["missing_buy_or_stop_zone"]

        role_tags = role_map.get(code) or []
        role, role_label = pick_role_from_tags(role_tags)
        score, score_detail = compute_recommend_score(
            strategies=list(bucket.get("strategies") or []),
            best_score=bucket.get("best_score"),
            advice_action=action,
            role=role,
            board_weak=board_weak,
        )
        constraint_reasons = list(chase_reasons)
        if out_of_weekly_pool:
            constraint_reasons.append("out_of_weekly_pool")
        if market_stance == "bear":
            constraint_reasons.append("market_bear")
        if board_weak:
            constraint_reasons.append("board_weak")

        pos_hint = "标准"
        if role == "leader":
            pos_hint = "弹性偏小（防追高）"
        elif role == "mid":
            pos_hint = "稳健可执行"

        stock_name = (
            bucket.get("name")
            or row.get("name")
            or bm.get("stock_name")
            or name_map.get(code)
        )
        industry = bm.get("industry") or bm.get("board_name")
        items.append(
            {
                "code": code,
                "name": stock_name,
                "action": action,
                "stance": action_to_stance(action),
                "primary_strategy": primary,
                "strategies": list(bucket.get("strategies") or []),
                "recommend_score": round(score, 2),
                "score_detail": score_detail,
                "role": role or "normal",
                "role_label": role_label or "普通",
                "role_tags": role_tags,
                "board_code": board_code,
                "board_name": industry,
                "industry": industry,
                "board_weak": board_weak,
                "board_env": {
                    "slopes": env.get("slopes"),
                    "fund_flow": env.get("fund_flow"),
                },
                "trade_advice": advice,
                "buy_zone": advice.get("buy_zone"),
                "stop_zone": advice.get("stop_zone"),
                "take_profit": advice.get("take_profit"),
                "summary": advice.get("summary"),
                "position_hint": pos_hint,
                "quote": {
                    "close": quote.get("close"),
                    "pct_chg": quote.get("pct_chg"),
                    "is_limit_up": quote.get("is_limit_up"),
                    "n_day_gain_pct": quote.get("n_day_gain_pct"),
                },
                "constraint_reasons": constraint_reasons,
                "evidence": {
                    "strategies": list(bucket.get("strategies") or []),
                    "best_score": bucket.get("best_score"),
                    "role": role,
                    "board_code": board_code,
                    "market_stance": market_stance,
                },
            }
        )

    # buy 优先 → 分数
    items.sort(
        key=lambda x: (
            0 if x.get("action") == "buy" else 1 if x.get("action") == "watch" else 2,
            -float(x.get("recommend_score") or 0),
        )
    )
    items = apply_diversification(items)

    executable = [x for x in items if x.get("action") == "buy"][:DAILY_TOP_EXECUTABLE]
    watch = [x for x in items if x.get("action") != "buy"][:DAILY_TOP_WATCH]
    # 重新拼装：可执行 + 观察（保持分散后的 action）
    final_items = executable + watch

    from backend_core.recommend.kpi import compute_brief_concentration_kpi

    kpi = compute_brief_concentration_kpi(final_items)
    summary = {
        "market": market,
        "config": brief_config_snapshot(),
        "counts": {
            "candidates": len(merged),
            "executable": len(executable),
            "watch": len(watch),
            "by_strategy": {k: len(v) for k, v in by_strat.items()},
        },
        "weekly_pool_applied": weekly_pool is not None,
        "disclaimer": "规则合成参考，非投资建议",
    }
    risk = _build_risk_observe(db, asof)

    payload = {
        "horizon": "daily",
        "asof_date": asof,
        "plan_for": asof,
        "late_run": bool(late_run),
        "market_stance": market_stance,
        "summary": summary,
        "items": final_items,
        "risk_observe": risk,
        "kpi": kpi,
    }
    if persist:
        return upsert_brief(
            db,
            horizon="daily",
            asof_date=asof,
            items=final_items,
            summary=summary,
            risk_observe=risk,
            kpi=kpi,
            market_stance=market_stance,
            plan_for=asof,
            late_run=late_run,
        )
    return payload
