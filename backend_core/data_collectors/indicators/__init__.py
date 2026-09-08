"""采集后指标日算模块。"""

from .macd_daily import run_macd_cn, run_macd_daily, run_macd_hk

__all__ = ["run_macd_daily", "run_macd_cn", "run_macd_hk"]
