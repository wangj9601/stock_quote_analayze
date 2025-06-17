"""
AKShare数据采集模块
提供股票行情、指数行情等数据的采集功能
"""

from .base import AKShareCollector
from .realtime import AkshareRealtimeQuoteCollector
from .historical import HistoricalQuoteCollector
from .index import IndexQuoteCollector
from .realtime_index_spot_ak import RealtimeIndexSpotAkCollector

__all__ = [
    'AKShareCollector',
    'AkshareRealtimeQuoteCollector',
    'HistoricalQuoteCollector',
    'IndexQuoteCollector',
    'RealtimeIndexSpotAkCollector'
] 