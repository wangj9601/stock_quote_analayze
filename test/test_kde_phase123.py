"""KDE 三期：多窗共振源、ZigZag 结构锚窗、时间衰减。"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from backend_core.analysis.confluence_zones import collect_candidate_points  # noqa: E402
from backend_core.strategies.rpe.kde_levels import (  # noqa: E402
    KDE_MULTI_WINDOWS,
    KDE_TIME_DECAY_AUTO_MIN_BARS,
    compute_kde_bundle,
    extract_kde_levels,
    extract_kde_levels_multi_window,
    resolve_kde_structural_lookback,
)
from stock.stock_analysis import KeyLevels  # noqa: E402


def _cluster_closes(n: int, seed: int = 3):
    random.seed(seed)
    closes, vols = [], []
    for i in range(n):
        cluster = [13.0, 15.0, 17.0][i % 3]
        closes.append(cluster + random.uniform(-0.12, 0.12))
        vols.append(1_000_000.0 + (i % 3) * 400_000)
    return closes, vols


def _zigzag_friendly_bars(n: int = 160):
    """构造可被 fractal ZigZag 识别的波段 OHLC（升序）。"""
    bars = []
    # 先下行再上行，形成明确 swing
    for i in range(n):
        if i < 40:
            mid = 20.0 - i * 0.15
        elif i < 90:
            mid = 14.0 + (i - 40) * 0.18
        else:
            mid = 23.0 - (i - 90) * 0.05
        bars.append(
            {
                "date": f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                "open": round(mid, 2),
                "high": round(mid + 0.35, 2),
                "low": round(mid - 0.35, 2),
                "close": round(mid + (0.05 if i % 2 == 0 else -0.05), 2),
                "volume": 1_200_000 + i * 1000,
            }
        )
    return bars


def test_multi_window_extract_has_60_120_250():
    closes, vols = _cluster_closes(300)
    mw = extract_kde_levels_multi_window(closes, vols, price=15.0)
    assert mw["ok"] is True
    wins = mw["windows"]
    for w in KDE_MULTI_WINDOWS:
        assert str(w) in wins
        assert wins[str(w)]["lookback"] == w
        assert "weight" in wins[str(w)]


def test_multi_window_feeds_confluence_sources():
    closes, vols = _cluster_closes(260)
    mw = extract_kde_levels_multi_window(closes, vols, price=15.0)
    pts = collect_candidate_points(
        kde_support=14.0,
        kde_resistance=16.0,
        kde_multi_windows=mw,
    )
    sources = {p["source"] for p in pts}
    assert "kde" in sources
    assert "kde_60" in sources or "kde_120" in sources or "kde_250" in sources


def test_time_decay_auto_on_long_sample():
    closes, vols = _cluster_closes(KDE_TIME_DECAY_AUTO_MIN_BARS + 20)
    on = extract_kde_levels(closes, vols, time_decay=None)
    off = extract_kde_levels(closes, vols, time_decay=False)
    assert on["time_decay"] is True
    assert off["time_decay"] is False
    # 衰减后密度峰集合允许不同，但两者都应成功
    assert on["ok"] and off["ok"]


def test_time_decay_off_short_sample():
    closes, vols = _cluster_closes(80)
    out = extract_kde_levels(closes, vols, time_decay=None)
    assert out["time_decay"] is False


def test_structural_lookback_resolves_or_fallback():
    bars = _zigzag_friendly_bars()
    meta = resolve_kde_structural_lookback(bars, calendar_fallback=60)
    assert meta["lookback"] >= 40
    assert meta["lookback"] <= 750
    if meta["ok"]:
        assert meta["method"] == "zigzag_fractal"
        assert meta["anchor_index"] is not None
    else:
        assert meta["method"] == "calendar_fallback"


def test_compute_kde_bundle_structural_and_multi():
    bars = _zigzag_friendly_bars(200)
    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]
    bundle = compute_kde_bundle(
        closes,
        vols,
        price=closes[-1],
        bars=bars,
        initial_lookback=None,
        structural=True,
        multi_window=True,
        calendar_fallback=60,
    )
    assert bundle["main"]["ok"] is True
    assert bundle["multi_windows"] is not None
    assert bundle["multi_windows"]["ok"] is True
    assert int(bundle["initial_lookback"]) >= 40


def test_key_levels_default_exposes_phase_fields():
    bars = _zigzag_friendly_bars(180)
    out = KeyLevels.calculate_key_levels(bars, float(bars[-1]["close"]), max_levels=4)
    assert "kde_multi_windows" in out
    assert out["kde_multi_windows"] is not None
    assert "kde_anchor" in out
    assert out.get("kde_window_mode") in ("structural", "calendar")


def test_key_levels_forced_calendar_disables_structural():
    bars = _zigzag_friendly_bars(180)
    out = KeyLevels.calculate_key_levels(
        bars,
        float(bars[-1]["close"]),
        initial_lookback=60,
        use_structural_window=False,
        max_levels=4,
    )
    assert out["kde_lookback_initial"] == 60
    assert out["kde_window_mode"] == "calendar"


def test_time_decay_weight_math():
    """最近一根衰减因子应为 1，更早根更小。"""
    hl = 40.0
    lam = math.log(2.0) / hl
    n = 5
    factors = [math.exp(-lam * (n - 1 - i)) for i in range(n)]
    assert abs(factors[-1] - 1.0) < 1e-12
    assert factors[0] < factors[-1]
