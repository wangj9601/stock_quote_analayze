# -*- coding: utf-8 -*-
"""每日复盘指标计算：优先涨停池，回退 historical_quotes 代理。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.board_roles.classify import is_limit_up, is_st_name, limit_up_threshold_for_code
from backend_core.market_review.picks import build_review_picks
from backend_core.market_review.render import export_markdown_file, render_markdown
from backend_core.market_review.rules import (
    PERCENTILE_MIN_SAMPLE,
    build_sentiment,
    build_trend_rules,
    classify_season,
    classify_tape_regime,
    curve_position_note,
    draft_advice,
    draft_viewpoint,
    evaluate_hard_gates,
    yuan_to_yi,
)

logger = logging.getLogger(__name__)

PERCENTILE_WINDOW = 79
LO_POS_MAX = 0.35
LO_SAMPLE_MIN = 30


def _prev_calendar_candidates(trade_date: str, n: int = 20) -> List[str]:
    """生成往前若干自然日字符串，供 SQL IN 过滤后再取交易日。"""
    base = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    return [(base - timedelta(days=i)).isoformat() for i in range(0, n + 1)]


def _trading_dates_on_or_before(db: Session, trade_date: str, limit: int) -> List[str]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT date
            FROM historical_quotes
            WHERE date <= :d
            ORDER BY date DESC
            LIMIT :lim
            """
        ),
        {"d": trade_date[:10], "lim": max(limit, 1)},
    ).fetchall()
    dates = [str(r[0])[:10] for r in rows]
    dates.reverse()
    return dates


def _zt_pool_count(db: Session, trade_date: str) -> int:
    return int(
        db.execute(
            text("SELECT COUNT(*) FROM stock_zt_pool_daily WHERE trade_date = :d"),
            {"d": trade_date[:10]},
        ).scalar()
        or 0
    )


# 有池数据则优先用官方连板数；空池才回退日终涨幅代理
ZT_POOL_MIN_ROWS = 1


def _metrics_from_zt_pool(db: Session, trade_date: str, prev_date: Optional[str]) -> Dict[str, Any]:
    d = trade_date[:10]
    limit_up_count = _zt_pool_count(db, d)
    cb = int(
        db.execute(
            text(
                """
                SELECT COUNT(*) FROM stock_zt_pool_daily
                WHERE trade_date = :d AND COALESCE(board_count, 0) >= 2
                """
            ),
            {"d": d},
        ).scalar()
        or 0
    )
    height = db.execute(
        text(
            """
            SELECT MAX(board_count) FROM stock_zt_pool_daily
            WHERE trade_date = :d
            """
        ),
        {"d": d},
    ).scalar()
    height = int(height) if height is not None else 0

    prev_cb_return = None
    if prev_date:
        # 昨日连板≥2 的代码，今日涨跌幅：优先今日池，否则行情表
        row = db.execute(
            text(
                """
                WITH prev_cb AS (
                    SELECT code FROM stock_zt_pool_daily
                    WHERE trade_date = :prev AND COALESCE(board_count, 0) >= 2
                )
                SELECT AVG(COALESCE(z.change_percent, h.change_percent))
                FROM prev_cb p
                LEFT JOIN stock_zt_pool_daily z
                  ON z.code = p.code AND z.trade_date = :d
                LEFT JOIN historical_quotes h
                  ON h.code = p.code AND h.date = :d
                """
            ),
            {"prev": prev_date[:10], "d": d},
        ).scalar()
        if row is not None:
            prev_cb_return = float(row)

    return {
        "limit_up_count": limit_up_count,
        "cb_count": cb,
        "height": height,
        "prev_cb_return": prev_cb_return,
        "limit_source": "em_zt_pool",
    }


def _max_consec(dates: List[str]) -> int:
    if not dates:
        return 0
    ordered = sorted(set(dates))
    best = 1
    cur = 1
    for i in range(1, len(ordered)):
        d0 = datetime.strptime(ordered[i - 1], "%Y-%m-%d").date()
        d1 = datetime.strptime(ordered[i], "%Y-%m-%d").date()
        gap = (d1 - d0).days
        if 1 <= gap <= 3:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def _metrics_from_hist_proxy(
    db: Session, trade_date: str, prev_date: Optional[str], lookback_dates: Sequence[str]
) -> Dict[str, Any]:
    """用日终涨幅代理计算涨停/连板。"""
    d = trade_date[:10]
    rows = db.execute(
        text(
            """
            SELECT code, name, change_percent
            FROM historical_quotes
            WHERE date = :d AND change_percent IS NOT NULL
            """
        ),
        {"d": d},
    ).fetchall()

    limit_codes = []
    for code, name, chg in rows:
        if is_st_name(name):
            continue
        if is_limit_up(code, chg):
            limit_codes.append(str(code).zfill(6))

    # 近窗涨停日
    if lookback_dates:
        lim_rows = db.execute(
            text(
                """
                SELECT code, name, date, change_percent
                FROM historical_quotes
                WHERE date = ANY(:dates) AND change_percent IS NOT NULL
                """
            ),
            {"dates": list(lookback_dates)},
        ).fetchall()
    else:
        lim_rows = []

    by_code: Dict[str, List[str]] = {}
    for code, name, dt, chg in lim_rows:
        if is_st_name(name):
            continue
        if not is_limit_up(code, chg):
            continue
        c = str(code).zfill(6)
        by_code.setdefault(c, []).append(str(dt)[:10])

    consec_today = {}
    for c, dates in by_code.items():
        # 只统计到 trade_date 的连板
        dates = [x for x in dates if x <= d]
        if d not in dates:
            continue
        consec_today[c] = _max_consec(dates)

    cb = sum(1 for v in consec_today.values() if v >= 2)
    height = max(consec_today.values()) if consec_today else 0

    prev_cb_return = None
    if prev_date:
        prev_cb_codes = []
        for c, dates in by_code.items():
            dates_p = [x for x in dates if x <= prev_date[:10]]
            if prev_date[:10] in dates_p and _max_consec(dates_p) >= 2:
                prev_cb_codes.append(c)
        if prev_cb_codes:
            avg = db.execute(
                text(
                    """
                    SELECT AVG(change_percent)
                    FROM historical_quotes
                    WHERE date = :d AND code = ANY(:codes)
                    """
                ),
                {"d": d, "codes": prev_cb_codes},
            ).scalar()
            if avg is not None:
                prev_cb_return = float(avg)

    return {
        "limit_up_count": len(limit_codes),
        "cb_count": cb,
        "height": int(height),
        "prev_cb_return": prev_cb_return,
        "limit_source": "hist_proxy",
    }


