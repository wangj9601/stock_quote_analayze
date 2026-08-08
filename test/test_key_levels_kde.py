"""个股详情关键价位：与 RPE 成交量加权 KDE 同口径。"""

import random
import sys
from pathlib import Path

import pytest

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
    assert len(out["resistance_levels"]) <= 2
    assert len(out["support_levels"]) <= 2

    # 与 RPE 峰划分一致（按当前价），展示侧各最多 2 档
    peaks = kde.get("all_peaks") or []
    expect_r = sorted([round(p, 2) for p in peaks if p > current])[:2]
    expect_s = sorted([round(p, 2) for p in peaks if 0 < p < current], reverse=True)[:2]
    assert out["resistance_levels"] == expect_r
    assert out["support_levels"] == expect_s
    assert KeyLevels.MAX_LEVELS == 2
    assert out.get("nearest_support") == (expect_s[0] if expect_s else None)
    assert out.get("nearest_resistance") == (expect_r[0] if expect_r else None)
    assert out.get("kde_lookback_initial") == KeyLevels.KDE_LOOKBACK_DAYS
    assert out.get("kde_lookback_max") == KeyLevels.KDE_LOOKBACK_MAX


def test_key_levels_insufficient_samples():
    out = KeyLevels.calculate_key_levels([{"close": 10, "volume": 1}] * 10, 10.0)
    assert out["resistance_levels"] == []
    assert out["support_levels"] == []
    assert out["kde_ok"] is False
    assert out.get("nearest_support") is None
    assert out.get("nearest_resistance") is None


def test_key_levels_max_levels_param():
    bars = _fake_bars(n=120, seed=11)
    out = KeyLevels.calculate_key_levels(bars, 15.0, max_levels=8)
    assert len(out["support_levels"]) <= 8
    assert len(out["resistance_levels"]) <= 8
    assert out["method"] == "kde_volume_weighted"


def test_classic_reference_levels_from_bars():
    """支撑压力接口附带的 Fib / Pivot 参考价。"""
    from datetime import date, timedelta

    bars = []
    base = date(2024, 1, 1)
    for i in range(40):
        px = 10.0 + (i / 39.0) * 5.0
        bars.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "high": round(px + 0.3, 2),
                "low": round(px - 0.3, 2),
                "close": round(px, 2),
                "volume": 1_000_000,
            }
        )
    out = KeyLevels.calculate_classic_reference_levels(bars, bars[-1]["close"])
    assert out["ok"] is True
    assert out["pivot"] is not None
    assert out["pivot"]["P"] is not None
    assert out["fibonacci"] is not None
    # ZigZag 锚定：单调上升序列也可能确认波段；至少有 pivot/cam
    assert out.get("camarilla") is not None
    assert out.get("lookback") == 180
    if out["fibonacci"].get("ok"):
        assert len(out["fibonacci"]["retracements"]) >= 3
    assert out["fibonacci"].get("anchor_method") == "zigzag_fractal"


def test_classic_levels_follow_qfq_ohlc():
    """前复权 OHLC 下 Fib/Pivot 须按复权价重算（与不复权结果不同）。"""
    from datetime import date, timedelta

    from backend_api.utils.adj_quotes import apply_qfq_to_bars

    base = date(2024, 1, 1)
    raw = []
    for i in range(30):
        px = 20.0 + i * 0.5
        raw.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "high": px + 1,
                "low": px - 1,
                "close": px,
                "volume": 1_000_000,
            }
        )
    # 前半段因子 1、后半段因子 2 → 前半段前复权缩半
    mid = base + timedelta(days=14)
    end = base + timedelta(days=29)
    factors = [(base, 1.0), (mid, 1.0), (end, 2.0)]
    qfq = apply_qfq_to_bars(raw, factors)
    raw_out = KeyLevels.calculate_classic_reference_levels(
        raw, raw[-1]["close"], price_adjust="none"
    )
    qfq_out = KeyLevels.calculate_classic_reference_levels(
        qfq, qfq[-1]["close"], price_adjust="qfq"
    )
    assert qfq_out["price_adjust"] == "qfq"
    assert raw_out["pivot"]["P"] != qfq_out["pivot"]["P"]
    # 有 ZigZag 锚点时 Fib 高低随复权变化；否则至少 Camarilla 随 OHLC 变
    if (
        raw_out["fibonacci"]
        and qfq_out["fibonacci"]
        and raw_out["fibonacci"].get("swing_low") is not None
        and qfq_out["fibonacci"].get("swing_low") is not None
    ):
        assert raw_out["fibonacci"]["swing_low"] != qfq_out["fibonacci"]["swing_low"]
    else:
        assert raw_out["camarilla"]["R1"] != qfq_out["camarilla"]["R1"]
    # 前复权锚点强制用序列末收
    assert qfq_out["last_close"] == pytest.approx(qfq[-1]["close"], abs=0.01)
