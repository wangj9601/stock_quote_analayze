"""个股详情关键价位：与 RPE 成交量加权 KDE 同口径。"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from backend_core.strategies.rpe.kde_levels import extract_kde_levels  # noqa: E402
from stock.stock_analysis import KeyLevels  # noqa: E402


def _fake_bars(n=80, seed=7):
    random.seed(seed)
    bars = []
    px = 15.0
    for i in range(n):
        # 在 13 / 15 / 17 附近堆量，便于形成密度峰
        cluster = [13.0, 15.0, 17.0][i % 3]
        px = cluster + random.uniform(-0.15, 0.15)
        bars.append(
            {
                "close": round(px, 2),
                "volume": 1_000_000 + (i % 3) * 500_000,
                "high": round(px + 0.2, 2),
                "low": round(px - 0.2, 2),
            }
        )
    return bars


def test_key_levels_uses_kde_peaks():
    bars = _fake_bars()
    current = 15.0
    kde = extract_kde_levels(
        [b["close"] for b in bars],
        [b["volume"] for b in bars],
        base_factor=1.0,
    )
    out = KeyLevels.calculate_key_levels(bars, current)

    assert out["method"] == "kde_volume_weighted"
    assert out["kde_ok"] is True
    assert all(r > current for r in out["resistance_levels"])
    assert all(s < current for s in out["support_levels"])
    assert out["resistance_levels"] == sorted(out["resistance_levels"])
    assert out["support_levels"] == sorted(out["support_levels"], reverse=True)
    assert len(out["resistance_levels"]) <= 3
    assert len(out["support_levels"]) <= 3

    # 与 RPE 峰划分一致（按当前价）
    peaks = kde.get("all_peaks") or []
    expect_r = sorted([round(p, 2) for p in peaks if p > current])[:3]
    expect_s = sorted([round(p, 2) for p in peaks if 0 < p < current], reverse=True)[:3]
    assert out["resistance_levels"] == expect_r
    assert out["support_levels"] == expect_s


def test_key_levels_insufficient_samples():
    out = KeyLevels.calculate_key_levels([{"close": 10, "volume": 1}] * 10, 10.0)
    assert out["resistance_levels"] == []
    assert out["support_levels"] == []
    assert out["kde_ok"] is False
