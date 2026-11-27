"""A 股 RS 回看窗口需明显大于「刚好 253 交易日」。"""

from backend_core.indicators.rs_rating.config import (
    LOOKBACK_CALENDAR_DAYS,
    LOOKBACK_CALENDAR_DAYS_HK,
    RS_WINDOWS,
)


def test_cn_lookback_has_margin_over_min_bars():
    need_bars = max(RS_WINDOWS) + 1
    # 420 日历日近年约 254 交易日，几乎无余量；520 起才够停牌/缺数缓冲
    assert LOOKBACK_CALENDAR_DAYS >= 520
    assert LOOKBACK_CALENDAR_DAYS > need_bars
    assert LOOKBACK_CALENDAR_DAYS_HK > LOOKBACK_CALENDAR_DAYS


def test_cn_precompute_uses_coverage_allows_publish():
    import inspect

    from backend_core.indicators.rs_rating import scheduled_precompute as mod

    src = inspect.getsource(mod.run_rs_rating_precompute)
    assert "coverage_allows_publish" in src
