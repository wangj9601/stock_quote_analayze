# -*- coding: utf-8 -*-
"""行业交易观察池自动候选日批。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

from backend_core.board_gates.fund_features import build_fund_feature_rows
from backend_core.board_gates.storage import resolve_asof_trade_date
from backend_core.board_metrics.sector_slope_store import (
    load_board_sector_slopes_multi,
    slope_strong_threshold_for_window,
)
from backend_core.board_observe.config import (
    ACTION_IN_POOL,
    ACTION_SUGGEST_IN,
    ACTION_SUGGEST_OUT,
    ACTION_WATCH,
    DEFAULT_BOARD_CODE_SOURCE,
    IN_CONFIRM_DAYS,
    LOCK_FOLLOW,
    MAINLINE_LOOKBACK_HITS,
    OUT_CONFIRM_DAYS,
    SENTIMENT_TOP_N,
    SOFT_CAP,
    TOP_N_NEW,
)
from backend_core.board_observe.score import score_board
from backend_core.board_observe.storage import (
    ensure_board_observe_tables,
    load_prior_eligibility,
    upsert_observe_candidates,
)
from backend_core.strategies.gms.board_resonance import (
    evaluate_board_environment,
    evaluate_multi_window_board_trend,
)

logger = logging.getLogger(__name__)


def _load_industry_metas(db, board_code_source: str) -> List[Dict[str, Any]]:
    """加载同花顺行业宇宙；正式池标记与同名其它来源（如东财）OR 对齐。"""
    try:
        rows = db.execute(
            text(
                """
                SELECT t.board_code, t.board_name,
                       (
                         COALESCE(t.trade_observe_flag, FALSE)
                         OR EXISTS (
                           SELECT 1 FROM industry_board_basic_info o
                           WHERE o.board_name IS NOT NULL
                             AND t.board_name IS NOT NULL
                             AND o.board_name = t.board_name
                             AND COALESCE(o.trade_observe_flag, FALSE) = TRUE
                         )
                       ) AS trade_observe_flag,
                       COALESCE(t.observe_lock, 'follow') AS observe_lock,
                       COALESCE(t.frontend_visible_flag, TRUE) AS frontend_visible_flag
                FROM industry_board_basic_info t
                WHERE COALESCE(t.board_code_source, :src) = :src
                ORDER BY t.board_code
                """
            ),
            {"src": board_code_source},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("load industry metas (with lock) failed: %s — fallback", e)
        try:
            db.rollback()
        except Exception:
            pass
        rows = db.execute(
            text(
                """
                SELECT board_code, board_name,
                       COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag
                FROM industry_board_basic_info
                WHERE COALESCE(board_code_source, :src) = :src
                ORDER BY board_code
                """
            ),
            {"src": board_code_source},
        ).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["observe_lock"] = LOCK_FOLLOW
            d["frontend_visible_flag"] = True
            out.append(d)
        return out


def _load_bar_counts(db, trade_date: str) -> Dict[str, int]:
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, COUNT(*)::int AS cnt
                FROM industry_board_historical_quotes
                WHERE trade_date <= CAST(:td AS date)
                GROUP BY board_code
                """
            ),
            {"td": trade_date[:10]},
        ).fetchall()
        return {str(c).strip(): int(n or 0) for c, n in rows}
    except Exception as e:
        logger.warning("bar counts failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}


def _load_rs_map(db, trade_date: str) -> Dict[str, int]:
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, rs_rating
                FROM board_rs_ratings
                WHERE board_kind = 'industry'
                  AND trade_date = CAST(:td AS date)
                  AND rs_rating IS NOT NULL
                """
            ),
            {"td": trade_date[:10]},
        ).fetchall()
        return {str(c).strip(): int(r) for c, r in rows if c is not None and r is not None}
    except Exception as e:
        logger.debug("rs map: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}


def _load_focus_codes(db, trade_date: str) -> Set[str]:
    """主线命中（若有行业）∪ 涨幅 TopN ∪ 资金净流入 TopN。"""
    out: Set[str] = set()
    td = trade_date[:10]
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, COUNT(*)::int AS cnt
                FROM market_daily_mainline_hits
                WHERE hit = TRUE
                  AND board_type = 'industry'
                  AND trade_date::date <= CAST(:td AS date)
                  AND trade_date::date >= CAST(:td AS date) - INTERVAL '14 days'
                GROUP BY board_code
                """
            ),
            {"td": td},
        ).fetchall()
        for c, cnt in rows:
            if int(cnt or 0) >= MAINLINE_LOOKBACK_HITS:
                out.add(str(c).strip())
            # 当日命中也算焦点
        today = db.execute(
            text(
                """
                SELECT board_code FROM market_daily_mainline_hits
                WHERE hit = TRUE AND board_type = 'industry'
                  AND trade_date::date = CAST(:td AS date)
                """
            ),
            {"td": td},
        ).fetchall()
        for (c,) in today:
            out.add(str(c).strip())
    except Exception as e:
        logger.debug("industry mainline: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    for order_col in ("change_percent", "main_net_inflow"):
        try:
            rows = db.execute(
                text(
                    f"""
                    SELECT board_code
                    FROM board_fund_flow_daily
                    WHERE board_kind = 'industry'
                      AND board_code_source = :src
                      AND trade_date = CAST(:td AS date)
                      AND {order_col} IS NOT NULL
                    ORDER BY {order_col} DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {
                    "src": DEFAULT_BOARD_CODE_SOURCE,
                    "td": td,
                    "lim": SENTIMENT_TOP_N,
                },
            ).fetchall()
            for (c,) in rows:
                out.add(str(c).strip())
        except Exception as e:
            logger.debug("focus %s: %s", order_col, e)
            try:
                db.rollback()
            except Exception:
                pass
    return out


def _sticky_count(today_ok: bool, prior: List[bool], need: int) -> int:
    """含今日的连续满足天数。"""
    if not today_ok:
        return 0
    n = 1
    for ok in prior:
        if ok:
            n += 1
        else:
            break
        if n >= need + 2:
            break
    return n


def compute_observe_candidates_for_date(
    db,
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_board_observe_tables(db)
    asof = resolve_asof_trade_date(db, trade_date)
    src = DEFAULT_BOARD_CODE_SOURCE

    metas = _load_industry_metas(db, src)
    metas = [m for m in metas if m.get("frontend_visible_flag", True) is not False]
    codes = [str(m["board_code"]).strip() for m in metas if m.get("board_code")]
    if not codes:
        return {"success": True, "trade_date": asof, "rows": 0, "suggest_in": 0, "suggest_out": 0}

    windows = (120, 60, 20, 10, 5)
    slopes_by_window = load_board_sector_slopes_multi(
        db, codes, board_kind="industry", asof_date=asof, windows=windows
    )
    bar_counts = _load_bar_counts(db, asof)
    rs_map = _load_rs_map(db, asof)
    focus = _load_focus_codes(db, asof)

    _WIN_FIELDS = {
        120: ("sector_slope_120", "board_env_120"),
        60: ("sector_slope", "board_env"),
        20: ("sector_slope_20", "board_env_20"),
        10: ("sector_slope_short", "board_env_short"),
        5: ("sector_slope_5", "board_env_5"),
    }

    # 先建 env 上下文供 fund_stage
    ctx: Dict[str, Dict[str, Any]] = {}
    for code in codes:
        item: Dict[str, Any] = {"board_code": code}
        for w, (slope_key, env_key) in _WIN_FIELDS.items():
            detail = (slopes_by_window.get(w) or {}).get(code) or {}
            slope_v = detail.get("sector_slope")
            r2_v = detail.get("slope_r2")
            item[slope_key] = slope_v
            if w == 60:
                item["slope_source"] = detail.get("slope_source")
            env = evaluate_board_environment(
                sector_slope_v=slope_v,
                board_change_percent=None,
                slope_strong_threshold=slope_strong_threshold_for_window(w),
                use_realtime_fallback=False,
                slope_r2=r2_v,
                sector_slope_window=w,
            )
            item[env_key] = env.get("board_env")
        trend = evaluate_multi_window_board_trend(item)
        item["board_trend_label"] = (trend or {}).get("board_trend_label")
        ctx[code] = item

    fund_rows = build_fund_feature_rows(
        db,
        codes,
        board_kind="industry",
        trade_date=asof,
        short_strong_by_code={
            c: (ctx[c].get("board_env_5") == "strong" or ctx[c].get("board_env_short") == "strong")
            for c in codes
        },
        mid_weak_by_code={c: ctx[c].get("board_env") == "weak" for c in codes},
        board_code_source=src,
    )
    fund_by = {str(r["board_code"]): r for r in fund_rows}

    prior_in = load_prior_eligibility(
        db, trade_date=asof, field="in", limit_days=IN_CONFIRM_DAYS
    )
    prior_out = load_prior_eligibility(
        db, trade_date=asof, field="out", limit_days=OUT_CONFIRM_DAYS
    )

    formal_n = sum(1 for m in metas if m.get("trade_observe_flag"))
    pool_at_cap = formal_n >= SOFT_CAP

    scored: List[Dict[str, Any]] = []
    for m in metas:
        code = str(m["board_code"]).strip()
        c = ctx.get(code) or {}
        feat = fund_by.get(code) or {}
        in_pool = bool(m.get("trade_observe_flag"))
        lock = str(m.get("observe_lock") or LOCK_FOLLOW).strip().lower() or LOCK_FOLLOW
        score, evidence, vetoes, _hard, in_el, out_el = score_board(
            env60=c.get("board_env"),
            slope60=c.get("sector_slope"),
            env120=c.get("board_env_120"),
            slope120=c.get("sector_slope_120"),
            slope_source_60=c.get("slope_source"),
            net_sum_20=feat.get("net_sum_20"),
            board_rs=rs_map.get(code),
            mainline_or_focus=code in focus,
            bars=bar_counts.get(code, 0),
            board_trend_label=c.get("board_trend_label"),
            fund_stage=feat.get("fund_stage"),
            observe_lock=lock,
            in_formal_pool=in_pool,
        )
        sticky_in = _sticky_count(in_el, prior_in.get(code) or [], IN_CONFIRM_DAYS)
        sticky_out = _sticky_count(out_el, prior_out.get(code) or [], OUT_CONFIRM_DAYS)

        if in_pool and out_el:
            action = ACTION_SUGGEST_OUT
            sticky = sticky_out
            adoptable = sticky_out >= OUT_CONFIRM_DAYS and lock != "include"
        elif (not in_pool) and in_el:
            action = ACTION_SUGGEST_IN
            sticky = sticky_in
            # 软上限：批量采纳默认关，但仍允许 sticky 后 adoptable=True 供逐个确认
            adoptable = sticky_in >= IN_CONFIRM_DAYS
            if pool_at_cap:
                evidence["soft_cap_reached"] = True
                evidence["batch_adopt_blocked"] = True
        elif in_pool:
            action = ACTION_IN_POOL
            sticky = sticky_in
            adoptable = False
        else:
            action = ACTION_WATCH
            sticky = sticky_in
            adoptable = False

        scored.append(
            {
                "board_code": code,
                "board_code_source": src,
                "trade_date": asof,
                "board_name": m.get("board_name"),
                "trade_observe_flag": in_pool,
                "observe_lock": lock,
                "action": action,
                "score": score,
                "sticky_count": sticky,
                "adoptable": adoptable,
                "rank_in": None,
                "evidence_json": evidence,
                "veto_json": vetoes,
                "_slope60": c.get("sector_slope"),
                "_rs": rs_map.get(code),
                "_in_el": in_el,
            }
        )

    # Top N 新候选排名（未在池且 in_eligible）
    newcomers = [r for r in scored if r["action"] == ACTION_SUGGEST_IN]
    newcomers.sort(
        key=lambda r: (
            -int(r["score"]),
            -(r["_rs"] if r["_rs"] is not None else -1),
            -(float(r["_slope60"]) if r["_slope60"] is not None else -1e9),
            r["board_code"],
        )
    )
    for i, r in enumerate(newcomers, start=1):
        r["rank_in"] = i
        if i > TOP_N_NEW:
            r["adoptable"] = False
            ev = r["evidence_json"]
            ev["beyond_top_n"] = True

    # 落库：suggest_in/out + 正式池对照 + 有分数的 watch（score>=1）以利排查
    to_store = []
    for r in scored:
        if r["action"] in (ACTION_SUGGEST_IN, ACTION_SUGGEST_OUT, ACTION_IN_POOL):
            to_store.append(r)
        elif r["action"] == ACTION_WATCH and int(r["score"]) >= 1:
            to_store.append(r)
        r.pop("_slope60", None)
        r.pop("_rs", None)
        r.pop("_in_el", None)

    n = upsert_observe_candidates(db, to_store)
    sug_in = sum(1 for r in to_store if r["action"] == ACTION_SUGGEST_IN)
    sug_out = sum(1 for r in to_store if r["action"] == ACTION_SUGGEST_OUT)
    adoptable_n = sum(1 for r in to_store if r.get("adoptable"))
    return {
        "success": True,
        "trade_date": asof,
        "rows": n,
        "suggest_in": sug_in,
        "suggest_out": sug_out,
        "adoptable": adoptable_n,
        "formal_pool": formal_n,
        "soft_cap": SOFT_CAP,
        "pool_at_cap": pool_at_cap,
    }


def run_board_observe_candidates_daily(
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    from backend_core.database.db import SessionLocal

    db = SessionLocal()
    try:
        return compute_observe_candidates_for_date(db, trade_date=trade_date)
    except Exception as e:
        logger.exception("observe candidates failed")
        try:
            db.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
    finally:
        db.close()
