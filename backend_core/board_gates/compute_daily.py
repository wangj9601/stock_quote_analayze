# -*- coding: utf-8 -*-
"""板块入场闸门日批：资金特征 + 板RS + 估值 + 三态落库。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import bindparam, text

from backend_core.board_gates.board_rs import compute_and_rank_board_rs
from backend_core.board_gates.boards import list_boards
from backend_core.board_gates.config import (
    DEFAULT_BOARD_CODE_SOURCE,
    GATE_ALLOC,
    GATE_AVOID,
    MIDLONG_CONFIRM_DAYS,
    SHORT_CONFIRM_DAYS,
    hard_filter_enabled,
    v2_layers_enabled,
)
from backend_core.board_gates.evaluate import evaluate_midlong_raw, evaluate_short_raw
from backend_core.board_gates.fund_features import build_fund_feature_rows
from backend_core.board_gates.sticky import apply_sticky, conflict_action
from backend_core.board_gates.storage import (
    ensure_board_gate_tables,
    load_gate_raw_history,
    resolve_asof_trade_date,
    upsert_board_gates,
    upsert_board_rs_ratings,
    upsert_board_valuation,
    upsert_fund_features,
)
from backend_core.board_gates.valuation import aggregate_board_valuation
from backend_core.board_metrics.sector_slope_store import (
    DEFAULT_SLOPE_WINDOWS,
    load_board_sector_slopes_multi,
    slope_strong_threshold_for_window,
)
from backend_core.strategies.gms.board_resonance import (
    evaluate_board_environment,
    evaluate_multi_window_board_trend,
)

logger = logging.getLogger(__name__)

_WINDOW_FIELD = {
    120: ("sector_slope_120", "board_env_120", "slope_r2_120", "slope_source_120"),
    60: ("sector_slope", "board_env", "slope_r2", "slope_source"),
    20: ("sector_slope_20", "board_env_20", "slope_r2_20", "slope_source_20"),
    10: ("sector_slope_short", "board_env_short", "slope_r2_short", "slope_source_short"),
    5: ("sector_slope_5", "board_env_5", "slope_r2_5", "slope_source_5"),
}


def _attach_envs(
    item: Dict[str, Any],
    slopes_by_window: Dict[int, Dict[str, Any]],
) -> None:
    for w, fields in _WINDOW_FIELD.items():
        slope_key, env_key, r2_key, src_key = fields
        detail = slopes_by_window.get(w) or {}
        slope_v = detail.get("sector_slope")
        r2_v = detail.get("slope_r2")
        src_v = detail.get("slope_source")
        item[slope_key] = slope_v
        item[r2_key] = r2_v
        item[src_key] = src_v
        env = evaluate_board_environment(
            sector_slope_v=slope_v,
            board_change_percent=None,
            slope_strong_threshold=slope_strong_threshold_for_window(w),
            use_realtime_fallback=False,
            slope_r2=r2_v,
            sector_slope_window=w,
        )
        item[env_key] = env.get("board_env")
        item[f"{env_key}_label"] = env.get("board_env_label")


def _load_mainline_sentiment(
    db, trade_date: str
) -> Tuple[Set[str], Dict[str, int], Set[str]]:
    """概念：当日命中集合、近10日计数、rotation dropped（近2日曾命中今日未命中）。"""
    hit_today: Set[str] = set()
    counts: Dict[str, int] = {}
    dropped: Set[str] = set()
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, trade_date
                FROM market_daily_mainline_hits
                WHERE hit = TRUE
                  AND board_type = 'concept'
                  AND trade_date <= CAST(:td AS date)
                  AND trade_date >= CAST(:td AS date) - INTERVAL '30 days'
                """
            ),
            {"td": trade_date[:10]},
        ).fetchall()
    except Exception as e:
        logger.warning("load mainline hits failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return hit_today, counts, dropped

    by_code_dates: Dict[str, List[str]] = {}
    for code, td in rows:
        c = str(code or "").strip()
        d = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
        by_code_dates.setdefault(c, []).append(d)

    asof = trade_date[:10]
    for c, dates in by_code_dates.items():
        dates = sorted(set(dates))
        if asof in dates:
            hit_today.add(c)
        # 近 10 个日历近似：取 asof 前含当日的最近记录数
        recent = [d for d in dates if d <= asof][-10:]
        counts[c] = len(recent)
        # dropped: 昨日在榜今日不在（简化：最近有命中且今日无）
        if asof not in dates and recent:
            # 若最近命中日距 asof 很近（<=3 日）视为掉出
            last = recent[-1]
            dropped.add(c)

    return hit_today, counts, dropped


def _load_industry_sentiment_top(
    db, trade_date: str, *, top_n: int = 15
) -> Set[str]:
    """行业情绪：当日资金流涨幅 TopN（观察池优先用 change_percent）。"""
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code
                FROM board_fund_flow_daily
                WHERE board_kind = 'industry'
                  AND board_code_source = :src
                  AND trade_date = CAST(:td AS date)
                  AND change_percent IS NOT NULL
                ORDER BY change_percent DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {
                "src": DEFAULT_BOARD_CODE_SOURCE,
                "td": trade_date[:10],
                "lim": int(top_n),
            },
        ).fetchall()
        return {str(r[0]).strip() for r in rows if r and r[0]}
    except Exception as e:
        logger.debug("industry sentiment top failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return set()


def _shadow_hint(short_state: str, midlong_state: Optional[str]) -> str:
    if short_state == GATE_AVOID or midlong_state == GATE_AVOID:
        return "would_block_new_buy"
    if short_state == GATE_ALLOC and midlong_state == GATE_AVOID:
        return "would_ultrashort_only"
    if midlong_state == GATE_ALLOC and short_state == GATE_AVOID:
        return "would_hold_no_new"
    if short_state == GATE_WATCH or midlong_state == GATE_WATCH:
        return "would_downweight"
    if short_state == GATE_ALLOC or midlong_state == GATE_ALLOC:
        return "would_full"
    return "neutral"


def compute_board_gates_for_date(
    db,
    trade_date: Optional[str] = None,
    *,
    v2: Optional[bool] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """主入口：计算并落库指定交易日闸门。"""
    ensure_board_gate_tables(db)
    asof = resolve_asof_trade_date(db, trade_date)
    use_v2 = v2_layers_enabled() if v2 is None else bool(v2)

    industry = list_boards(db, board_kind="industry")
    concepts = list_boards(db, board_kind="concept")
    if not industry and not concepts:
        return {"success": False, "trade_date": asof, "error": "无板块目录"}

    # --- 斜率多窗 ---
    ind_codes = [str(b["board_code"]) for b in industry]
    con_codes = [str(b["board_code"]) for b in concepts]
    slopes_ind = load_board_sector_slopes_multi(
        db, ind_codes, board_kind="industry", asof_date=asof, windows=DEFAULT_SLOPE_WINDOWS
    ) if ind_codes else {}
    slopes_con = load_board_sector_slopes_multi(
        db, con_codes, board_kind="concept", asof_date=asof, windows=DEFAULT_SLOPE_WINDOWS
    ) if con_codes else {}

    def _pack(kind: str, metas: List[Dict[str, Any]], slopes_multi: Dict) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for m in metas:
            code = str(m["board_code"])
            item = {
                "board_code": code,
                "board_name": m.get("board_name"),
                "board_kind": kind,
                "trade_observe_flag": bool(m.get("trade_observe_flag")),
            }
            by_w = {
                w: (slopes_multi.get(w) or {}).get(code) or {}
                for w in DEFAULT_SLOPE_WINDOWS
            }
            _attach_envs(item, by_w)
            trend = evaluate_multi_window_board_trend(item)
            item["board_trend_label"] = trend.get("board_trend_label")
            item["board_trend_env"] = trend.get("board_trend_env")
            out[code] = item
        return out

    ind_ctx = _pack("industry", industry, slopes_ind)
    con_ctx = _pack("concept", concepts, slopes_con)

    # --- 资金特征（需短强/中弱）---
    def _short_strong(item: Dict[str, Any]) -> bool:
        return item.get("board_env_5") == "strong" or item.get("board_env_short") == "strong"

    def _mid_weak(item: Dict[str, Any]) -> bool:
        return item.get("board_env") == "weak"

    fund_rows: List[Dict[str, Any]] = []
    for kind, codes, ctx in (
        ("industry", ind_codes, ind_ctx),
        ("concept", con_codes, con_ctx),
    ):
        if not codes:
            continue
        rows = build_fund_feature_rows(
            db,
            codes,
            board_kind=kind,
            trade_date=asof,
            short_strong_by_code={c: _short_strong(ctx[c]) for c in codes if c in ctx},
            mid_weak_by_code={c: _mid_weak(ctx[c]) for c in codes if c in ctx},
        )
        fund_rows.extend(rows)
    upsert_fund_features(db, fund_rows)
    fund_by_key = {
        (r["board_kind"], r["board_code"]): r for r in fund_rows
    }

    # --- 板 RS（行业）---
    rs_rows = compute_and_rank_board_rs(
        db, industry, trade_date=asof, board_kind="industry"
    ) if industry else []
    upsert_board_rs_ratings(db, rs_rows)
    rs_by_code = {r["board_code"]: r for r in rs_rows}

    # --- 估值（观察池行业）---
    observe_metas = [m for m in industry if m.get("trade_observe_flag")]
    val_rows = (
        aggregate_board_valuation(db, observe_metas, trade_date=asof)
        if observe_metas
        else []
    )
    upsert_board_valuation(db, val_rows)
    val_by_code = {r["board_code"]: r for r in val_rows}

    # --- 情绪 ---
    concept_hits, concept_counts, concept_dropped = _load_mainline_sentiment(db, asof)
    industry_top = _load_industry_sentiment_top(db, asof)

    gate_rows: List[Dict[str, Any]] = []
    stats = {"short_alloc": 0, "short_avoid": 0, "midlong_alloc": 0, "midlong_avoid": 0}

    def _process(kind: str, metas: List[Dict[str, Any]], ctx_map: Dict[str, Dict[str, Any]]):
        for m in metas:
            code = str(m["board_code"])
            ctx = ctx_map.get(code) or {}
            feat = fund_by_key.get((kind, code)) or {}
            observe = bool(m.get("trade_observe_flag"))

            if kind == "concept":
                sentiment = code in concept_hits or concept_counts.get(code, 0) >= 2
                dropped = code in concept_dropped
            else:
                sentiment = code in industry_top
                dropped = False

            short_raw, short_ev, short_deg = evaluate_short_raw(
                board_kind=kind,
                env5=ctx.get("board_env_5"),
                slope5=ctx.get("sector_slope_5"),
                env10=ctx.get("board_env_short"),
                slope10=ctx.get("sector_slope_short"),
                day_net=feat.get("day_net"),
                net_sum_5=feat.get("net_sum_5"),
                inflow_streak=feat.get("inflow_streak"),
                pos_days_5=feat.get("pos_days_5"),
                outflow_streak=feat.get("outflow_streak"),
                sentiment_ok=sentiment,
                rotation_dropped=dropped,
                v2=use_v2,
            )
            prior_s = load_gate_raw_history(
                db,
                board_kind=kind,
                board_code=code,
                board_code_source=DEFAULT_BOARD_CODE_SOURCE,
                before_date=asof,
                limit=SHORT_CONFIRM_DAYS,
                field="short_raw",
            )
            short_state, short_cnt = apply_sticky(
                short_raw, prior_s, confirm_days=SHORT_CONFIRM_DAYS
            )

            midlong_raw = None
            midlong_state = None
            midlong_cnt = None
            mid_ev: Dict[str, Any] = {}
            mid_deg: List[str] = []
            if kind == "industry" and observe:
                rs = rs_by_code.get(code) or {}
                val = val_by_code.get(code) or {}
                board_rs = rs.get("rs_observe")
                if board_rs is None:
                    board_rs = rs.get("rs_rating")
                midlong_raw, mid_ev, mid_deg = evaluate_midlong_raw(
                    env60=ctx.get("board_env"),
                    slope60=ctx.get("sector_slope"),
                    env120=ctx.get("board_env_120"),
                    slope120=ctx.get("sector_slope_120"),
                    slope_source_60=ctx.get("slope_source"),
                    net_sum_20=feat.get("net_sum_20"),
                    board_trend_label=ctx.get("board_trend_label"),
                    fund_stage=feat.get("fund_stage"),
                    inflow_streak=feat.get("inflow_streak"),
                    pos_days_20=feat.get("pos_days_20"),
                    board_rs=board_rs,
                    pe_pct=val.get("pe_pct"),
                    pb_pct=val.get("pb_pct"),
                    valuation_unknown=bool(val.get("valuation_unknown", True)),
                    v2=use_v2,
                )
                prior_m = load_gate_raw_history(
                    db,
                    board_kind=kind,
                    board_code=code,
                    board_code_source=DEFAULT_BOARD_CODE_SOURCE,
                    before_date=asof,
                    limit=MIDLONG_CONFIRM_DAYS,
                    field="midlong_raw",
                )
                midlong_state, midlong_cnt = apply_sticky(
                    midlong_raw, prior_m, confirm_days=MIDLONG_CONFIRM_DAYS
                )

            ca = conflict_action(midlong_state, short_state)
            evidence = {
                "short": short_ev,
                "midlong": mid_ev,
                "fund_stage": feat.get("fund_stage"),
                "board_trend_label": ctx.get("board_trend_label"),
                "board_rs": (rs_by_code.get(code) or {}).get("rs_observe")
                or (rs_by_code.get(code) or {}).get("rs_rating"),
                "valuation": {
                    "pe_pct": (val_by_code.get(code) or {}).get("pe_pct"),
                    "pb_pct": (val_by_code.get(code) or {}).get("pb_pct"),
                    "unknown": (val_by_code.get(code) or {}).get(
                        "valuation_unknown", True
                    ),
                }
                if kind == "industry"
                else None,
            }
            degraded = {"short": short_deg, "midlong": mid_deg}
            hint = _shadow_hint(short_state, midlong_state)

            gate_rows.append(
                {
                    "board_kind": kind,
                    "board_code_source": DEFAULT_BOARD_CODE_SOURCE,
                    "board_code": code,
                    "trade_date": asof,
                    "board_name": m.get("board_name"),
                    "trade_observe_flag": observe,
                    "short_raw": short_raw,
                    "short_state": short_state,
                    "short_confirm_count": short_cnt,
                    "midlong_raw": midlong_raw,
                    "midlong_state": midlong_state,
                    "midlong_confirm_count": midlong_cnt,
                    "conflict_action": ca,
                    "evidence_json": evidence,
                    "degraded_json": degraded,
                    "shadow_hard_filter_hint": hint,
                    "v2_enabled": use_v2,
                }
            )
            if short_state == GATE_ALLOC:
                stats["short_alloc"] += 1
            if short_state == GATE_AVOID:
                stats["short_avoid"] += 1
            if midlong_state == GATE_ALLOC:
                stats["midlong_alloc"] += 1
            if midlong_state == GATE_AVOID:
                stats["midlong_avoid"] += 1

    _process("industry", industry, ind_ctx)
    _process("concept", concepts, con_ctx)

    n = upsert_board_gates(db, gate_rows)
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "success": True,
        "trade_date": asof,
        "v2_enabled": use_v2,
        "hard_filter_enabled": hard_filter_enabled(),
        "boards": n,
        "fund_features": len(fund_rows),
        "board_rs": len(rs_rows),
        "valuations": len(val_rows),
        "stats": stats,
    }


def run_board_gates_daily(trade_date: Optional[str] = None) -> Dict[str, Any]:
    """工作流 / CLI 入口。"""
    from backend_core.database.db import SessionLocal

    db = SessionLocal()
    try:
        return compute_board_gates_for_date(db, trade_date, commit=True)
    finally:
        db.close()
