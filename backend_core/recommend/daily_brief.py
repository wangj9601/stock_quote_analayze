"""每日推荐简报生成器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend_core.analysis.trade_advice import build_trade_advice
from backend_core.recommend.candidates import (
    collect_strategy_buy_candidates,
    merge_candidates_by_code,
)
from backend_core.recommend.config import (
    DAILY_TOP_EXEC_DEFENSE,
    DAILY_TOP_EXECUTABLE,
    DAILY_TOP_WATCH,
    E_SLOPE_DEFENSE_THRESHOLD,
    LATE_FALSE_BREAK_PCT,
    LATE_UPPER_SHADOW_RATIO,
    brief_config_snapshot,
    strategy_priority_for_regime,
)
from backend_core.recommend.env import (
    combine_e_slope,
    compute_index_slope_20,
    evaluate_market_stance,
    load_board_env_bundle,
    load_quotes_snapshot,
    load_stock_names,
    map_stocks_to_ths_industry,
    resolve_asof_date,
)
from backend_core.recommend.normalize import (
    apply_normalized_best_score,
    normalize_strategy_scores,
)
from backend_core.recommend.regime import (
    classify_regime,
    pick_primary_strategy,
    regime_quality_weights,
)
from backend_core.recommend.scoring import (
    action_to_stance,
    apply_anti_chase,
    apply_diversification,
    compute_recommend_score,
    pick_role_from_tags,
)
from backend_core.recommend.sr_levels import compute_sr_for_codes, merge_advice_with_sr
from backend_core.recommend.store import upsert_brief

logger = logging.getLogger(__name__)


def _attach_roles(
    db: Session, codes: List[str], board_map: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
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
    from backend_core.recommend.store import get_brief

    weekly = get_brief(db, horizon="weekly", asof_date=None)
    if not weekly:
        return None
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


def _load_theme_align_sets(db: Session, asof: str) -> Dict[str, Set[str]]:
    """周主线板 / 月主题板代码集合，用于日报主题对齐加分。"""
    from backend_core.recommend.store import get_brief

    weekly_codes: Set[str] = set()
    monthly_codes: Set[str] = set()
    weekly_boards: Set[str] = set()
    monthly_boards: Set[str] = set()

    weekly = get_brief(db, horizon="weekly", asof_date=None)
    if weekly and str(weekly.get("asof_date") or "") <= asof:
        for it in weekly.get("items") or []:
            c = str(it.get("code") or "").strip()
            if c:
                weekly_codes.add(c.zfill(6) if c.isdigit() and len(c) < 6 else c)
        for board in (weekly.get("summary") or {}).get("main_boards") or []:
            bc = str(board.get("board_code") or "").strip()
            if bc:
                weekly_boards.add(bc)

    monthly = get_brief(db, horizon="monthly", asof_date=None)
    if monthly and str(monthly.get("asof_date") or "") <= asof:
        for it in monthly.get("items") or []:
            c = str(it.get("code") or "").strip()
            if c:
                monthly_codes.add(c.zfill(6) if c.isdigit() and len(c) < 6 else c)
        for board in (monthly.get("summary") or {}).get("theme_boards") or []:
            bc = str(board.get("board_code") or "").strip()
            if bc:
                monthly_boards.add(bc)

    return {
        "weekly_codes": weekly_codes,
        "monthly_codes": monthly_codes,
        "weekly_boards": weekly_boards,
        "monthly_boards": monthly_boards,
    }


def _build_risk_observe(db: Session, asof: str) -> List[Dict[str, Any]]:
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


def _board_slope_20(env: Dict[str, Any]) -> Optional[float]:
    slopes = env.get("slopes") or {}
    raw = slopes.get("20") or slopes.get(20) or {}
    if isinstance(raw, dict):
        s = raw.get("sector_slope")
    else:
        s = None
    try:
        return float(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def apply_late_session_filters(
    items: List[Dict[str, Any]],
    quotes_intraday: Dict[str, Dict[str, Any]],
) -> tuple:
    """尾盘确认：长上影 / 假突破 → buy 降 watch。返回 (items, degrade_count)。"""
    degraded = 0
    out = []
    for it in items:
        row = dict(it)
        reasons = list(row.get("constraint_reasons") or [])
        if row.get("action") != "buy":
            out.append(row)
            continue
        code = str(row.get("code") or "")
        q = quotes_intraday.get(code) or {}
        o = q.get("open")
        h = q.get("high")
        low = q.get("low")
        c = q.get("close")
        try:
            if None not in (o, h, low, c):
                o, h, low, c = float(o), float(h), float(low), float(c)
                rng = max(h - low, 1e-6)
                upper = h - max(o, c)
                if upper / rng >= float(LATE_UPPER_SHADOW_RATIO):
                    row["action"] = "watch"
                    row["stance"] = action_to_stance("watch")
                    reasons.append("late_upper_shadow")
                    degraded += 1
                    summary = row.get("summary") or ""
                    row["summary"] = summary + "；尾盘长上影，降为观察"
            # 假突破：收盘跌回买区上沿之下
            if row.get("action") == "buy":
                zone = row.get("buy_zone") or {}
                anchor = zone.get("high") or zone.get("price")
                if c is not None and anchor is not None:
                    a = float(anchor)
                    if float(c) < a * (1.0 - float(LATE_FALSE_BREAK_PCT)):
                        row["action"] = "watch"
                        row["stance"] = action_to_stance("watch")
                        reasons.append("late_false_break")
                        degraded += 1
                        summary = row.get("summary") or ""
                        row["summary"] = summary + "；尾盘假突破，降为观察"
        except (TypeError, ValueError):
            pass
        row["constraint_reasons"] = reasons
        out.append(row)
    return out, degraded


def _load_intraday_quotes(
    db: Session, codes: List[str], asof: str
) -> Dict[str, Dict[str, Any]]:
    """尽力取当日 OHLC：优先 historical_quotes 当日，否则快照。"""
    base = load_quotes_snapshot(db, codes, asof)
    # historical 已含 open/high/low 时补齐
    try:
        from sqlalchemy import bindparam, text

        rows = db.execute(
            text(
                """
                SELECT code, open, high, low, close
                FROM historical_quotes
                WHERE code IN :codes AND date = :asof
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": codes, "asof": asof},
        ).fetchall()
        for r in rows:
            code = str(r[0]).strip()
            bucket = base.setdefault(code, {})
            for k, v in (("open", r[1]), ("high", r[2]), ("low", r[3]), ("close", r[4])):
                if v is not None:
                    bucket[k] = float(v)
    except Exception as e:
        logger.debug("intraday quotes enrich skipped: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return base


def generate_daily_brief(
    db: Session,
    *,
    asof_date: Optional[str] = None,
    late_run: bool = False,
    persist: bool = True,
) -> Dict[str, Any]:
    asof = resolve_asof_date(db, asof_date)
    # 若当日尚无 ZHAB 信号（复盘未跑），兜底扫描近窗涨停池
    try:
        from backend_api.models import ZhabSignalTrace, ZhabStrategyConfig
        from datetime import date as _date

        td = _date.fromisoformat(asof[:10])
        cfg = (
            db.query(ZhabStrategyConfig)
            .filter(ZhabStrategyConfig.is_default.is_(True))
            .order_by(ZhabStrategyConfig.id.asc())
            .first()
        )
        q = db.query(ZhabSignalTrace).filter(ZhabSignalTrace.trade_date == td)
        if cfg is not None:
            q = q.filter(ZhabSignalTrace.config_id == int(cfg.id))
        if q.limit(1).first() is None:
            from backend_core.strategies.zhab.strategy_engine import ensure_zhab_signals

            ensure_zhab_signals(db, asof, persist=True)
    except Exception:
        logger.exception("ZHAB recommend 兜底扫描失败")
        try:
            db.rollback()
        except Exception:
            pass

    market = evaluate_market_stance(db, asof)
    market_stance = market.get("stance") or "neutral"
    index_slope = compute_index_slope_20(db, asof)
    market_e = float(index_slope.get("e_slope") or 1.0)
    market_slope_20 = index_slope.get("slope_20")

    regime_info = classify_regime(market_slope_20=market_slope_20)
    regime = regime_info.get("regime") or "range"
    priority = strategy_priority_for_regime(regime)
    weights = regime_quality_weights(regime)

    by_strat = collect_strategy_buy_candidates(db, asof)
    by_strat = normalize_strategy_scores(by_strat)
    merged = merge_candidates_by_code(by_strat, priority=priority)
    apply_normalized_best_score(merged, regime_weights=weights)

    # regime 重选主策略
    for bucket in merged.values():
        primary = pick_primary_strategy(bucket.get("strategies") or [], regime)
        if primary:
            bucket["primary_strategy"] = primary

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
    theme_sets = _load_theme_align_sets(db, asof)

    sr_map = compute_sr_for_codes(db, codes, asof, quotes=quotes)

    items: List[Dict[str, Any]] = []
    for code, bucket in merged.items():
        primary = bucket.get("primary_strategy") or pick_primary_strategy(
            bucket.get("strategies") or [], regime
        ) or "gms"
        row = dict((bucket.get("strategy_rows") or {}).get(primary) or {})
        quote = quotes.get(code) or {}
        if quote.get("close") is not None and row.get("close") is None:
            row["close"] = quote["close"]
        bm = board_map.get(code) or {}
        board_code = bm.get("board_code")
        env = board_env.get(board_code or "") or {}
        board_weak = bool(env.get("board_weak"))
        b_slope20 = _board_slope_20(env)
        e_info = combine_e_slope(market_e, b_slope20)
        e_slope = float(e_info["e_slope"])
        floor_hit = bool(e_info.get("floor_hit"))

        if board_weak:
            row["board_weak"] = True

        advice = build_trade_advice(primary, row)
        sr = sr_map.get(code) or {}
        advice = merge_advice_with_sr(advice, sr)
        action = str(advice.get("action") or "watch")

        # ZHAB 蓄势 / 环境未过门：强制观察
        if primary == "zhab" and (
            row.get("watch_only")
            or str(row.get("signal_type") or "") == "setup"
            or not row.get("entry_signal")
        ):
            action = "watch"
            advice = dict(advice)
            advice["action"] = "watch"

        if market_stance == "bear" and action == "buy":
            action = "watch"
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；大盘偏空，降为观察"
        if (board_weak or floor_hit) and action == "buy":
            action = "watch"
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；板弱/E地板，降为观察"

        action, chase_reasons = apply_anti_chase(
            action=action,
            quote=quote,
            advice=advice,
            strategies=list(bucket.get("strategies") or []),
            primary_strategy=primary,
            signal_type=row.get("signal_type"),
        )
        if chase_reasons and action == "watch":
            advice = dict(advice)
            advice["action"] = "watch"

        out_of_weekly_pool = False
        if weekly_pool is not None and code not in weekly_pool and action == "buy":
            action = "watch"
            out_of_weekly_pool = True
            advice = dict(advice)
            advice["action"] = "watch"
            advice["summary"] = (advice.get("summary") or "") + "；周观察池外，降为观察"

        # 有 VP 浮动区则不再因缺价位一律降级
        has_sr_zone = bool(sr.get("buy_zone") and sr.get("stop_zone"))
        if action == "buy" and not has_sr_zone:
            if not advice.get("buy_zone") or not advice.get("stop_zone"):
                action = "watch"
                chase_reasons = list(chase_reasons) + ["missing_buy_or_stop_zone"]

        role_tags = role_map.get(code) or []
        role, role_label = pick_role_from_tags(role_tags)

        theme_align = (
            code in theme_sets["weekly_codes"]
            or code in theme_sets["monthly_codes"]
            or (board_code and board_code in theme_sets["weekly_boards"])
            or (board_code and board_code in theme_sets["monthly_boards"])
        )

        score, score_detail = compute_recommend_score(
            strategies=list(bucket.get("strategies") or []),
            best_score=bucket.get("best_score"),
            advice_action=action,
            role=role,
            board_weak=board_weak,
            e_slope=e_slope,
            s_sr=float(sr.get("s_sr") or 0.0),
            theme_align=theme_align,
            e_slope_floor_hit=floor_hit,
        )
        if sr.get("p_sup") is not None:
            score_detail["p_sup"] = sr.get("p_sup")
        if sr.get("p_res") is not None:
            score_detail["p_res"] = sr.get("p_res")

        constraint_reasons = list(chase_reasons)
        if out_of_weekly_pool:
            constraint_reasons.append("out_of_weekly_pool")
        if market_stance == "bear":
            constraint_reasons.append("market_bear")
        if board_weak:
            constraint_reasons.append("board_weak")
        if floor_hit:
            constraint_reasons.append("e_slope_floor")

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
                "regime": regime,
                "e_slope": e_slope,
                "s_sr": sr.get("s_sr"),
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
                    "e_slope": e_info,
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
                    "regime": regime,
                    "theme_align": theme_align,
                    "e_slope": e_info,
                },
            }
        )

    items.sort(
        key=lambda x: (
            0 if x.get("action") == "buy" else 1 if x.get("action") == "watch" else 2,
            -float(x.get("recommend_score") or 0),
        )
    )
    items = apply_diversification(items)

    late_degraded = 0
    if late_run:
        intra = _load_intraday_quotes(db, [str(x.get("code")) for x in items], asof)
        items, late_degraded = apply_late_session_filters(items, intra)
        items.sort(
            key=lambda x: (
                0 if x.get("action") == "buy" else 1 if x.get("action") == "watch" else 2,
                -float(x.get("recommend_score") or 0),
            )
        )

    defense = (
        market_stance == "bear"
        or market_e < float(E_SLOPE_DEFENSE_THRESHOLD)
    )
    top_exec = int(DAILY_TOP_EXEC_DEFENSE) if defense else int(DAILY_TOP_EXECUTABLE)
    executable = [x for x in items if x.get("action") == "buy"][:top_exec]
    watch = [x for x in items if x.get("action") != "buy"][:DAILY_TOP_WATCH]
    final_items = executable + watch

    from backend_core.recommend.kpi import compute_brief_concentration_kpi

    kpi = compute_brief_concentration_kpi(final_items)
    kpi["defense_mode"] = defense
    kpi["daily_top_exec_effective"] = top_exec
    kpi["late_degraded"] = late_degraded
    kpi["regime"] = regime
    kpi["regime_counts"] = {
        "range": sum(1 for x in final_items if x.get("regime") == "range"),
        "trend": sum(1 for x in final_items if x.get("regime") == "trend"),
    }

    cfg = brief_config_snapshot()
    cfg["daily_top_exec_effective"] = top_exec
    cfg["defense_mode"] = defense

    summary = {
        "market": {**market, "slope_20": market_slope_20, "e_slope": market_e},
        "regime": regime_info,
        "config": cfg,
        "counts": {
            "candidates": len(merged),
            "executable": len(executable),
            "watch": len(watch),
            "by_strategy": {k: len(v) for k, v in by_strat.items()},
        },
        "weekly_pool_applied": weekly_pool is not None,
        "late_run": bool(late_run),
        "late_degraded": late_degraded,
        "publish_window": "尾盘确认 14:30–14:50" if late_run else "日终静态",
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