def _compute_vol(db: Session, trade_date: str) -> Optional[float]:
    row = db.execute(
        text(
            """
            SELECT SUM(amount)
            FROM historical_quotes
            WHERE date = :d
              AND amount IS NOT NULL
              AND (name IS NULL OR (
                    UPPER(REPLACE(name, ' ', '')) NOT LIKE 'ST%'
                AND UPPER(REPLACE(name, ' ', '')) NOT LIKE '*ST%'
                AND UPPER(REPLACE(name, ' ', '')) NOT LIKE 'S*ST%'
                AND UPPER(REPLACE(name, ' ', '')) NOT LIKE 'SST%'
              ))
            """
        ),
        {"d": trade_date[:10]},
    ).scalar()
    if row is None:
        return None
    return float(row) / 1e12


def _compute_lo_hi(db: Session, trade_date: str, trading_dates: Sequence[str]) -> Dict[str, Any]:
    """近10日累计涨幅：Hi=全市场最大；Lo=低位组中位数（不足则 P20）。"""
    if len(trading_dates) < 2:
        return {"lo_value": None, "hi_value": None, "sp_value": None}

    win = list(trading_dates[-10:]) if len(trading_dates) >= 10 else list(trading_dates)
    start_d, end_d = win[0], win[-1]
    # 60 日窗口用于相对位置
    pos_dates = list(trading_dates[-60:]) if len(trading_dates) >= 2 else list(trading_dates)
    pos_start = pos_dates[0]

    rows = db.execute(
        text(
            """
            SELECT code, name, date, close
            FROM historical_quotes
            WHERE date >= :ps AND date <= :ed
              AND close IS NOT NULL AND close > 0
            """
        ),
        {"ps": pos_start, "ed": end_d},
    ).fetchall()

    by_code: Dict[str, Dict[str, float]] = {}
    names: Dict[str, str] = {}
    for code, name, dt, close in rows:
        c = str(code).zfill(6)
        if is_st_name(name):
            continue
        names[c] = str(name or "")
        by_code.setdefault(c, {})[str(dt)[:10]] = float(close)

    rets = []
    low_rets = []
    for c, series in by_code.items():
        if start_d not in series or end_d not in series:
            continue
        c0, c1 = series[start_d], series[end_d]
        if c0 <= 0:
            continue
        ret = (c1 / c0 - 1.0) * 100.0
        rets.append(ret)
        # 相对位置：用 pos 窗口高低
        vals = [series[d] for d in pos_dates if d in series]
        if len(vals) >= 5:
            lo_p, hi_p = min(vals), max(vals)
            if hi_p > lo_p:
                pos = (c1 - lo_p) / (hi_p - lo_p)
                if pos <= LO_POS_MAX:
                    low_rets.append(ret)

    if not rets:
        return {"lo_value": None, "hi_value": None, "sp_value": None}

    rets_sorted = sorted(rets)
    hi_value = max(rets_sorted)
    if len(low_rets) >= LO_SAMPLE_MIN:
        low_sorted = sorted(low_rets)
        mid = len(low_sorted) // 2
        if len(low_sorted) % 2:
            lo_value = low_sorted[mid]
        else:
            lo_value = (low_sorted[mid - 1] + low_sorted[mid]) / 2.0
    else:
        # P20
        idx = max(0, int(len(rets_sorted) * 0.2) - 1)
        lo_value = rets_sorted[idx]

    return {
        "lo_value": float(lo_value),
        "hi_value": float(hi_value),
        "sp_value": float(hi_value - lo_value),
    }


def _percentile(hist_vals: List[float], value: Optional[float]) -> Optional[float]:
    if value is None or not hist_vals:
        return None
    n = sum(1 for x in hist_vals if x <= value)
    return round(100.0 * n / len(hist_vals), 1)


def _safe(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _merge_board_hit(
    hits: Dict[Tuple[str, str], Dict[str, Any]],
    *,
    trade_date: str,
    board_type: str,
    code: str,
    name: str,
    reason: str,
    **extra: Any,
) -> None:
    code_s = str(code or "").strip()
    if not code_s or code_s.startswith("ZT:"):
        return
    key = (board_type, code_s)
    item = hits.get(key)
    if not item:
        item = {
            "trade_date": trade_date,
            "board_type": board_type,
            "board_code": code_s,
            "board_name": name,
            "hit": True,
            "hit_reasons": [],
            "change_percent": extra.get("change_percent"),
            "limit_up_count": extra.get("limit_up_count"),
            "net_inflow": extra.get("net_inflow"),
        }
        hits[key] = item
    if reason not in item["hit_reasons"]:
        item["hit_reasons"].append(reason)
    for k in ("change_percent", "limit_up_count", "net_inflow"):
        if extra.get(k) is not None and item.get(k) is None:
            item[k] = extra[k]
    if name and (not item.get("board_name") or item["board_name"] == code_s):
        item["board_name"] = name


def _fetch_ths_board_tops(
    db: Session,
    trade_date: str,
    board_kind: str,
    *,
    change_limit: int = 15,
    inflow_limit: int = 10,
    industry_realtime_fallback: bool = False,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """同花顺单日涨幅/资金流上榜合成（不写库）。"""
    d = trade_date[:10]
    hits: Dict[Tuple[str, str], Dict[str, Any]] = {}

    rows = []
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, board_name, change_percent
                FROM board_fund_flow_daily
                WHERE trade_date = CAST(:d AS date)
                  AND board_kind = :k
                  AND board_code_source = 'tonghuashun'
                ORDER BY change_percent DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"d": d, "k": board_kind, "lim": change_limit},
        ).fetchall()
    except Exception:
        db.rollback()
        rows = []

    if not rows and board_kind == "industry" and industry_realtime_fallback:
        try:
            rows = db.execute(
                text(
                    """
                    SELECT board_code, board_name, change_percent
                    FROM industry_board_realtime_quotes
                    WHERE board_code LIKE '88%'
                    ORDER BY change_percent DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {"lim": change_limit},
            ).fetchall()
        except Exception:
            db.rollback()
            rows = []

    for code, name, chg in rows:
        _merge_board_hit(
            hits,
            trade_date=d,
            board_type=board_kind,
            code=str(code),
            name=str(name or code),
            reason="涨幅Top15",
            change_percent=_safe(chg),
        )

    try:
        ff = db.execute(
            text(
                """
                SELECT board_code, board_name, main_net_inflow
                FROM board_fund_flow_daily
                WHERE trade_date = CAST(:d AS date)
                  AND board_kind = :k
                  AND board_code_source = 'tonghuashun'
                ORDER BY main_net_inflow DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"d": d, "k": board_kind, "lim": inflow_limit},
        ).fetchall()
    except Exception:
        db.rollback()
        ff = []
    for code, name, net in ff:
        _merge_board_hit(
            hits,
            trade_date=d,
            board_type=board_kind,
            code=str(code),
            name=str(name or code),
            reason="资金流Top10",
            net_inflow=_safe(net),
        )
    return hits


