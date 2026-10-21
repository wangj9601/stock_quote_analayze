# -*- coding: utf-8 -*-
"""BVF 底部放量分型 detector 单元测试。"""

from backend_core.strategies.bvf.detector import detect_bottom_volume_fractal


def _bar(date: str, high: float, low: float, close: float, volume: float, open_=None):
    return {
        "date": date,
        "open": open_ if open_ is not None else close,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _d(i: int) -> str:
    """从 2024-01-01 起按日历日编号（仅作合成日期，不要求交易日）。"""
    from datetime import date, timedelta

    return (date(2024, 1, 1) + timedelta(days=i)).isoformat()


def _build_series(
    *,
    n_before: int = 60,
    base: float = 10.0,
    mid_vol: float = 3e6,
    avg_vol: float = 1e6,
    mid_low: float = 9.0,
    bottom_floor: float = 9.0,
):
    """前 n_before 根平稳，最后三根构成底分型；中 K 低点=mid_low。"""
    bars = []
    for i in range(n_before):
        # 窗口内埋一个接近底部的低点，其余略高
        lo = bottom_floor if i == n_before // 2 else bottom_floor + 0.5
        hi = lo + 0.8
        bars.append(_bar(_d(i), hi, lo, (hi + lo) / 2, avg_vol))
    i0 = n_before
    bars.append(_bar(_d(i0), base + 1.0, base + 0.2, base + 0.5, avg_vol))
    bars.append(_bar(_d(i0 + 1), base + 0.3, mid_low, base, mid_vol))
    bars.append(_bar(_d(i0 + 2), base + 1.2, base + 0.4, base + 0.8, avg_vol))
    return bars


def test_hit_default_bottom_and_volume():
    bars = _build_series(mid_low=9.0, bottom_floor=9.0, mid_vol=3e6, avg_vol=1e6)
    hit = detect_bottom_volume_fractal(bars)
    assert hit is not None
    assert hit["right_date"] == bars[-1]["date"]
    assert hit["mid_date"] == bars[-2]["date"]
    assert hit["left_date"] == bars[-3]["date"]
    assert hit["vol_ratio_actual"] >= 2.0
    assert hit["bottom_dev_pct"] <= 0.03


def test_reject_not_fractal_high():
    bars = _build_series()
    # 破坏中高 < 右高
    bars[-1]["high"] = bars[-2]["high"] - 0.01
    assert detect_bottom_volume_fractal(bars) is None


def test_reject_not_near_bottom():
    # 中低远高于窗口最低
    bars = _build_series(mid_low=12.0, bottom_floor=9.0, base=12.5)
    # 修正左右使分型仍成立
    bars[-3] = _bar("2025-03-01", 13.5, 12.5, 13.0, 1e6)
    bars[-2] = _bar("2025-03-02", 12.8, 12.0, 12.2, 3e6)
    bars[-1] = _bar("2025-03-03", 13.8, 12.6, 13.2, 1e6)
    assert detect_bottom_volume_fractal(bars) is None


def test_reject_insufficient_volume():
    bars = _build_series(mid_vol=1.5e6, avg_vol=1e6)  # 仅 1.5x < 2.0
    assert detect_bottom_volume_fractal(bars) is None


def test_reject_when_right_not_last_of_window_cfg_require():
    """默认只看最后三根；序列不足底部回看也应失败。"""
    bars = _build_series(n_before=10)
    assert detect_bottom_volume_fractal(bars) is None
