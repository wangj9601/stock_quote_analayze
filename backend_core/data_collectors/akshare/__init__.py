"""
AKShare数据采集模块
提供股票行情、指数行情等数据的采集功能

子模块按需加载，避免 import 任一采集器时就预加载 akshare/pandas 全家桶。
"""

__all__ = [
    "AKShareCollector",
    "AkshareRealtimeQuoteCollector",
    "HistoricalQuoteCollector",
    "HistoricalTurnoverRateCollector",
    "IndexQuoteCollector",
    "RealtimeIndexSpotAkCollector",
]

_LAZY_ATTRS = {
    "AKShareCollector": (".base", "AKShareCollector"),
    "AkshareRealtimeQuoteCollector": (".realtime", "AkshareRealtimeQuoteCollector"),
    "HistoricalQuoteCollector": (".historical", "HistoricalQuoteCollector"),
    "HistoricalTurnoverRateCollector": (
        ".historical_turnover_rate",
        "HistoricalTurnoverRateCollector",
    ),
    "IndexQuoteCollector": (".index", "IndexQuoteCollector"),
    "RealtimeIndexSpotAkCollector": (
        ".realtime_index_spot_ak",
        "RealtimeIndexSpotAkCollector",
    ),
}


def __getattr__(name: str):
    spec = _LAZY_ATTRS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    mod_name, attr = spec
    mod = import_module(mod_name, __name__)
    val = getattr(mod, attr)
    globals()[name] = val
    return val