def compute_mainline_hits(db: Session, trade_date: str) -> List[Dict[str, Any]]:
    """合成日榜上榜命中并写入 market_daily_mainline_hits。

    主线口径：仅同花顺**概念**板块（涨幅 Top15 ∪ 资金流 Top10）。
    行业板块不计入主线次数，改由 build_industry_confirm 做当日赛道确认。
    """
    d = trade_date[:10]
    hits = _fetch_ths_board_tops(db, d, "concept")

    db.execute(text("DELETE FROM market_daily_mainline_hits WHERE trade_date = :d"), {"d": d})
    for item in hits.values():
        db.execute(
            text(
                """
                INSERT INTO market_daily_mainline_hits (
                    trade_date, board_type, board_code, board_name, hit,
                    hit_reasons, change_percent, limit_up_count, net_inflow, created_at
                ) VALUES (
                    :trade_date, :board_type, :board_code, :board_name, :hit,
                    CAST(:hit_reasons AS jsonb), :change_percent, :limit_up_count,
                    :net_inflow, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                **item,
                "hit_reasons": json.dumps(item["hit_reasons"], ensure_ascii=False),
            },
        )
    db.commit()
    return list(hits.values())


def build_industry_confirm(db: Session, trade_date: str) -> Dict[str, Any]:
    """当日同花顺行业涨幅/资金流上榜 → 赛道确认（不计入近10日主线次数）。"""
    d = trade_date[:10]
    hits = _fetch_ths_board_tops(
        db, d, "industry", industry_realtime_fallback=True
    )
    rows = []
    for item in hits.values():
        reasons = item.get("hit_reasons") or []
        rows.append(
            {
                "board_type": "industry",
                "board_code": item["board_code"],
                "board_name": item.get("board_name") or item["board_code"],
                "hit_reasons": reasons,
                "change_percent": item.get("change_percent"),
                "net_inflow": item.get("net_inflow"),
                "label": "赛道确认",
                "reason_text": "、".join(reasons) if reasons else "—",
            }
        )
    rows.sort(
        key=lambda r: (
            -(r.get("change_percent") if r.get("change_percent") is not None else -9999),
            r.get("board_name") or "",
        )
    )
    n = len(rows)
    if n == 0:
        summary = "今日无同花顺行业涨幅/资金流上榜，赛道确认偏弱。"
    else:
        names = "、".join(r["board_name"] for r in rows[:8])
        more = f" 等{n}个" if n > 8 else f"（共{n}个）"
        summary = (
            f"今日行业确认上榜 {n} 个（涨幅Top15∪资金流Top10）：{names}{more}。"
            "有对应概念主线时更可信，仅行业无概念则慎追。"
        )
    return {"rows": rows, "summary": summary, "count": n}


def build_mainline_summary(db: Session, trade_date: str) -> Dict[str, Any]:
    """近10日主线：仅统计同花顺概念；附带当日行业赛道确认。"""
    d = trade_date[:10]
    industry_confirm = build_industry_confirm(db, d)
    dates = _trading_dates_on_or_before(db, d, 10)
    if not dates:
        return {
            "policy": "concept_primary",
            "rows": [],
            "summary": "暂无交易日数据",
            "industry_confirm": industry_confirm,
        }

    rows = db.execute(
        text(
            """
            SELECT board_type, board_code, board_name, trade_date, hit_reasons
            FROM market_daily_mainline_hits
            WHERE trade_date = ANY(:dates)
              AND hit = TRUE
              AND board_type = 'concept'
            """
        ),
        {"dates": dates},
    ).fetchall()

    agg: Dict[Tuple[str, str], Dict[str, Any]] = {}
    today_set = set()
    for btype, bcode, bname, td, reasons in rows:
        code_s = str(bcode or "").strip()
        # 历史误写入的东财涨停池行业别名不再展示
        if not code_s or code_s.startswith("ZT:"):
            continue
        key = (str(btype), code_s)
        item = agg.setdefault(
            key,
            {
                "board_type": btype,
                "board_code": code_s,
                "board_name": bname or code_s,
                "hits_10d": 0,
                "days": set(),
            },
        )
        td_s = str(td)[:10]
        if td_s not in item["days"]:
            item["days"].add(td_s)
            item["hits_10d"] += 1
        if td_s == d:
            today_set.add(key)

    out_rows = []
    for key, item in agg.items():
        hits = item["hits_10d"]
        today = key in today_set
        if hits >= 5:
            tier_label = "★★★ 核心主线"
        elif hits >= 3:
            tier_label = "★★ 核心主线"
        else:
            tier_label = "观察"
        if today and hits == 1:
            echelon = "新面孔"
            today_status = "🟩 今日上榜"
        elif today:
            echelon = "持续"
            today_status = "🟩 今日上榜"
        elif hits >= 3:
            echelon = "休整"
            today_status = "❌ 今日跌落"
        else:
            echelon = "滑出主线" if hits >= 2 else "掉队"
            today_status = "❌ 今日跌落"
        out_rows.append(
            {
                "board_type": item["board_type"],
                "board_code": item["board_code"],
                "board_name": item["board_name"],
                "hits_10d": hits,
                "tier_label": tier_label,
                "today_status": today_status,
                "echelon": echelon,
                "today_hit": today,
            }
        )

    out_rows.sort(key=lambda x: (-x["hits_10d"], x["board_name"]))
    roles = split_industry_roles(industry_confirm.get("rows") or [])
    focus = _focus_names(roles)
    shown = filter_concept_rows(out_rows, focus)
    active = sum(1 for r in shown if r["today_hit"])
    core = sum(1 for r in out_rows if r["hits_10d"] >= 3)
    ind_n = int(industry_confirm.get("count") or 0)
    summary = (
        f"近10日统计同花顺概念 {len(out_rows)} 个，正文展示 {len(shown)} 个"
        f"（上榜不少于 2 次，或今日上榜且对应主线/支线），核心主线 {core} 个；"
        f"今日概念活跃上榜 {active} 个；行业赛道确认 {ind_n} 个。"
    )
    return {
        "policy": "concept_primary",
        "rows": shown,
        "rows_all": out_rows,
        "summary": summary,
        "industry_confirm": industry_confirm,
    }


INDEX_SPECS = (
    ("000001.SH", "上证指数", True),
    ("399001.SZ", "深证成指", False),
    ("399006.SZ", "创业板指", False),
    ("000300.SH", "沪深300", False),
    ("000688.SH", "科创50", False),
)


def _index_amount_yi(amount: Any) -> Optional[float]:
    """指数成交额：大于约 1000 亿按元，否则按千元（Tushare）折算为亿元。"""
    v = _safe(amount)
    if v is None or v <= 0:
        return None
    if v >= 1e11:
        return v / 1e8
    return v / 1e5


def _hundred_crossed(pre_close: Any, close: Any) -> Optional[int]:
    pre = _safe(pre_close)
    px = _safe(close)
    if pre is None or px is None:
        return None
    level = int(px // 100) * 100
    if level <= 0:
        return None
    if pre < level <= px:
        return level
    return None


def _industry_row(
    code: Any,
    name: Any,
    change_percent: Any,
    net_inflow: Any,
    breadth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    code_s = str(code or "").strip()
    yi = yuan_to_yi(net_inflow)
    br = (breadth or {}).get(code_s) or {}
    return {
        "board_code": code_s,
        "board_name": str(name or code_s),
        "change_percent": _safe(change_percent),
        "net_inflow": _safe(net_inflow),
        "net_inflow_yi": None if yi is None else round(yi, 1),
        "up_count": br.get("up"),
        "down_count": br.get("down"),
    }


def split_industry_roles(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """领涨取有涨跌幅的前 10；主线为其中净流入最大者，其余正流入为支线。"""
    with_chg = [r for r in rows if r.get("change_percent") is not None]
    leaders = sorted(with_chg, key=lambda r: -float(r["change_percent"]))[:10]
    positive = [
        r for r in leaders if r.get("net_inflow") is not None and float(r["net_inflow"]) > 0
    ]
    main = None
    sides: List[Dict[str, Any]] = []
    if positive:
        main = max(positive, key=lambda r: float(r.get("net_inflow") or 0))
        sides = [r for r in positive if r is not main]
    return {"leaders": leaders, "main": main, "sidelines": sides}


def _focus_names(roles: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    main = roles.get("main") or {}
    if main.get("board_name"):
        names.append(str(main["board_name"]))
    for row in roles.get("sidelines") or []:
        if row.get("board_name"):
            names.append(str(row["board_name"]))
    return names


def concept_matches_focus(name: Any, focus_names: Sequence[str]) -> bool:
    n = str(name or "").strip()
    if len(n) < 2:
        return False
    for raw in focus_names:
        f = str(raw or "").strip()
        if len(f) < 2:
            continue
        if f in n or n in f:
            return True
    return False


def filter_concept_rows(
    rows: List[Dict[str, Any]],
    focus_names: Sequence[str],
) -> List[Dict[str, Any]]:
    shown = []
    for row in rows:
        hits = int(row.get("hits_10d") or 0)
        if hits >= 2:
            shown.append(row)
            continue
        if row.get("today_hit") and concept_matches_focus(row.get("board_name"), focus_names):
            shown.append(row)
    return shown


def _query_industry_rank(db: Session, trade_date: str, *, bottom: bool, limit: int) -> List[Any]:
    order = "ASC" if bottom else "DESC"
    try:
        return db.execute(
            text(
                f"""
                SELECT board_code, board_name, change_percent, main_net_inflow
                FROM board_fund_flow_daily
                WHERE trade_date = CAST(:d AS date)
                  AND board_kind = 'industry'
                  AND board_code_source = 'tonghuashun'
                  AND change_percent IS NOT NULL
                ORDER BY change_percent {order} NULLS LAST
                LIMIT :lim
                """
            ),
            {"d": trade_date[:10], "lim": limit},
        ).fetchall()
    except Exception:
        logger.exception("行业涨跌幅排名查询失败 trade_date=%s", trade_date)
        db.rollback()
        return []


def _board_breadth(db: Session, trade_date: str, codes: Sequence[str]) -> Dict[str, Dict[str, int]]:
    clean = [str(c).strip() for c in codes if str(c or "").strip()]
    if not clean:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT c.board_code,
                       SUM(CASE WHEN h.change_percent > 0 THEN 1 ELSE 0 END) AS up_n,
                       SUM(CASE WHEN h.change_percent < 0 THEN 1 ELSE 0 END) AS down_n,
                       COUNT(*) AS n
                FROM industry_board_constituents c
                JOIN historical_quotes h
                  ON h.code = c.stock_code AND h.date = :d
                WHERE c.board_code = ANY(:codes)
                GROUP BY c.board_code
                """
            ),
            {"d": trade_date[:10], "codes": clean},
        ).fetchall()
    except Exception:
        logger.exception("板块成分涨跌家数查询失败")
        db.rollback()
        return {}
    out: Dict[str, Dict[str, int]] = {}
    for code, up_n, down_n, n in rows:
        if not n:
            continue
        out[str(code)] = {"up": int(up_n or 0), "down": int(down_n or 0)}
    return out


