"""
GMS 策略观察股表（gms_strategy_version_stocks）同步：交易观察加入时补全观察股池。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend_api.models import (
    GMSStrategyVersion,
    GMSStrategyVersionStock,
    StockBasicInfo,
    StockBasicInfoHK,
)

logger = logging.getLogger(__name__)

DEFAULT_REMARK = "交易观察自动加入"
BOARD_ROLE_REMARK = "分析频道·板块龙头/中军"


@dataclass
class WatchlistAddResult:
    """单只加入结果。"""

    code: str
    market: str
    name: str
    status: str  # added | skipped | failed
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "market": self.market,
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


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


def add_gms_strategy_watchlist_stock(
    db: Session,
    *,
    market: str,
    code: str,
    name: Optional[str] = None,
    remark: str = DEFAULT_REMARK,
    version: Optional[GMSStrategyVersion] = None,
) -> WatchlistAddResult:
    """
    将股票写入主启用策略版本观察股池（未 commit，由调用方统一提交）。
    status: added / skipped / failed。
    """
    wl_market = _watchlist_market(market)
    wl_code = _watchlist_code(wl_market, code)
    display_name = (name or "").strip() or wl_code
    if not wl_code:
        logger.warning("GMS 观察股同步跳过：代码无效 market=%s code=%s", market, code)
        return WatchlistAddResult(
            code=str(code or "").strip(),
            market=wl_market,
            name=display_name,
            status="failed",
            message="股票代码无效",
        )

    ver = version or _resolve_primary_active_version(db)
    if not ver:
        logger.warning("GMS 观察股同步跳过：无启用的策略版本")
        return WatchlistAddResult(
            code=wl_code,
            market=wl_market,
            name=display_name,
            status="failed",
            message="无启用的 GMS 策略版本",
        )

    already = (
        db.query(GMSStrategyVersionStock.id)
        .filter(
            GMSStrategyVersionStock.version_id == int(ver.id),
            GMSStrategyVersionStock.market == wl_market,
            GMSStrategyVersionStock.stock_code == wl_code,
        )
        .first()
    )
    if already or is_in_gms_strategy_watchlist(db, market=market, code=code):
        return WatchlistAddResult(
            code=wl_code,
            market=wl_market,
            name=display_name,
            status="skipped",
            message="已在 GMS 策略观察股中",
        )

    stock_name = display_name if (name or "").strip() else (
        _lookup_stock_name(db, wl_market, wl_code) or wl_code
    )
    row = GMSStrategyVersionStock(
        version_id=int(ver.id),
        market=wl_market,
        stock_code=wl_code,
        stock_name=stock_name,
        sort_order=0,
        status="active",
        is_verified=False,
        remark=remark or DEFAULT_REMARK,
    )
    db.add(row)
    logger.info(
        "GMS 观察股同步：version_id=%s %s %s (%s)",
        ver.id,
        wl_market,
        wl_code,
        stock_name,
    )
    return WatchlistAddResult(
        code=wl_code,
        market=wl_market,
        name=stock_name,
        status="added",
        message="已加入 GMS 策略观察股",
    )


def ensure_gms_strategy_watchlist_stock(
    db: Session,
    *,
    market: str,
    code: str,
    name: Optional[str] = None,
    remark: str = DEFAULT_REMARK,
) -> bool:
    """
    若该股不在 GMS 策略观察股表中，则写入主启用策略版本。
    返回 True 表示本次新写入（未 commit，由调用方统一提交）。
    """
    result = add_gms_strategy_watchlist_stock(
        db, market=market, code=code, name=name, remark=remark
    )
    return result.status == "added"


def add_gms_strategy_watchlist_stocks_batch(
    db: Session,
    stocks: Iterable[Dict[str, Any]],
    *,
    remark: str = BOARD_ROLE_REMARK,
) -> Dict[str, Any]:
    """
    批量写入主启用策略版本观察股。未 commit。
    stocks 项：{code, name?, market?}
    """
    version = _resolve_primary_active_version(db)
    results: List[WatchlistAddResult] = []
    seen: set = set()

    for raw in stocks:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or raw.get("stock_code") or "").strip()
        market = str(raw.get("market") or "CN").strip() or "CN"
        name = raw.get("name") or raw.get("stock_name")
        wl_market = _watchlist_market(market)
        wl_code = _watchlist_code(wl_market, code)
        dedupe_key = (wl_market, wl_code)
        if wl_code and dedupe_key in seen:
            results.append(
                WatchlistAddResult(
                    code=wl_code,
                    market=wl_market,
                    name=(str(name).strip() if name else wl_code),
                    status="skipped",
                    message="本批次内重复",
                )
            )
            continue
        if wl_code:
            seen.add(dedupe_key)
        results.append(
            add_gms_strategy_watchlist_stock(
                db,
                market=market,
                code=code,
                name=name,
                remark=remark,
                version=version,
            )
        )

    added = sum(1 for r in results if r.status == "added")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    return {
        "added": added,
        "skipped": skipped,
        "failed": failed,
        "total": len(results),
        "items": [r.to_dict() for r in results],
        "version_id": int(version.id) if version else None,
    }
