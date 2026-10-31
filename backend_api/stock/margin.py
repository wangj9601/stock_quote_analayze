# -*- coding: utf-8 -*-
"""个股两融日序列与融资踩踏旁证（公开数据推断，非账户强平实锤）。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    normalize_code,
    safe_float,
)
from backend_core.market_review.margin_summary import (
    compute_margin_market_summary,
    resolve_margin_trade_date,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["stock_margin"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DISCLAIMER = (
    "旁证基于公开两融余额/净偿还与流通市值推断，不能证明某家机构账户被券商强平。"
)

RANK_METRICS = (
    "rzmre",
    "rz_net",
    "rzye",
    "rzye_drop_5d",
    "crowding",
)

# 信号阈值（可后续调环境变量）
CROWDING_HIGH = 0.08  # 融资余额/流通市值 ≥ 8%
REPAY_ACCEL_RATIO = 2.0  # 当日净偿还相对近5日均值倍数
BALANCE_DROP_5D = 0.08  # 5 日融资余额降幅 ≥ 8%
LOOKBACK_SIGNAL = 25


def _rz_net(rzye_row: Dict[str, Any]) -> Optional[float]:
    rzmre = safe_float(rzye_row.get("rzmre"))
    rzche = safe_float(rzye_row.get("rzche"))
    if rzmre is None and rzche is None:
        return None
    return (rzmre or 0.0) - (rzche or 0.0)


def _row_to_api(r: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "code": r.get("code"),
        "trade_date": r.get("trade_date"),
        "name": r.get("name"),
        "rzye": safe_float(r.get("rzye")),
        "rzmre": safe_float(r.get("rzmre")),
        "rzche": safe_float(r.get("rzche")),
        "rqye": safe_float(r.get("rqye")),
        "rqyl": safe_float(r.get("rqyl")),
        "rqmcl": safe_float(r.get("rqmcl")),
        "rqchl": safe_float(r.get("rqchl")),
        "rzrqye": safe_float(r.get("rzrqye")),
        "source": r.get("source"),
    }
    out["rz_net"] = _rz_net(out)
    return out


def _fetch_margin_rows(
    db: Session,
    code: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 250,
) -> List[Dict[str, Any]]:
    code_n = normalize_code(code)
    if not code_n:
        return []
    sql = """
        SELECT code, trade_date, name, rzye, rzmre, rzche, rqye, rqyl,
               rqmcl, rqchl, rzrqye, source
        FROM stock_margin_daily
        WHERE code = :code
    """
    params: Dict[str, Any] = {"code": code_n}
    if start and _DATE_RE.match(start):
        sql += " AND trade_date >= :start"
        params["start"] = start
    if end and _DATE_RE.match(end):
        sql += " AND trade_date <= :end"
        params["end"] = end
    sql += " ORDER BY trade_date ASC"
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _resolve_float_mv(
    db: Session, code: str, trade_date: str
) -> Tuple[Optional[float], Optional[str]]:
    """流通市值（元）。优先实时表，其次 流通股本 × 收盘价。"""
    code_n = normalize_code(code)
    if not code_n:
        return None, None
    td = (trade_date or "")[:10]

    # 实时行情流通市值
    try:
        rt = db.execute(
            text(
                """
                SELECT circulating_market_value
                FROM stock_realtime_quote
                WHERE code = :code
                ORDER BY trade_date DESC
                LIMIT 1
                """
            ),
            {"code": code_n},
        ).mappings().first()
        if rt:
            mv = safe_float(rt.get("circulating_market_value"))
            if mv and mv > 0:
                return mv, "stock_realtime_quote.circulating_market_value"
    except Exception as e:
        logger.debug("float_mv realtime fail %s: %s", code_n, e)

    close = None
    close_src = None
    # 当日收盘
    try:
        hq = db.execute(
            text(
                """
                SELECT close FROM historical_quotes
                WHERE code = :code AND CAST(date AS text) = :td
                LIMIT 1
                """
            ),
            {"code": code_n, "td": td},
        ).mappings().first()
        if hq:
            close = safe_float(hq.get("close"))
            if close:
                close_src = "historical_quotes.close"
    except Exception as e:
        logger.debug("float_mv hq exact fail %s: %s", code_n, e)

    if close is None:
        try:
            hq2 = db.execute(
                text(
                    """
                    SELECT close FROM historical_quotes
                    WHERE code = :code AND CAST(date AS text) <= :td
                    ORDER BY date DESC LIMIT 1
                    """
                ),
                {"code": code_n, "td": td},
            ).mappings().first()
            if hq2:
                close = safe_float(hq2.get("close"))
                if close:
                    close_src = "historical_quotes.close<=td"
        except Exception as e:
            logger.debug("float_mv hq le fail %s: %s", code_n, e)

    if close is None:
        try:
            hq3 = db.execute(
                text(
                    """
                    SELECT close FROM historical_quotes
                    WHERE code = :code
                    ORDER BY date DESC LIMIT 1
                    """
                ),
                {"code": code_n},
            ).mappings().first()
            if hq3:
                close = safe_float(hq3.get("close"))
                if close:
                    close_src = "historical_quotes.latest"
        except Exception as e:
            logger.debug("float_mv hq latest fail %s: %s", code_n, e)

    if close is None:
        try:
            rt2 = db.execute(
                text(
                    """
                    SELECT current_price FROM stock_realtime_quote
                    WHERE code = :code
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """
                ),
                {"code": code_n},
            ).mappings().first()
            if rt2:
                close = safe_float(rt2.get("current_price"))
                if close:
                    close_src = "stock_realtime_quote.current_price"
        except Exception as e:
            logger.debug("float_mv rt price fail %s: %s", code_n, e)

    try:
        basic = db.execute(
            text(
                """
                SELECT free_float_shares FROM stock_basic_info
                WHERE code = :code LIMIT 1
                """
            ),
            {"code": code_n},
        ).mappings().first()
        shares = safe_float(basic.get("free_float_shares")) if basic else None
        if shares and shares > 0 and close and close > 0:
            mv = shares * close
            if shares < 1e6:
                mv = shares * 1e4 * close
            return mv, f"free_float_shares*{close_src or 'close'}"
    except Exception as e:
        logger.debug("float_mv basic fail %s: %s", code_n, e)
    return None, None


def _percentile_rank(values: List[float], x: float) -> Optional[float]:
    if not values:
        return None
    sorted_v = sorted(values)
    n = len(sorted_v)
    less = sum(1 for v in sorted_v if v < x)
    equal = sum(1 for v in sorted_v if v == x)
    return (less + 0.5 * equal) / n


def _compute_signal(
    series: List[Dict[str, Any]],
    *,
    trade_date: str,
    float_mv: Optional[float],
    float_mv_source: Optional[str],
) -> Dict[str, Any]:
    by_date = {str(r.get("trade_date"))[:10]: r for r in series}
    target = by_date.get(trade_date[:10])
    if not target and series:
        # 取不超过 trade_date 的最近一日
        candidates = [d for d in by_date if d <= trade_date[:10]]
        if candidates:
            trade_date = max(candidates)
            target = by_date[trade_date]
    if not target:
        return {
            "trade_date": trade_date,
            "available": False,
            "error": "无两融数据",
            "disclaimer": DISCLAIMER,
        }

    api_rows = [_row_to_api(r) for r in series]
    api_by = {r["trade_date"]: r for r in api_rows}
    cur = api_by.get(trade_date) or _row_to_api(target)
    rzye = cur.get("rzye")
    rz_net = cur.get("rz_net")

    crowding = None
    if rzye is not None and float_mv and float_mv > 0:
        crowding = rzye / float_mv

    # 近 N 日序列（含当日）
    dates = sorted(d for d in api_by if d <= trade_date)
    window = dates[-LOOKBACK_SIGNAL:]
    rzye_hist = [api_by[d]["rzye"] for d in window if api_by[d].get("rzye") is not None]
    rz_net_hist = [
        api_by[d]["rz_net"] for d in window if api_by[d].get("rz_net") is not None
    ]

    # 连续净偿还（rz_net < 0）天数
    neg_streak = 0
    for d in reversed(dates):
        n = api_by[d].get("rz_net")
        if n is not None and n < 0:
            neg_streak += 1
        else:
            break

    # 5/10 日余额降幅
    def _drop(n_days: int) -> Optional[float]:
        if rzye is None or len(dates) < n_days + 1:
            return None
        prev_d = dates[-(n_days + 1)]
        prev = api_by[prev_d].get("rzye")
        if prev is None or prev <= 0:
            return None
        return (prev - rzye) / prev

    drop_5 = _drop(5)
    drop_10 = _drop(10)

    # 净偿还加速：当日净偿还（正偿还= -rz_net）相对近5日均值
    accel_repay = False
    repay_today = (-rz_net) if rz_net is not None and rz_net < 0 else None
    if repay_today and repay_today > 0 and len(rz_net_hist) >= 6:
        prior = [-x for x in rz_net_hist[:-1] if x is not None and x < 0]
        prior = prior[-5:]
        if prior:
            avg = sum(prior) / len(prior)
            if avg > 0 and repay_today >= avg * REPAY_ACCEL_RATIO:
                accel_repay = True

    rzye_pctile = (
        _percentile_rank(rzye_hist, rzye) if rzye is not None and rzye_hist else None
    )
    # 余额处于近20日高位后加速下降更危险：用历史分位偏高 + 降幅
    high_crowding = crowding is not None and crowding >= CROWDING_HIGH
    balance_collapse = drop_5 is not None and drop_5 >= BALANCE_DROP_5D

    flags = {
        "high_crowding": bool(high_crowding),
        "accel_repay": bool(accel_repay),
        "balance_collapse": bool(balance_collapse),
        "neg_net_streak_ge_3": neg_streak >= 3,
    }
    score = sum(1 for v in flags.values() if v)
    if score >= 3:
        squeeze_risk = "high"
    elif score >= 2:
        squeeze_risk = "mid"
    elif score >= 1:
        squeeze_risk = "low"
    else:
        squeeze_risk = "low"

    # 无任何负向 flag 时标 none 更清晰
    if score == 0:
        squeeze_risk = "none"

    label_map = {
        "none": "未见明显踩踏旁证",
        "low": "踩踏风险偏低",
        "mid": "踩踏风险中等（去杠杆旁证）",
        "high": "踩踏风险偏高（去杠杆加速旁证，非爆仓实锤）",
    }
    return {
        "trade_date": trade_date,
        "available": True,
        "code": cur.get("code"),
        "name": cur.get("name"),
        "rzye": rzye,
        "rz_net": rz_net,
        "float_mv": float_mv,
        "float_mv_source": float_mv_source,
        "crowding": crowding,
        "rzye_pctile_20d": rzye_pctile,
        "rzye_drop_5d": drop_5,
        "rzye_drop_10d": drop_10,
        "neg_net_streak": neg_streak,
        "flags": flags,
        "squeeze_risk": squeeze_risk,
        "squeeze_label": label_map.get(squeeze_risk, squeeze_risk),
        "disclaimer": DISCLAIMER,
        "source": cur.get("source"),
    }


def _fetch_dragon_tiger_org(
    db: Session, code: str, trade_date: str
) -> Optional[Dict[str, Any]]:
    """同日龙虎榜机构净额旁证（库内快照；东方财富源常为 NULL）。"""
    code_n = normalize_code(code)
    td = (trade_date or "")[:10]
    if not code_n or not td:
        return None
    try:
        row = db.execute(
            text(
                """
                SELECT code, name, trade_date, board_type, org_net_value,
                       net_value, source
                FROM dragon_tiger_stock
                WHERE code = :code AND trade_date = :td
                  AND org_net_value IS NOT NULL
                ORDER BY CASE board_type
                    WHEN 'org' THEN 0
                    WHEN 'all' THEN 1
                    ELSE 2 END
                LIMIT 1
                """
            ),
            {"code": code_n, "td": td},
        ).mappings().first()
        if not row:
            return None
        org_net = safe_float(row.get("org_net_value"))
        return {
            "trade_date": str(row.get("trade_date") or "")[:10],
            "board_type": row.get("board_type"),
            "org_net_value": org_net,
            "net_value": safe_float(row.get("net_value")),
            "source": row.get("source"),
            "note": (
                "龙虎榜机构净额为同日席位披露旁证，与两融去杠杆叠加仍不能证明强平。"
                if org_net is not None and org_net < 0
                else "龙虎榜机构净额旁证。"
            ),
        }
    except Exception as e:
        logger.debug("dragon_tiger org lookup fail %s %s: %s", code_n, td, e)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _attach_extras(
    db: Session, signal: Dict[str, Any], *, with_lhb: bool = True
) -> Dict[str, Any]:
    if not signal or not signal.get("available"):
        return signal
    if with_lhb:
        lhb = _fetch_dragon_tiger_org(
            db, str(signal.get("code") or ""), str(signal.get("trade_date") or "")
        )
        signal["dragon_tiger"] = lhb
        if (
            lhb
            and lhb.get("org_net_value") is not None
            and float(lhb["org_net_value"]) < 0
            and signal.get("squeeze_risk") in ("mid", "high")
        ):
            signal["composite_hint"] = (
                "两融去杠杆旁证 + 龙虎榜机构净卖出，风险提示加重（仍非爆仓实锤）"
            )
        else:
            signal["composite_hint"] = None
    return signal


@router.get("/margin/market/summary")
async def get_margin_market_summary(
    trade_date: Optional[str] = Query(None, description="披露日 YYYY-MM-DD"),
    top_n: int = Query(5, ge=1, le=30),
    db: Session = Depends(get_db),
):
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
            status_code=400,
        )
    try:
        data = compute_margin_market_summary(db, trade_date, top_n=top_n)
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.exception("get_margin_market_summary")
        return JSONResponse(
            {"success": False, "message": f"汇总失败: {e}"}, status_code=500
        )


@router.get("/margin/rank")
async def get_margin_rank(
    metric: str = Query(
        "rz_net",
        description="rzmre|rz_net|rzye|rzye_drop_5d|crowding",
    ),
    trade_date: Optional[str] = Query(None),
    limit: int = Query(40, ge=5, le=100),
    side: str = Query("top", description="top|bottom"),
    db: Session = Depends(get_db),
):
    metric_n = (metric or "rz_net").strip().lower()
    if metric_n not in RANK_METRICS:
        return JSONResponse(
            {
                "success": False,
                "message": f"metric 须为 {', '.join(RANK_METRICS)}",
            },
            status_code=400,
        )
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
            status_code=400,
        )
    d = resolve_margin_trade_date(db, trade_date)
    if not d:
        return JSONResponse(
            {
                "success": False,
                "message": "无两融数据，请先日采/回填",
                "disclaimer": DISCLAIMER,
            },
            status_code=404,
        )
    ascending = (side or "top").lower() == "bottom"
    try:
        if metric_n in ("rzmre", "rzye"):
            col = metric_n
            order = "ASC" if ascending else "DESC"
            rows = db.execute(
                text(
                    f"""
                    SELECT code, name, rzye, rzmre, rzche, rqye,
                           (COALESCE(rzmre,0) - COALESCE(rzche,0)) AS rz_net
                    FROM stock_margin_daily
                    WHERE trade_date = :d AND {col} IS NOT NULL
                    ORDER BY {col} {order} NULLS LAST
                    LIMIT :n
                    """
                ),
                {"d": d, "n": int(limit)},
            ).mappings().all()
            items = []
            for i, r in enumerate(rows, 1):
                val = safe_float(r.get(col))
                items.append(
                    {
                        "rank": i,
                        "code": r["code"],
                        "name": r["name"],
                        "metric": metric_n,
                        "value": val,
                        "rzye": safe_float(r.get("rzye")),
                        "rzmre": safe_float(r.get("rzmre")),
                        "rz_net": safe_float(r.get("rz_net")),
                    }
                )
        elif metric_n == "rz_net":
            order = "ASC" if ascending else "DESC"
            rows = db.execute(
                text(
                    f"""
                    SELECT code, name, rzye, rzmre, rzche,
                           (COALESCE(rzmre,0) - COALESCE(rzche,0)) AS rz_net
                    FROM stock_margin_daily
                    WHERE trade_date = :d
                    ORDER BY (COALESCE(rzmre,0) - COALESCE(rzche,0)) {order}
                    LIMIT :n
                    """
                ),
                {"d": d, "n": int(limit)},
            ).mappings().all()
            items = []
            for i, r in enumerate(rows, 1):
                val = safe_float(r.get("rz_net"))
                items.append(
                    {
                        "rank": i,
                        "code": r["code"],
                        "name": r["name"],
                        "metric": metric_n,
                        "value": val,
                        "rzye": safe_float(r.get("rzye")),
                        "rzmre": safe_float(r.get("rzmre")),
                        "rz_net": val,
                    }
                )
        elif metric_n == "rzye_drop_5d":
            # 当前余额相对 5 个交易日前：降幅 = (prev - cur) / prev
            rows = db.execute(
                text(
                    """
                    WITH cur AS (
                        SELECT code, name, rzye, rzmre, rzche,
                               (COALESCE(rzmre,0) - COALESCE(rzche,0)) AS rz_net
                        FROM stock_margin_daily
                        WHERE trade_date = :d AND rzye IS NOT NULL AND rzye > 0
                    ),
                    hist AS (
                        SELECT DISTINCT trade_date
                        FROM stock_margin_daily
                        WHERE trade_date <= :d
                        ORDER BY trade_date DESC
                        LIMIT 6
                    ),
                    prev_d AS (
                        SELECT MIN(trade_date) AS td FROM hist
                    )
                    SELECT c.code, c.name, c.rzye, c.rzmre, c.rz_net,
                           p.rzye AS rzye_prev,
                           CASE
                             WHEN p.rzye IS NOT NULL AND p.rzye > 0
                             THEN (p.rzye - c.rzye) / p.rzye
                             ELSE NULL
                           END AS drop_5d
                    FROM cur c
                    CROSS JOIN prev_d pd
                    LEFT JOIN stock_margin_daily p
                      ON p.code = c.code AND p.trade_date = pd.td
                    WHERE p.rzye IS NOT NULL AND p.rzye > 0
                    """
                ),
                {"d": d},
            ).mappings().all()
            scored = []
            for r in rows:
                drop = safe_float(r.get("drop_5d"))
                if drop is None:
                    continue
                scored.append((drop, r))
            scored.sort(key=lambda x: x[0], reverse=not ascending)
            items = []
            for i, (drop, r) in enumerate(scored[: int(limit)], 1):
                items.append(
                    {
                        "rank": i,
                        "code": r["code"],
                        "name": r["name"],
                        "metric": metric_n,
                        "value": drop,
                        "rzye": safe_float(r.get("rzye")),
                        "rzye_prev": safe_float(r.get("rzye_prev")),
                        "rz_net": safe_float(r.get("rz_net")),
                    }
                )
        else:  # crowding
            rows = db.execute(
                text(
                    """
                    SELECT m.code, m.name, m.rzye, m.rzmre, m.rzche,
                           (COALESCE(m.rzmre,0) - COALESCE(m.rzche,0)) AS rz_net,
                           COALESCE(
                             NULLIF(rt.circulating_market_value, 0),
                             CASE
                               WHEN b.free_float_shares IS NOT NULL
                                    AND b.free_float_shares > 0
                                    AND hq.close IS NOT NULL AND hq.close > 0
                               THEN CASE
                                 WHEN b.free_float_shares < 1000000
                                 THEN b.free_float_shares * 10000 * hq.close
                                 ELSE b.free_float_shares * hq.close
                               END
                               ELSE NULL
                             END
                           ) AS float_mv
                    FROM stock_margin_daily m
                    LEFT JOIN LATERAL (
                        SELECT circulating_market_value
                        FROM stock_realtime_quote
                        WHERE code = m.code
                        ORDER BY trade_date DESC
                        LIMIT 1
                    ) rt ON TRUE
                    LEFT JOIN stock_basic_info b ON b.code = m.code
                    LEFT JOIN LATERAL (
                        SELECT close FROM historical_quotes
                        WHERE code = m.code AND CAST(date AS text) <= :d
                        ORDER BY date DESC LIMIT 1
                    ) hq ON TRUE
                    WHERE m.trade_date = :d AND m.rzye IS NOT NULL AND m.rzye > 0
                    """
                ),
                {"d": d},
            ).mappings().all()
            scored = []
            for r in rows:
                mv = safe_float(r.get("float_mv"))
                rzye = safe_float(r.get("rzye"))
                if not mv or mv <= 0 or rzye is None:
                    continue
                crowding = rzye / mv
                scored.append((crowding, r, mv))
            scored.sort(key=lambda x: x[0], reverse=not ascending)
            items = []
            for i, (crowding, r, mv) in enumerate(scored[: int(limit)], 1):
                items.append(
                    {
                        "rank": i,
                        "code": r["code"],
                        "name": r["name"],
                        "metric": metric_n,
                        "value": crowding,
                        "rzye": safe_float(r.get("rzye")),
                        "float_mv": mv,
                        "rz_net": safe_float(r.get("rz_net")),
                    }
                )

        return JSONResponse(
            {
                "success": True,
                "data": {
                    "trade_date": d,
                    "metric": metric_n,
                    "side": "bottom" if ascending else "top",
                    "count": len(items),
                    "items": items,
                    "disclaimer": DISCLAIMER,
                    "note": "两融明细 T+1 披露；拥挤度/降幅为查询时计算。",
                },
            }
        )
    except Exception as e:
        logger.exception("get_margin_rank metric=%s", metric_n)
        return JSONResponse(
            {"success": False, "message": f"排行失败: {e}"}, status_code=500
        )


@router.get("/margin/signals")
async def get_margin_signals_batch(
    codes: str = Query(..., description="逗号分隔股票代码，最多 80 只"),
    trade_date: Optional[str] = Query(None),
    with_lhb: bool = Query(True),
    db: Session = Depends(get_db),
):
    raw = [c.strip() for c in (codes or "").split(",") if c.strip()]
    uniq: List[str] = []
    seen = set()
    for c in raw:
        n = normalize_code(c)
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)
        if len(uniq) >= 80:
            break
    if not uniq:
        return JSONResponse(
            {"success": False, "message": "无有效股票代码"}, status_code=400
        )
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
            status_code=400,
        )
    end = trade_date or datetime.now().strftime("%Y-%m-%d")
    start_dt = datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(days=60)
    start = start_dt.strftime("%Y-%m-%d")
    out: Dict[str, Any] = {}
    try:
        for code_n in uniq:
            rows = _fetch_margin_rows(
                db, code_n, start=start, end=end, limit=80
            )
            if not rows:
                out[code_n] = {
                    "available": False,
                    "code": code_n,
                    "error": "无两融数据",
                    "disclaimer": DISCLAIMER,
                }
                continue
            td = trade_date or str(rows[-1]["trade_date"])[:10]
            float_mv, mv_src = _resolve_float_mv(db, code_n, td)
            signal = _compute_signal(
                rows, trade_date=td, float_mv=float_mv, float_mv_source=mv_src
            )
            out[code_n] = _attach_extras(db, signal, with_lhb=with_lhb)
        return JSONResponse(
            {
                "success": True,
                "count": len(out),
                "data": out,
                "disclaimer": DISCLAIMER,
            }
        )
    except Exception as e:
        logger.exception("get_margin_signals_batch")
        return JSONResponse(
            {"success": False, "message": f"批量信号失败: {e}"}, status_code=500
        )


@router.get("/{code}/margin")
async def get_stock_margin(
    code: str,
    start: Optional[str] = Query(None, description="起始日 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    code_n = normalize_code(code)
    if not code_n:
        return JSONResponse(
            {"success": False, "message": "无效股票代码"}, status_code=400
        )
    try:
        rows = _fetch_margin_rows(db, code_n, start=start, end=end)
        data = [_row_to_api(r) for r in rows]
        return JSONResponse(
            {
                "success": True,
                "code": code_n,
                "count": len(data),
                "data": data,
                "disclaimer": DISCLAIMER,
            }
        )
    except Exception as e:
        logger.exception("get_stock_margin %s", code_n)
        return JSONResponse(
            {"success": False, "message": f"查询失败: {e}"}, status_code=500
        )


@router.get("/{code}/margin/signal")
async def get_stock_margin_signal(
    code: str,
    trade_date: Optional[str] = Query(
        None, description="信号日 YYYY-MM-DD，默认最近有数据的交易日"
    ),
    with_lhb: bool = Query(True, description="是否附带同日龙虎榜机构净额旁证"),
    db: Session = Depends(get_db),
):
    code_n = normalize_code(code)
    if not code_n:
        return JSONResponse(
            {"success": False, "message": "无效股票代码"}, status_code=400
        )
    if trade_date and not _DATE_RE.match(trade_date):
        return JSONResponse(
            {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
            status_code=400,
        )
    try:
        end = trade_date or datetime.now().strftime("%Y-%m-%d")
        start_dt = datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(days=60)
        rows = _fetch_margin_rows(
            db, code_n, start=start_dt.strftime("%Y-%m-%d"), end=end, limit=80
        )
        if not rows:
            return JSONResponse(
                {
                    "success": False,
                    "code": code_n,
                    "message": "无两融数据，请先日采/回填",
                    "disclaimer": DISCLAIMER,
                },
                status_code=404,
            )
        td = trade_date or str(rows[-1]["trade_date"])[:10]
        float_mv, mv_src = _resolve_float_mv(db, code_n, td)
        signal = _compute_signal(
            rows, trade_date=td, float_mv=float_mv, float_mv_source=mv_src
        )
        signal = _attach_extras(db, signal, with_lhb=with_lhb)
        return JSONResponse({"success": True, "code": code_n, "data": signal})
    except Exception as e:
        logger.exception("get_stock_margin_signal %s", code_n)
        return JSONResponse(
            {"success": False, "message": f"信号计算失败: {e}"}, status_code=500
        )
