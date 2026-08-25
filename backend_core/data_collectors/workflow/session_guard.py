"""休市判定（从 data_collectors.main 抽出，供流程引擎与定时任务复用）。"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def cn_session_closed_today() -> bool:
    """A 股侧今日是否休市：周六日或 trading_calendar(CN)。查询失败时不跳过。"""
    try:
        from backend_api.database import SessionLocal
        from backend_api.utils.trading_calendar_utils import is_market_session_closed

        session = SessionLocal()
        try:
            return is_market_session_closed(session, "CN", datetime.now().date())
        finally:
            session.close()
    except Exception as e:
        logger.warning("A股休市判定异常，不跳过采集: %s", e)
        return False


def hk_session_closed_today() -> bool:
    """港股侧今日是否休市：周六日或 trading_calendar(HK)。查询失败时不跳过。"""
    try:
        from backend_api.database import SessionLocal
        from backend_api.utils.trading_calendar_utils import is_market_session_closed

        session = SessionLocal()
        try:
            return is_market_session_closed(session, "HK", datetime.now().date())
        finally:
            session.close()
    except Exception as e:
        logger.warning("港股休市判定异常，不跳过采集: %s", e)
        return False


def should_skip_for_holiday(skip_on_holiday: str) -> tuple[bool, str]:
    """
    根据流程级 skip_on_holiday 策略判断是否整条跳过。
    skip_on_holiday: CN | HK | BOTH | NONE
    """
    policy = (skip_on_holiday or "NONE").upper()
    if policy == "NONE" or not policy:
        return False, ""
    if policy == "CN":
        if cn_session_closed_today():
            return True, "A股休市，跳过流程"
        return False, ""
    if policy == "HK":
        if hk_session_closed_today():
            return True, "港股休市，跳过流程"
        return False, ""
    if policy == "BOTH":
        cn_closed = cn_session_closed_today()
        hk_closed = hk_session_closed_today()
        if cn_closed and hk_closed:
            return True, "A股与港股均休市，跳过流程"
        return False, ""
    return False, ""
