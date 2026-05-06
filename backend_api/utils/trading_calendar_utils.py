"""
交易日与节假日工具：结合周六日及 trading_calendar 表（按市场 CN / HK 区分）。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import AbstractSet, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from backend_api.models import TradingCalendar

logger = logging.getLogger(__name__)


def is_weekend(d: date) -> bool:
    """是否为周六、周日（weekday: 周一=0 … 周日=6）。"""
    return d.weekday() >= 5


def is_market_holiday_on_date(db: Session, market: str, d: date) -> bool:
    """
    trading_calendar 中是否将该日登记为指定市场的节假日（不区分是否周末）。
    market: CN 或 HK。
    """
    m = (market or "").strip().upper()
    if m not in ("CN", "HK"):
        m = "CN"
    try:
        return (
            db.query(TradingCalendar)
            .filter(
                TradingCalendar.market == m,
                TradingCalendar.holiday_date == d,
            )
            .first()
        ) is not None
    except Exception as e:
        logger.warning(
            "查询 trading_calendar 失败，节假日判定按否处理: market=%s date=%s err=%s",
            m,
            d,
            e,
        )
        return False


def is_market_session_closed(db: Session, market: str, d: date) -> bool:
    """
    该市场当日是否休市：周六日，或 trading_calendar 中该 market 有节假日记录。
    """
    if is_weekend(d):
        return True
    return is_market_holiday_on_date(db, market, d)


def is_holiday_in_trading_calendar(db: Session, d: date) -> bool:
    """
    当日是否在 trading_calendar 中配置为节假日（任一人市场有一条记录即视为休市日）。
    用于粗粒度场景；GMS 推送请用 should_skip_gms_scheduled_notification 并按自选市场区分。
    """
    try:
        return (
            db.query(TradingCalendar)
            .filter(TradingCalendar.holiday_date == d)
            .first()
        ) is not None
    except Exception as e:
        logger.warning(
            "查询 trading_calendar 失败，节假日判定按否处理: date=%s err=%s",
            d,
            e,
        )
        return False


def _normalize_watchlist_markets(markets: Optional[Iterable[str]]) -> Tuple[bool, bool]:
    """
    从自选股 market 集合解析是否需要 A 股侧(CN/ETF)与港股侧(HK)交易日。
    ETF 在大陆上市交易，跟随 A 股交易日历（CN）。
    """
    if not markets:
        return False, False
    mset = {(x or "").strip().upper() for x in markets}
    needs_cn = any(x in ("CN", "ETF") for x in mset)
    needs_hk = "HK" in mset
    return needs_cn, needs_hk


def should_skip_gms_scheduled_notification(
    db: Session,
    d: date,
    watchlist_markets: Optional[AbstractSet[str]] = None,
) -> Tuple[bool, str]:
    """
    GMS 定时通知（gms_daily）是否跳过：按自选股涉及的交易场所分别判断。

    - 仅 A 股/ETF：只看 CN 日历；若仅有港股持仓则只看 HK 日历。
    - 同时含 A 股与港股：只要任一侧仍为交易日即不跳过（例如 A 股放假、港股仍交易时会继续推送）。
    - 无自选股集合时不因日历跳过（空列表交由后续无数据逻辑）。

    参数 watchlist_markets 为自选股项上的 market 字段去重集合，如 {\"CN\",\"HK\"}。
    """
    needs_cn, needs_hk = _normalize_watchlist_markets(watchlist_markets)
    if not needs_cn and not needs_hk:
        return False, ""

    cn_closed = is_market_session_closed(db, "CN", d)
    hk_closed = is_market_session_closed(db, "HK", d)

    can_trade_cn = needs_cn and not cn_closed
    can_trade_hk = needs_hk and not hk_closed
    if can_trade_cn or can_trade_hk:
        return False, ""

    if needs_cn and needs_hk:
        return True, "A股与港股均为休市日"
    if needs_cn:
        return True, "A股休市(周末或trading_calendar·CN)"
    return True, "港股休市(周末或trading_calendar·HK)"
