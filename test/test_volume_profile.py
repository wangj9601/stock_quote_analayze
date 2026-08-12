# -*- coding: utf-8 -*-
"""日线 Volume Profile：POC / VAH / VAL 与 KDE 对比。"""

from backend_core.analysis.volume_profile import (
    compare_vp_with_kde,
    compute_volume_profile_from_bars,
)


def _bars_clustered():
    """在 10 / 15 / 20 附近堆量，便于 POC 落在中部密集区。"""
    bars = []
    # 低区少量
    for i in range(5):
        bars.append(
            {
                "date": f"2024-01-{i+1:02d}",
                "high": 11.0,
                "low": 9.0,
                "close": 10.0,
                "volume": 100_000,
            }
        )
    # 中区大量 → 期望 POC 靠近 15
    for i in range(20):
        bars.append(
            {
                "date": f"2024-02-{i+1:02d}",
                "high": 16.0,
                "low": 14.0,
                "close": 15.0,
                "volume": 1_000_000,
            }
        )
    # 高区少量
    for i in range(5):
        bars.append(
            {
                "date": f"2024-03-{i+1:02d}",
                "high": 21.0,
                "low": 19.0,
                "close": 20.0,
                "volume": 100_000,
            }
        )
    return bars


def test_vp_poc_vah_val_basic():
    out = compute_volume_profile_from_bars(_bars_clustered(), last_close=15.0, lookback=60)
    assert out["ok"] is True
    assert out["poc"] is not None
    assert out["val"] is not None
    assert out["vah"] is not None
    assert out["val"] <= out["poc"] <= out["vah"]
    # POC 应落在中部成交密集区附近
    assert 13.5 <= out["poc"] <= 16.5
    assert out["nearest_support"] is not None or out["nearest_resistance"] is not None


def test_vp_value_area_covers_majority():
    out = compute_volume_profile_from_bars(_bars_clustered(), last_close=15.0)
    assert out["value_area_pct"] == 0.70
    assert out["total_volume"] > 0
    assert len(out["bins"]) >= 3


def test_compare_vp_with_kde_aligned():
    vp = {
        "ok": True,
        "poc": 15.0,
        "val": 14.0,
        "vah": 16.0,
        "nearest_support": 14.0,
        "nearest_resistance": 16.0,
        "last_close": 15.0,
    }
    cmp_ = compare_vp_with_kde(
        vp, kde_support=14.1, kde_resistance=16.05, price=15.0
    )
    assert cmp_["support"]["aligned"] is True
    assert cmp_["resistance"]["aligned"] is True


def test_compare_vp_with_kde_not_aligned():
    vp = {
        "ok": True,
        "poc": 15.0,
        "val": 12.0,
        "vah": 18.0,
        "nearest_support": 12.0,
        "nearest_resistance": 18.0,
        "last_close": 15.0,
    }
    cmp_ = compare_vp_with_kde(
        vp, kde_support=14.5, kde_resistance=16.0, price=15.0
    )
    assert cmp_["support"]["aligned"] is False
    assert cmp_["resistance"]["aligned"] is False


def test_compare_vp_does_not_use_vah_below_price_as_resistance():
    """现价已越过 VAH 时，压力对照不得再兜底塞入现价下方的 VAH。"""
    vp = {
        "ok": True,
        "poc": 2.90,
        "val": 2.49,
        "vah": 3.24,
        "nearest_support": 2.90,
        "nearest_resistance": None,
        "bars_used": 60,
        "last_close": 3.86,
    }
    cmp_ = compare_vp_with_kde(
        vp, kde_support=3.84, kde_resistance=4.04, price=3.86
    )
    assert cmp_["resistance"]["vp"] is None
    assert cmp_["support"]["vp"] == 2.90
    assert cmp_["resistance"].get("note")
    assert "VAH" in cmp_["resistance"]["note"]
    assert "resistance_above_vah" in cmp_["notes"]


def test_vp_resistance_note_when_above_vah():
    """现价站上 VAH 时返回 resistance_note，而非仅空压力。"""
    bars = []
    for i in range(30):
        # 价值区大致在 10～12，末根收盘拉到 20
        c = 11.0 if i < 29 else 20.0
        bars.append(
            {
                "date": f"2026-06-{(i % 28) + 1:02d}",
                "high": c + 0.5,
                "low": c - 0.5,
                "close": c,
                "volume": 1000.0,
            }
        )
    # 前 29 根集中在 10-12，末根 20
    for i in range(29):
        bars[i]["high"] = 12.0
        bars[i]["low"] = 10.0
        bars[i]["close"] = 11.0
    bars[29]["high"] = 20.5
    bars[29]["low"] = 19.5
    bars[29]["close"] = 20.0
    out = compute_volume_profile_from_bars(bars, last_close=20.0, lookback=30)
    assert out["ok"] is True
    assert out["nearest_resistance"] is None
    assert out.get("resistance_note")
    assert "VAH" in out["resistance_note"]
    assert "筹码压制" in out["resistance_note"]


def test_vp_insufficient_bars():
    out = compute_volume_profile_from_bars(
        [{"high": 1, "low": 1, "close": 1, "volume": 1}] * 3,
        last_close=1.0,
    )
    assert out["ok"] is False
