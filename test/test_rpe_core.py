"""RPE 核心算法单测。"""

from backend_core.strategies.rpe.config import get_default_rpe_config
from backend_core.strategies.rpe.filters import liquidity_ok, structure_break, structure_filter, trend_veto
from backend_core.strategies.rpe.kde_levels import extract_kde_levels, nearest_levels
from backend_core.strategies.rpe.sector_benchmark import compute_vwap_benchmark, linear_slope, sector_slope
from backend_core.strategies.rpe.signal_detector import detect_signal
from backend_core.strategies.rpe.zscore import latest_zscore, relative_ratio_series, rolling_zscore


def test_vwap_benchmark():
    dm = {
        "2024-01-01": [(10.0, 100.0), (20.0, 100.0)],
        "2024-01-02": [(12.0, 50.0), (18.0, 150.0)],
    }
    bm = compute_vwap_benchmark(dm)
    assert len(bm) == 2
    assert abs(bm[0]["i_t"] - 15.0) < 1e-6


def test_linear_slope_up():
    s = linear_slope([1, 2, 3, 4, 5, 6, 7, 8])
    assert s is not None and s > 0


def test_rolling_zscore_and_latest():
    vals = [1.0] * 30 + [3.0]
    zs = rolling_zscore(vals, 20)
    assert zs[-1] is not None and zs[-1] > 0

    closes = {f"2024-01-{i+1:02d}": 10 + i * 0.01 for i in range(50)}
    # pad dates beyond month for simplicity using sequential keys sorted
    closes = {f"2024-02-{i+1:02d}" if i < 28 else f"2024-03-{i-27:02d}": 10 + (i % 5) * 0.1 for i in range(50)}
    bm = [{"date": d, "i_t": 10.0, "volume_sum": 1} for d in sorted(closes.keys())]
    # make last ratio low -> catch up
    last = sorted(closes.keys())[-1]
    closes[last] = 8.0
    info = latest_zscore(closes, bm, 20)
    assert info is not None
    assert "z_score" in info


def test_kde_levels_basic():
    import random

    random.seed(1)
    closes = [10 + random.random() for _ in range(40)] + [9.0] * 20 + [11.0] * 20
    volumes = [100 + random.random() * 50 for _ in closes]
    res = extract_kde_levels(closes, volumes, base_factor=1.0)
    assert res.get("ok") is True
    assert "support_levels" in res
    assert "resistance_levels" in res
    near = nearest_levels(closes[-1], res["support_levels"], res["resistance_levels"])
    assert "nearest_support" in near


def test_kde_histogram_fallback_without_scipy(monkeypatch):
    import builtins
    import random

    random.seed(2)
    closes = [10 + random.random() for _ in range(30)] + [8.5] * 25 + [12.0] * 25 + [10.1]
    volumes = [80 + random.random() * 40 for _ in closes]

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "scipy" or name.startswith("scipy."):
            raise ImportError("scipy disabled for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    res = extract_kde_levels(closes, volumes, base_factor=1.0)
    assert res.get("ok") is True
    assert res.get("method") == "histogram_fallback"
    assert res.get("reason") == "ok_histogram_fallback"
    # 至少一侧应能给出峰位（取决于现价位置）
    assert (res.get("support_levels") or res.get("resistance_levels"))


def test_filters_and_signal():
    assert trend_veto(-0.01, True) is True
    assert trend_veto(0.01, True) is False
    st = structure_filter(10.0, 9.0, 12.0, min_rr=1.5)
    assert st["structure_valid"] is True
    assert structure_break(8.9, 9.0) is True
    bars = [{"amount": 8_000_000, "turnover_rate": 1.0} for _ in range(20)]
    # 未传板别时沿用传入/默认 min_avg_amount=500万
    assert liquidity_ok(bars)["liquidity_ok"] is True
    cfg = get_default_rpe_config()
    sig = detect_signal(
        z_score=-2.0,
        sector_slope=0.01,
        structure_valid=True,
        liquidity_ok=True,
        config=cfg,
    )
    assert sig["signal_type"] == "catch_up"
    assert sig["entry_signal"] is True
