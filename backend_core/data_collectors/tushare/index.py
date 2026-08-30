"""Tushare 指数行情采集器（兼容旧入口，委托 index_daily）。"""

from typing import Any, Dict, Optional

from .index_daily import IndexDailyCollector, run_index_daily_collect


class IndexQuoteCollector(IndexDailyCollector):
    """指数行情采集器（写入 index_historical_quotes）。"""

    def collect_index_quotes(self, **kwargs: Any) -> Dict[str, Any]:
        return self.collect(**kwargs)


def collect_index_quotes(**kwargs: Any) -> Dict[str, Any]:
    return run_index_daily_collect(**kwargs)
