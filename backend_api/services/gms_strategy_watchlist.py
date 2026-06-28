"""
GMS 策略观察股表（gms_strategy_version_stocks）同步：交易观察加入时补全观察股池。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend_api.models import (
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockBasicInfo,
    StockBasicInfoHK,
)

logger = logging.getLogger(__name__)


def _watchlist_market(market: str) -> str:
    m = (market or "").strip().upper()
    if m in ("CN", "A", "A股"):
        return "A"
    if m in ("HK", "H", "港股"):
        return "HK"
    return "A"


def _watchlist_code(market: str, code: str) -> str:
    c = str(code or "").strip().upper().replace("SZ", "").replace("SH", "")
    if market == "A":
        digits = "".join(ch for ch in c if ch.isdigit())
        return digits.zfill(6) if digits else ""
    digits = "".join(ch for ch in c if ch.isdigit())
    return digits.zfill(5) if digits else c


def _lookup_stock_name(db: Session, market: str, code: str) -> str:
    if market == "A":
        row = db.query(StockBasicInfo.name).filter(StockBasicInfo.code == code).first()
        if row and row[0]:
            return str(row[0]).strip()
        return ""
    row = db.query(StockBasicInfoHK.name).filter(StockBasicInfoHK.code == code).first()
    if row and row[0]:
        return str(row[0]).strip()
    return ""


def _resolve_primary_active_version(db: Session) -> Optional[GMSStrategyVersion]:
    return (
        db.query(GMSStrategyVersion)
        .filter(GMSStrategyVersion.is_active.is_(True))
        .order_by(GMSStrategyVersion.id.asc())
        .first()
    )


def is_in_gms_strategy_watchlist(db: Session, *, market: str, code: str) -> bool:
    """是否已存在于任一启用策略版本的 active 观察股中。"""
    wl_market = _watchlist_market(market)
    wl_code = _watchlist_code(wl_market, code)
    if not wl_code:
        return False
    row = (
        db.query(GMSStrategyVersionStock.id)
        .join(GMSStrategyVersion, GMSStrategyVersion.id == GMSStrategyVersionStock.version_id)
        .filter(
            GMSStrategyVersion.is_active.is_(True),
            GMSStrategyVersionStock.market == wl_market,
            GMSStrategyVersionStock.stock_code == wl_code,
            func.lower(func.trim(func.coalesce(GMSStrategyVersionStock.status, ""))) == "active",
        )
        .first()
    )
    return row is not None


def ensure_gms_strategy_watchlist_stock(
    db: Session,
    *,
    market: str,
    code: str,
    name: Optional[str] = None,
    remark: str = "交易观察自动加入",
) -> bool:
    """
    若该股不在 GMS 策略观察股表中，则写入主启用策略版本。
    返回 True 表示本次新写入（未 commit，由调用方统一提交）。
    """
    wl_market = _watchlist_market(market)
    wl_code = _watchlist_code(wl_market, code)
    if not wl_code:
        logger.warning("GMS 观察股同步跳过：代码无效 market=%s code=%s", market, code)
        return False

    version = _resolve_primary_active_version(db)
    if not version:
        logger.warning("GMS 观察股同步跳过：无启用的策略版本")
        return False

    already = (
        db.query(GMSStrategyVersionStock.id)
        .filter(
            GMSStrategyVersionStock.version_id == int(version.id),
            GMSStrategyVersionStock.market == wl_market,
            GMSStrategyVersionStock.stock_code == wl_code,
        )
        .first()
    )
    if already or is_in_gms_strategy_watchlist(db, market=market, code=code):
        return False

    stock_name = (name or "").strip() or _lookup_stock_name(db, wl_market, wl_code) or wl_code
    row = GMSStrategyVersionStock(
        version_id=int(version.id),
        market=wl_market,
        stock_code=wl_code,
        stock_name=stock_name,
        sort_order=0,
        status="active",
        is_verified=False,
        remark=remark,
    )
    db.add(row)
    logger.info(
        "GMS 观察股同步：version_id=%s %s %s (%s)",
        version.id,
        wl_market,
        wl_code,
        stock_name,
    )
    return True