def _capital_boards(db: Session, trade_date: str, *, outflow: bool, limit: int) -> List[Dict[str, Any]]:
    order = "ASC" if outflow else "DESC"
    cond = "AND main_net_inflow < 0" if outflow else "AND main_net_inflow > 0"
    try:
        rows = db.execute(
            text(
                f"""
                SELECT board_code, board_name, main_net_inflow
                FROM board_fund_flow_daily
                WHERE trade_date = CAST(:d AS date)
                  AND board_kind = 'industry'
                  AND board_code_source = 'tonghuashun'
                  AND main_net_inflow IS NOT NULL
                  {cond}
                ORDER BY main_net_inflow {order} NULLS LAST
                LIMIT :lim
                """
            ),
            {"d": trade_date[:10], "lim": limit},
        ).fetchall()
    except Exception:
        logger.exception("行业资金排名查询失败")
        db.rollback()
        return []
    out = []
    for code, name, net in rows:
        yi = yuan_to_yi(net)
        out.append(
            {
                "board_code": str(code or ""),
                "board_name": str(name or code or ""),
                "net_inflow": _safe(net),
                "net_inflow_yi": None if yi is None else round(yi, 1),
            }
        )
    return out


def build_sector_pack(
    db: Session,
    trade_date: str,
    industry_confirm: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """领涨/领跌、主线支线、轮动、资金方向。成分涨跌对不上则留空。"""
    d = trade_date[:10]
    dates = _trading_dates_on_or_before(db, d, 2)
    prev = dates[-2] if len(dates) >= 2 else None

    gain_rows = _query_industry_rank(db, d, bottom=False, limit=10)
    loss_rows = _query_industry_rank(db, d, bottom=True, limit=3)
    codes = [str(r[0]) for r in list(gain_rows) + list(loss_rows)]
    breadth = _board_breadth(db, d, codes)
    leaders = [
        _industry_row(c, n, chg, net, breadth) for c, n, chg, net in gain_rows
    ]
    laggards = [
        _industry_row(c, n, chg, net, breadth) for c, n, chg, net in loss_rows
    ]
    # 领跌不应与领涨重复（全市场不足 13 个行业时）
    lead_codes = {r["board_code"] for r in leaders}
    laggards = [r for r in laggards if r["board_code"] not in lead_codes]

    if leaders:
        roles = split_industry_roles(leaders)
    else:
        roles = split_industry_roles((industry_confirm or {}).get("rows") or [])
        leaders = roles["leaders"]

    main = roles["main"]
    sidelines = roles["sidelines"]

    today_hits = _fetch_ths_board_tops(db, d, "industry")
    y_hits = _fetch_ths_board_tops(db, prev, "industry") if prev else {}
    today_names = {str(v.get("board_name") or "") for v in today_hits.values()}
    y_names = {str(v.get("board_name") or "") for v in y_hits.values()}
    today_names.discard("")
    y_names.discard("")
    dropped = sorted(y_names - today_names)
    new_names = today_names - y_names
    new_items = []
    for item in today_hits.values():
        name = str(item.get("board_name") or "")
        if name not in new_names:
            continue
        net = item.get("net_inflow")
        if net is None or float(net) <= 0:
            continue
        yi = yuan_to_yi(net)
        new_items.append(
            {
                "board_name": name,
                "board_code": item.get("board_code"),
                "net_inflow_yi": None if yi is None else round(yi, 1),
                "net_inflow": _safe(net),
            }
        )
    new_items.sort(key=lambda r: -(r.get("net_inflow") or 0))

    def _main_payload(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row or not row.get("board_name"):
            return None
        yi = row.get("net_inflow_yi")
        if yi is None:
            conv = yuan_to_yi(row.get("net_inflow"))
            yi = None if conv is None else round(conv, 1)
        return {
            "board_code": row.get("board_code"),
            "board_name": row.get("board_name"),
            "change_percent": row.get("change_percent"),
            "net_inflow": row.get("net_inflow"),
            "net_inflow_yi": yi,
            "up_count": row.get("up_count"),
            "down_count": row.get("down_count"),
        }

    return {
        "leaders": leaders,
        "laggards": laggards,
        "main": _main_payload(main),
        "sidelines": [_main_payload(r) for r in sidelines if r],
        "rotation": {
            "dropped": dropped,
            "new_inflow": new_items[:5],
        },
        "capital_in": _capital_boards(db, d, outflow=False, limit=5),
        "capital_out": _capital_boards(db, d, outflow=True, limit=3),
    }


def _name_matches_industry(stock_industry: Any, main_name: Any) -> bool:
    a = str(stock_industry or "").strip()
    b = str(main_name or "").strip()
    if len(a) < 2 or len(b) < 2:
        return False
    return a in b or b in a


def build_tape_detail(
    db: Session,
    trade_date: str,
    main: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """连板梯队、主线封单、个股主力净流入。对不上行业则省略过滤结果。"""
    d = trade_date[:10]
    ladder = {"b2": 0, "b3": 0, "b4plus": 0}
    height_stock = None
    max_board = 0
    seal_leaders: List[Dict[str, Any]] = []
    main_name = (main or {}).get("board_name")
    main_code = (main or {}).get("board_code")
    try:
        rows = db.execute(
            text(
                """
                SELECT code, name, change_percent, seal_fund, board_count, industry
                FROM stock_zt_pool_daily
                WHERE trade_date = :d
                """
            ),
            {"d": d},
        ).fetchall()
    except Exception:
        logger.exception("涨停池梯队查询失败")
        db.rollback()
        rows = []

    matched = []
    for code, name, chg, seal, board_count, industry in rows:
        bc = int(board_count or 0)
        if bc >= 4:
            ladder["b4plus"] += 1
        elif bc == 3:
            ladder["b3"] += 1
        elif bc == 2:
            ladder["b2"] += 1
        if bc > max_board:
            max_board = bc
            height_stock = {"code": str(code), "name": str(name or code), "board_count": bc}
        if main_name and _name_matches_industry(industry, main_name):
            seal_yi = yuan_to_yi(seal)
            matched.append(
                {
                    "code": str(code),
                    "name": str(name or code),
                    "change_percent": _safe(chg),
                    "seal_fund": _safe(seal),
                    "seal_yi": None if seal_yi is None else round(seal_yi, 2),
                    "board_count": bc,
                }
            )
    matched.sort(key=lambda r: -(r.get("seal_fund") or 0))
    seal_leaders = matched[:5]

    flow_top: List[Dict[str, Any]] = []
    try:
        flow_rows = db.execute(
            text(
                """
                SELECT code, name, net_amount
                FROM stock_fund_flow_daily
                WHERE trade_date = :d AND net_amount IS NOT NULL
                ORDER BY net_amount DESC NULLS LAST
                LIMIT 5
                """
            ),
            {"d": d},
        ).fetchall()
        for code, name, net in flow_rows:
            yi = yuan_to_yi(net)
            flow_top.append(
                {
                    "code": str(code),
                    "name": str(name or code),
                    "net_inflow_yi": None if yi is None else round(yi, 2),
                }
            )
    except Exception:
        logger.exception("个股资金流排名查询失败")
        db.rollback()
        flow_top = []

    main_flow: List[Dict[str, Any]] = []
    if main_code:
        try:
            mf = db.execute(
                text(
                    """
                    SELECT f.code, f.name, f.net_amount
                    FROM stock_fund_flow_daily f
                    JOIN industry_board_constituents c ON c.stock_code = f.code
                    WHERE f.trade_date = :d
                      AND c.board_code = :bc
                      AND f.net_amount IS NOT NULL
                    ORDER BY f.net_amount DESC NULLS LAST
                    LIMIT 3
                    """
                ),
                {"d": d, "bc": str(main_code)},
            ).fetchall()
            for code, name, net in mf:
                yi = yuan_to_yi(net)
                main_flow.append(
                    {
                        "code": str(code),
                        "name": str(name or code),
                        "net_inflow_yi": None if yi is None else round(yi, 2),
                    }
                )
        except Exception:
            logger.exception("主线内资金流查询失败")
            db.rollback()
            main_flow = []

    has_ladder = bool(rows) and (ladder["b2"] or ladder["b3"] or ladder["b4plus"] or height_stock)
    return {
        "ladder": ladder if has_ladder else None,
        "height_stock": height_stock,
        "seal_leaders": seal_leaders,
        "flow_top": flow_top,
        "main_flow_top": main_flow,
    }


def _compute_breadth(db: Session, trade_date: str) -> Dict[str, Any]:
    d = trade_date[:10]
    try:
        rows = db.execute(
            text(
                """
                SELECT code, name, change_percent
                FROM historical_quotes
                WHERE date = :d AND change_percent IS NOT NULL
                """
            ),
            {"d": d},
        ).fetchall()
    except Exception:
        logger.exception("涨跌家数查询失败")
        db.rollback()
        return {}
    up = down = flat = limit_down = 0
    for code, name, chg in rows:
        if is_st_name(name):
            continue
        try:
            chg_f = float(chg)
        except (TypeError, ValueError):
            continue
        if chg_f > 0:
            up += 1
        elif chg_f < 0:
            down += 1
        else:
            flat += 1
        if chg_f <= -limit_up_threshold_for_code(code):
            limit_down += 1
    if up == 0 and down == 0 and flat == 0:
        return {}
    return {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "limit_down_count": limit_down,
    }


def compute_market_env(
    db: Session,
    trade_date: str,
    vol_trillion: Any,
    y_vol: Any,
) -> Dict[str, Any]:
    d = trade_date[:10]
    indexes: List[Dict[str, Any]] = []
    sh_gap = None
    for ts_code, fallback, integer_gate in INDEX_SPECS:
        try:
            row = db.execute(
                text(
                    """
                    SELECT name, close, pre_close, pct_chg, amount
                    FROM index_historical_quotes
                    WHERE ts_code = :ts AND trade_date = CAST(:d AS date)
                    """
                ),
                {"ts": ts_code, "d": d},
            ).mappings().first()
        except Exception:
            logger.exception("指数行情查询失败 ts=%s", ts_code)
            db.rollback()
            row = None
        if not row or row.get("close") is None:
            continue
        try:
            high20 = db.execute(
                text(
                    """
                    SELECT MAX(high) FROM (
                        SELECT high
                        FROM index_historical_quotes
                        WHERE ts_code = :ts AND trade_date <= CAST(:d AS date)
                        ORDER BY trade_date DESC
                        LIMIT 20
                    ) t
                    """
                ),
                {"ts": ts_code, "d": d},
            ).scalar()
        except Exception:
            db.rollback()
            high20 = None
        close = _safe(row.get("close"))
        gap = None
        if close is not None and high20 is not None:
            gap = round(float(high20) - close, 2)
        if integer_gate:
            sh_gap = gap
        note = ""
        if integer_gate:
            level = _hundred_crossed(row.get("pre_close"), close)
            if level:
                note = f"收盘站上{level}点"
        indexes.append(
            {
                "ts_code": ts_code,
                "name": str(row.get("name") or fallback),
                "close": close,
                "pct_chg": _safe(row.get("pct_chg")),
                "amount_yi": _index_amount_yi(row.get("amount")),
                "gap_to_high20": gap,
                "note": note,
            }
        )

    vol = _safe(vol_trillion)
    yv = _safe(y_vol)
    delta_yi = None
    if vol is not None and yv is not None:
        delta_yi = round((vol - yv) * 10000.0, 1)
    return {
        "indexes": indexes,
        "vol_trillion": vol,
        "vol_delta_yi": delta_yi,
        "above_2t": bool(vol is not None and vol >= 2.0),
        "breadth": _compute_breadth(db, d),
        "sh_gap_to_high20": sh_gap,
    }


def compute_market_metrics(db: Session, trade_date: str) -> Dict[str, Any]:
    d = trade_date[:10]
    dates = _trading_dates_on_or_before(db, d, max(PERCENTILE_WINDOW + 5, 70))
    if not dates:
        # 允许仅有涨停池时仍计算部分指标
        dates = [d]
    prev_date = dates[-2] if len(dates) >= 2 else None

    vol = _compute_vol(db, d)
    zt_n = _zt_pool_count(db, d)
    if zt_n >= ZT_POOL_MIN_ROWS:
        lim = _metrics_from_zt_pool(db, d, prev_date)
    else:
        if zt_n > 0:
            logger.warning(
                "涨停池行数过少 trade_date=%s n=%s < %s，回退 hist_proxy",
                d,
                zt_n,
                ZT_POOL_MIN_ROWS,
            )
        lookback = dates[-15:] if len(dates) >= 2 else dates
        lim = _metrics_from_hist_proxy(db, d, prev_date, lookback)

    lohi = _compute_lo_hi(db, d, dates)

    return {
        "trade_date": d,
        "vol_trillion": vol,
        **lim,
        **lohi,
    }


def _load_review_history(db: Session, trade_date: str, limit: int = PERCENTILE_WINDOW) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT trade_date, vol_trillion, limit_up_count, cb_count, height,
                   prev_cb_return, lo_value, hi_value, sp_value, limit_source
            FROM market_daily_review
            WHERE trade_date <= :d
            ORDER BY trade_date DESC
            LIMIT :lim
            """
        ),
        {"d": trade_date[:10], "lim": limit},
    ).mappings().all()
    out = [dict(r) for r in rows]
    out.reverse()
    return out


def build_review_snapshot(
    db: Session,
    trade_date: str,
    *,
    export_md: bool = False,
    keep_overrides: bool = True,
) -> Dict[str, Any]:
    d = trade_date[:10]
    metrics = compute_market_metrics(db, d)
    compute_mainline_hits(db, d)
    mainline = build_mainline_summary(db, d)

    # 先写入基础指标，便于百分位用历史
    existing = db.execute(
        text(
            """
            SELECT viewpoint_md, advice_md, viewpoint_override, advice_override
            FROM market_daily_review WHERE trade_date = :d
            """
        ),
        {"d": d},
    ).mappings().first()

    db.execute(
        text(
            """
            INSERT INTO market_daily_review (
                trade_date, vol_trillion, limit_up_count, cb_count, height,
                prev_cb_return, lo_value, hi_value, sp_value, limit_source,
                computed_at, updated_at
            ) VALUES (
                :trade_date, :vol_trillion, :limit_up_count, :cb_count, :height,
                :prev_cb_return, :lo_value, :hi_value, :sp_value, :limit_source,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (trade_date) DO UPDATE SET
                vol_trillion = EXCLUDED.vol_trillion,
                limit_up_count = EXCLUDED.limit_up_count,
                cb_count = EXCLUDED.cb_count,
                height = EXCLUDED.height,
                prev_cb_return = EXCLUDED.prev_cb_return,
                lo_value = EXCLUDED.lo_value,
                hi_value = EXCLUDED.hi_value,
                sp_value = EXCLUDED.sp_value,
                limit_source = EXCLUDED.limit_source,
                computed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        metrics,
    )
    db.commit()

    hist = _load_review_history(db, d, PERCENTILE_WINDOW)
    # 确保今日在 hist 末尾
    if not hist or str(hist[-1].get("trade_date"))[:10] != d:
        hist.append(metrics)

    lo_hist = [float(x["lo_value"]) for x in hist if x.get("lo_value") is not None]
    hi_hist = [float(x["hi_value"]) for x in hist if x.get("hi_value") is not None]
    sp_hist = [float(x["sp_value"]) for x in hist if x.get("sp_value") is not None]

    sample_n = len(hist)
    metrics["percentile_sample"] = sample_n
    if sample_n < PERCENTILE_MIN_SAMPLE:
        metrics["lo_percentile"] = None
        metrics["hi_percentile"] = None
        metrics["sp_percentile"] = None
        metrics["percentile_note"] = "样本不足"
    else:
        metrics["lo_percentile"] = _percentile(lo_hist, metrics.get("lo_value"))
        metrics["hi_percentile"] = _percentile(hi_hist, metrics.get("hi_value"))
        metrics["sp_percentile"] = _percentile(sp_hist, metrics.get("sp_value"))
        metrics["percentile_note"] = None

    yesterday = hist[-2] if len(hist) >= 2 else None
    y_vol = (yesterday or {}).get("vol_trillion")
    market_env = compute_market_env(db, d, metrics.get("vol_trillion"), y_vol)
    sector = build_sector_pack(db, d, mainline.get("industry_confirm"))
    focus = _focus_names({"main": sector.get("main"), "sidelines": sector.get("sidelines")})
    source_rows = mainline.get("rows_all") or mainline.get("rows") or []
    if focus:
        mainline["rows"] = filter_concept_rows(source_rows, focus)
    tape_detail = build_tape_detail(db, d, sector.get("main"))
    sector["ladder"] = tape_detail.get("ladder")
    sector["height_stock"] = tape_detail.get("height_stock")
    sector["seal_leaders"] = tape_detail.get("seal_leaders")
    sector["flow_top"] = tape_detail.get("flow_top")
    sector["main_flow_top"] = tape_detail.get("main_flow_top")
    mainline["sector"] = sector

    gates = evaluate_hard_gates(metrics, hist)
    season = classify_season(
        metrics.get("cb_count"), metrics.get("height"), metrics.get("prev_cb_return")
    )
    rules = build_trend_rules(metrics, yesterday)
    tape = classify_tape_regime(metrics, yesterday, market_env.get("breadth"))
    zones = curve_position_note(
        sample_n,
        metrics.get("lo_percentile"),
        metrics.get("hi_percentile"),
        metrics.get("sp_percentile"),
    )
    sentiment = build_sentiment(metrics, yesterday, tape, market_env, sector)
    focus_main = []
    if sector.get("main") and sector["main"].get("board_name"):
        focus_main.append(str(sector["main"]["board_name"]))
    concept_codes = []
    for row in mainline.get("rows") or []:
        if not concept_matches_focus(row.get("board_name"), focus_main):
            continue
        if row.get("board_code"):
            concept_codes.append(str(row["board_code"]))
    prev_for_picks = str((yesterday or {}).get("trade_date") or "")[:10] or None
    try:
        rules["picks"] = build_review_picks(
            db,
            d,
            sector=sector,
            tape=tape,
            season=season,
            gates=gates,
            concept_board_codes=concept_codes,
            prev_date=prev_for_picks,
        )
    except Exception:
        logger.exception("复盘个股短名单失败")
        db.rollback()
        rules["picks"] = {
            "disclaimer": "规则合成参考，非投资建议。这是明日计划，不是按收盘价买入。",
            "note": "名单生成失败",
            "mode": "empty",
            "no_chase": [],
            "track": [],
            "sideline": [],
            "avoid": [],
        }
    rules["tape"] = tape
    rules["market_env"] = market_env
    rules["curve_zones"] = zones
    rules["percentile_sample"] = sample_n
    rules["sentiment"] = sentiment
    viewpoint = draft_viewpoint(metrics, rules, season, tape, market_env, sector)
    advice = draft_advice(gates, season, rules, tape, sentiment)

    vp_override = bool(existing and existing.get("viewpoint_override"))
    ad_override = bool(existing and existing.get("advice_override"))
    if keep_overrides and vp_override and existing.get("viewpoint_md"):
        viewpoint = existing["viewpoint_md"]
    if keep_overrides and ad_override and existing.get("advice_md"):
        advice = existing["advice_md"]

    snapshot = {
        **metrics,
        "hard_gates": gates,
        "season": season.get("season"),
        "season_detail": season,
        "rules_json": rules,
        "mainline_json": mainline,
        "viewpoint_md": viewpoint,
        "advice_md": advice,
        "viewpoint_override": vp_override,
        "advice_override": ad_override,
    }

    db.execute(
        text(
            """
            UPDATE market_daily_review SET
                lo_percentile = :lo_percentile,
                hi_percentile = :hi_percentile,
                sp_percentile = :sp_percentile,
                hard_gates = CAST(:hard_gates AS jsonb),
                season = :season,
                season_detail = CAST(:season_detail AS jsonb),
                rules_json = CAST(:rules_json AS jsonb),
                mainline_json = CAST(:mainline_json AS jsonb),
                viewpoint_md = :viewpoint_md,
                advice_md = :advice_md,
                viewpoint_override = :viewpoint_override,
                advice_override = :advice_override,
                updated_at = CURRENT_TIMESTAMP
            WHERE trade_date = :trade_date
            """
        ),
        {
            "trade_date": d,
            "lo_percentile": snapshot.get("lo_percentile"),
            "hi_percentile": snapshot.get("hi_percentile"),
            "sp_percentile": snapshot.get("sp_percentile"),
            "hard_gates": json.dumps(gates, ensure_ascii=False),
            "season": snapshot.get("season"),
            "season_detail": json.dumps(season, ensure_ascii=False),
            "rules_json": json.dumps(rules, ensure_ascii=False),
            "mainline_json": json.dumps(mainline, ensure_ascii=False),
            "viewpoint_md": viewpoint,
            "advice_md": advice,
            "viewpoint_override": vp_override,
            "advice_override": ad_override,
        },
    )
    db.commit()

    if export_md:
        path = export_markdown_file(snapshot)
        snapshot["export_path"] = str(path)
    snapshot["markdown"] = render_markdown(snapshot)
    return snapshot


def get_review_snapshot(db: Session, trade_date: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text("SELECT * FROM market_daily_review WHERE trade_date = :d"),
        {"d": trade_date[:10]},
    ).mappings().first()
    if not row:
        return None
    data = dict(row)
    for k in ("hard_gates", "season_detail", "rules_json", "mainline_json"):
        v = data.get(k)
        if isinstance(v, str):
            try:
                data[k] = json.loads(v)
            except Exception:
                pass
    data["markdown"] = render_markdown(data)
    return data


def update_review_text(
    db: Session,
    trade_date: str,
    *,
    viewpoint_md: Optional[str] = None,
    advice_md: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    sets = []
    params: Dict[str, Any] = {"d": trade_date[:10]}
    if viewpoint_md is not None:
        sets.append("viewpoint_md = :viewpoint_md")
        sets.append("viewpoint_override = TRUE")
        params["viewpoint_md"] = viewpoint_md
    if advice_md is not None:
        sets.append("advice_md = :advice_md")
        sets.append("advice_override = TRUE")
        params["advice_md"] = advice_md
    if not sets:
        return get_review_snapshot(db, trade_date)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    db.execute(
        text(f"UPDATE market_daily_review SET {', '.join(sets)} WHERE trade_date = :d"),
        params,
    )
    db.commit()
    return get_review_snapshot(db, trade_date)


def collect_and_build_review(
    trade_date: Optional[str] = None,
    *,
    collect_zt: bool = True,
    export_md: bool = True,
) -> Dict[str, Any]:
    """工作流入口：可选先采涨停池，再算复盘快照。"""
    from backend_core.data_collectors.akshare.zt_pool_em import collect_zt_pool_em
    from backend_core.database.db import SessionLocal

    d = (trade_date or datetime.now().strftime("%Y-%m-%d"))[:10]
    zt_result = None
    if collect_zt:
        zt_result = collect_zt_pool_em(d)
    db = SessionLocal()
    try:
        snap = build_review_snapshot(db, d, export_md=export_md)
        return {
            "success": True,
            "trade_date": d,
            "zt_pool": zt_result,
            "limit_source": snap.get("limit_source"),
            "season": snap.get("season"),
            "hard_gates_rate": (snap.get("hard_gates") or {}).get("rate"),
            "export_path": snap.get("export_path"),
        }
    finally:
        db.close()
