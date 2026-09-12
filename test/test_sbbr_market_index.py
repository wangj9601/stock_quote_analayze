# -*- coding: utf-8 -*-
"""SBBR 大盘序列应读上证指数表，而非个股 000001。"""

from backend_core.strategies.sbbr.data_loader import (
    SBBRDataLoader,
    normalize_index_ts_code,
)


def test_normalize_index_ts_code():
    assert normalize_index_ts_code("000001") == "000001.SH"
    assert normalize_index_ts_code("sh000001") == "000001.SH"
    assert normalize_index_ts_code("000001.SH") == "000001.SH"


def test_load_market_returns_uses_shanghai_index():
    loader = SBBRDataLoader()
    bars = loader.load_index_bars("000001.SH", end_date="2026-09-11", limit=10)
    assert len(bars) >= 2
    # 上证点位量级，绝不是平安银行 ~10 元
    assert bars[-1]["close"] > 1000
    rets = loader.load_market_returns(end_date="2026-09-11", lookback=8)
    assert len(rets) >= 1
    # 兼容旧默认入参 000001 → 仍映射到上证
    bars2 = loader.load_index_bars("000001", end_date="2026-09-11", limit=5)
    assert bars2 and bars2[-1]["close"] > 1000
