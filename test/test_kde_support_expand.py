"""KDE 支撑缺失时按 250 日递推扩窗（上限 750≈3 年）。"""

from backend_core.strategies.rpe.kde_levels import (
    extract_kde_levels,
    extract_kde_levels_expand_support,
)


def test_expand_support_extends_when_short_window_has_no_support():
    """近 250 日全在高位附近无下方峰；更早有明显低位堆量峰，扩窗后应找到支撑。"""
    # 早期：大量成交堆在 10 元附近
    early_closes = [10.0 + (i % 3) * 0.05 for i in range(400)]
    early_vols = [2_000_000.0] * 400
    # 近端：价格抬到 20 附近且波动很小，250 窗内往往无「下方」峰
    recent_closes = [20.0 + (i % 2) * 0.02 for i in range(250)]
    recent_vols = [800_000.0] * 250
    closes = early_closes + recent_closes
    volumes = early_vols + recent_vols
    price = 20.0

    short = extract_kde_levels(closes[-250:], volumes[-250:], base_factor=1.0)
    short_supports = [p for p in (short.get("all_peaks") or []) if p < price]

    expanded = extract_kde_levels_expand_support(
        closes,
        volumes,
        price=price,
        initial_lookback=250,
        step=250,
        max_lookback=750,
        base_factor=1.0,
    )

    assert expanded.get("ok") is True
    assert expanded.get("lookback_used", 0) >= 250
    # 若短窗已有支撑则不必扩；否则必须扩窗并找到支撑
    if not short_supports:
        assert expanded.get("lookback_expanded") is True
        assert expanded.get("lookback_used", 0) > 250
        assert any(s < price for s in (expanded.get("support_levels") or []))


def test_expand_caps_at_max_lookback():
    closes = [15.0 + (i % 5) * 0.1 for i in range(2000)]
    volumes = [1_000_000.0] * len(closes)
    out = extract_kde_levels_expand_support(
        closes,
        volumes,
        price=float(closes[-1]),
        initial_lookback=250,
        step=250,
        max_lookback=750,
    )
    assert out.get("lookback_used", 0) <= 750


def test_key_levels_expand_fields():
    from stock.stock_analysis import KeyLevels

    bars = []
    for i in range(500):
        px = 10.0 if i < 300 else 18.0
        bars.append({"close": px + (i % 2) * 0.05, "volume": 1_500_000})
    out = KeyLevels.calculate_key_levels(bars, 18.0)
    assert "kde_lookback_used" in out
    assert "kde_lookback_expanded" in out
    assert out["kde_lookback_used"] <= KeyLevels.KDE_LOOKBACK_MAX
