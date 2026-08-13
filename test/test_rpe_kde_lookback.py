"""KDE / 评估 lookback 截断口径单测。"""

from backend_core.strategies.rpe.kde_levels import extract_kde_levels, nearest_levels
from backend_core.strategies.rpe.strategy_engine import _bars_for_lookback


def test_bars_for_lookback_keeps_tail():
    bars = [{"date": f"d{i}", "close": float(i)} for i in range(500)]
    out = _bars_for_lookback(bars, 250)
    assert len(out) == 250
    assert out[0]["date"] == "d250"
    assert out[-1]["date"] == "d499"
    assert _bars_for_lookback(bars[:10], 250) == bars[:10]


def test_full_history_inflates_bw_vs_lookback_window():
    """全历史含早期低价时 raw 带宽更大；截断 lookback 后下降；clamp 后不超过 max_bw。"""
    closes = [8.0 + (i % 3) * 0.1 for i in range(2800)]
    closes += [40.0 + (i % 5) * 0.4 for i in range(200)]
    closes += [35.0] * 5
    volumes = [1_000_000.0] * len(closes)

    full = extract_kde_levels(closes, volumes, base_factor=1.0, max_bw=0.08)
    short = extract_kde_levels(closes[-250:], volumes[-250:], base_factor=1.0, max_bw=0.08)
    assert full.get("ok") and short.get("ok")
    assert float(full.get("bw_raw") or 0) > float(short.get("bw_raw") or 0)
    assert float(full["bw"]) <= 0.08 + 1e-12
    assert float(short["bw"]) <= 0.08 + 1e-12
    # 触顶后仍不低于短窗有效带宽
    assert float(full["bw"]) >= float(short["bw"]) - 1e-12


def test_clipping_matches_evaluate_lookback_helper():
    """引擎截断后的序列应与直接取末 lookback 根一致。"""
    bars = [{"date": f"2024-01-{i+1:02d}" if i < 28 else f"2024-02-{i-27:02d}", "close": 10 + i * 0.01, "volume": 1000} for i in range(40)]
    # pad to >250 with synthetic dates
    bars = [{"date": f"d{i:04d}", "close": 20 + (i % 9) * 0.1, "volume": 1e6} for i in range(300)]
    clipped = _bars_for_lookback(bars, 250)
    kde = extract_kde_levels([b["close"] for b in clipped], [b["volume"] for b in clipped], base_factor=1.0)
    assert kde.get("ok") is True
    near = nearest_levels(clipped[-1]["close"], kde.get("support_levels") or [], kde.get("resistance_levels") or [])
    assert "nearest_support" in near and "nearest_resistance" in near
