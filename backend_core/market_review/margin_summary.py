# -*- coding: utf-8 -*-
"""复盘用：全市场两融日汇总（公开披露 T+1，旁证非爆仓实锤）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "旁证基于公开两融余额/净偿还推断，不能证明某家机构账户被券商强平。"
)


def _safe(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def resolve_margin_trade_date(db: Session, trade_date: Optional[str] = None) -> Optional[str]:
    """解析可用披露日：优先指定日，否则 MAX(trade_date)。"""
    d = (trade_date or "")[:10]
    if d:
        try:
            n = db.execute(
                text(
                    "SELECT 1 FROM stock_margin_daily WHERE trade_date = :d LIMIT 1"
                ),
                {"d": d},
            ).scalar()
            if n:
                return d
        except Exception:
            logger.exception("两融披露日检查失败 %s", d)
            db.rollback()
    try:
        latest = db.execute(
            text("SELECT MAX(trade_date) FROM stock_margin_daily")
        ).scalar()
        return str(latest)[:10] if latest else None
    except Exception:
        logger.exception("两融最新披露日查询失败")
        db.rollback()
        return None


def compute_margin_market_summary(
    db: Session, trade_date: Optional[str] = None, *, top_n: int = 5
) -> Dict[str, Any]:
    """全市场融资余额合计、日环比、净买入前几名。单位：元。"""
    d = resolve_margin_trade_date(db, trade_date)
    if not d:
        return {
            "available": False,
            "trade_date": trade_date,
            "disclaimer": DISCLAIMER,
            "error": "无两融数据",
        }

    try:
        agg = db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS stock_count,
                    COALESCE(SUM(rzye), 0) AS rzye_sum,
                    COALESCE(SUM(rzmre), 0) AS rzmre_sum,
                    COALESCE(SUM(rzche), 0) AS rzche_sum,
                    COALESCE(SUM(rqye), 0) AS rqye_sum,
                    COALESCE(SUM(rzrqye), 0) AS rzrqye_sum
                FROM stock_margin_daily
                WHERE trade_date = :d
                """
            ),
            {"d": d},
        ).mappings().first()
    except Exception:
        logger.exception("两融市场汇总失败 %s", d)
        db.rollback()
        return {
            "available": False,
            "trade_date": d,
            "disclaimer": DISCLAIMER,
            "error": "两融汇总查询失败",
        }

    rzye_sum = _safe(agg.get("rzye_sum") if agg else None) or 0.0
    rzmre_sum = _safe(agg.get("rzmre_sum") if agg else None) or 0.0
    rzche_sum = _safe(agg.get("rzche_sum") if agg else None) or 0.0
    rqye_sum = _safe(agg.get("rqye_sum") if agg else None) or 0.0
    rzrqye_sum = _safe(agg.get("rzrqye_sum") if agg else None) or 0.0
    stock_count = int(agg.get("stock_count") or 0) if agg else 0
    rz_net_sum = rzmre_sum - rzche_sum

    prev_d = None
    rzye_prev = None
    rzye_delta = None
    rzye_delta_pct = None
    try:
        prev_d = db.execute(
            text(
                """
                SELECT MAX(trade_date) FROM stock_margin_daily
                WHERE trade_date < :d
                """
            ),
            {"d": d},
        ).scalar()
        if prev_d:
            prev_d = str(prev_d)[:10]
            prev_sum = db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(rzye), 0) AS rzye_sum
                    FROM stock_margin_daily WHERE trade_date = :d
                    """
                ),
                {"d": prev_d},
            ).scalar()
            rzye_prev = _safe(prev_sum)
            if rzye_prev is not None:
                rzye_delta = rzye_sum - rzye_prev
                if rzye_prev > 0:
                    rzye_delta_pct = rzye_delta / rzye_prev
    except Exception:
        logger.exception("两融环比查询失败 %s", d)
        db.rollback()

    top_buy: List[Dict[str, Any]] = []
    top_repay: List[Dict[str, Any]] = []
    try:
        buy_rows = db.execute(
            text(
                """
                SELECT code, name, rzye, rzmre, rzche,
                       (COALESCE(rzmre,0) - COALESCE(rzche,0)) AS rz_net
                FROM stock_margin_daily
                WHERE trade_date = :d
                ORDER BY (COALESCE(rzmre,0) - COALESCE(rzche,0)) DESC NULLS LAST
                LIMIT :n
                """
            ),
            {"d": d, "n": int(top_n)},
        ).mappings().all()
        top_buy = [
            {
                "code": r["code"],
                "name": r["name"],
                "rzye": _safe(r["rzye"]),
                "rz_net": _safe(r["rz_net"]),
            }
            for r in buy_rows
        ]
        repay_rows = db.execute(
            text(
                """
                SELECT code, name, rzye, rzmre, rzche,
                       (COALESCE(rzmre,0) - COALESCE(rzche,0)) AS rz_net
                FROM stock_margin_daily
                WHERE trade_date = :d
                ORDER BY (COALESCE(rzmre,0) - COALESCE(rzche,0)) ASC NULLS LAST
                LIMIT :n
                """
            ),
            {"d": d, "n": int(top_n)},
        ).mappings().all()
        top_repay = [
            {
                "code": r["code"],
                "name": r["name"],
                "rzye": _safe(r["rzye"]),
                "rz_net": _safe(r["rz_net"]),
            }
            for r in repay_rows
        ]
    except Exception:
        logger.exception("两融 Top 名单查询失败 %s", d)
        db.rollback()

    return {
        "available": stock_count > 0,
        "trade_date": d,
        "prev_trade_date": prev_d,
        "stock_count": stock_count,
        "rzye_sum": rzye_sum,
        "rzye_prev": rzye_prev,
        "rzye_delta": rzye_delta,
        "rzye_delta_pct": rzye_delta_pct,
        "rzmre_sum": rzmre_sum,
        "rzche_sum": rzche_sum,
        "rz_net_sum": rz_net_sum,
        "rqye_sum": rqye_sum,
        "rzrqye_sum": rzrqye_sum,
        "top_buy": top_buy,
        "top_repay": top_repay,
        "disclaimer": DISCLAIMER,
        "note": "交易所两融明细为 T+1 披露，复盘使用当日或最近可用披露日。",
    }
