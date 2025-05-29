"""
AKShare数据采集模块
提供股票行情、指数行情等数据的采集功能
"""

from .base import AKShareCollector
from .realtime import RealtimeQuoteCollector
from .historical import HistoricalQuoteCollector
from .index import IndexQuoteCollector

__all__ = [
    'AKShareCollector',
    'RealtimeQuoteCollector',
    'HistoricalQuoteCollector',
    'IndexQuoteCollector'
] 