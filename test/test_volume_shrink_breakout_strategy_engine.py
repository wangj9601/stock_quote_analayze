"""
3倍量缩量突破 — strategy_engine 纯逻辑单测（无 DB）
"""

import pytest

from backend_core.strategies.volume_shrink_breakout.strategy_engine import (
    evaluate_stock,
    find_boom_index,
    pass_ma_bull_at_k,
    pass_shrink_breakout,
    validate_phase2_retracement,
    validate_phase3_entry,
)


def _bar(date: str, close: float, volume: float) -> dict:
    return {
        "date": date,
        "open": close,
        "close": close,
        "high": close,
        "low": close,
        "change_percent": 0.0,
        "volume": volume,
        "amount": 0.0,
        "code": "600000",
        "name": "测试",
    }


def test_find_boom_index_smallest_k_wins():
    # 索引大=更久远；爆量在 k=5：vol[5]=300, vol[6]=100 -> 3x
    vol = [10.0] * 5 + [300.0, 100.0, 80.0, 70.0] + [50.0] * 40
    k = find_boom_index(vol, volume_ratio=3.0, k_min=3, k_max=10)
    assert k == 5


def test_find_boom_index_none_when_no_spike():
    vol = [100.0 + i for i in range(80)]
    k = find_boom_index(vol, volume_ratio=3.0, k_min=5, k_max=20)
    assert k is None


def test_pass_shrink_breakout():
    closes = [12.0, 10.0, 9.0]
    volumes = [50.0, 400.0, 100.0]
    assert pass_shrink_breakout(closes, volumes, k=1) is True
    assert pass_shrink_breakout([9.0, 10.0], volumes, k=1) is False


def test_pass_ma_bull_at_k():
    # 全平则 MA5=MA10=MA20，不满足严格大于
    closes_flat = [100.0] * 80
    assert pass_ma_bull_at_k(closes_flat, 10) is False
    # 数据最新在前：下标越大越久远；收盘价随 i 增大而减小 => 近端更高，典型多头均线 MA5>MA10>MA20
    closes_up = [20.0 + (80 - i) * 0.2 for i in range(80)]
    assert pass_ma_bull_at_k(closes_up, 10) is True


def test_evaluate_stock_happy_path():
    hist = []
    for i in range(80):
        c = 20.0 + (80 - i) * 0.15
        v = 88.0
        if i == 0:
            c, v = 32.5, 80.0
        elif i == 5:
            c, v = 31.0, 300.0
        elif i == 6:
            c, v = 30.5, 90.0
        hist.append(_bar(f"2024-03-{min(i+1, 28):02d}", c, v))
    out = evaluate_stock(
        hist,
        volume_ratio=3.0,
        boom_lookback_min=4,
        boom_lookback_max=15,
        config={"evaluation_mode": "legacy"},
    )
    assert out is not None
    assert out["boom_volume_ratio_vs_prev"] is not None
    assert out["breakout_close"] == pytest.approx(32.5)
    assert "buy_signal" in out and isinstance(out["buy_signal"], str)
    assert "signal_strength" in out and 0 <= int(out["signal_strength"]) <= 100
    assert out["signal_strength_level"] in ("强", "中", "弱")
    assert isinstance(out["signal_reminders"], list)


def test_evaluate_stock_rejects_high_volume_breakout():
    hist = []
    for i in range(80):
        c = 10.0 + i * 0.02
        v = 100.0 if i != 0 else 500.0
        if i == 5:
            v = 300.0
        if i == 6:
            v = 90.0
        hist.append(_bar(f"d{i}", c, v))
    out = evaluate_stock(hist, volume_ratio=3.0, boom_lookback_min=4, boom_lookback_max=20)
    assert out is None


def _three_phase_synthetic_hist_ok():
    """DESC 序列：侦测日 s=24 倍量+MA5 上穿 MA20，回调段缩量，触发日突破。"""
    n = 90
    hist = []
    for i in range(n):
        c = 50.0 if i >= 26 else 50.0 + (25 - i) * 0.2
        hist.append(_bar(f"d{i:03d}", c, 52.0))
    s = 24
    b = hist[s]
    hist[s] = _bar(b["date"], b["close"], 300.0)
    b1 = hist[s + 1]
    hist[s + 1] = _bar(b1["date"], b1["close"], 90.0)
    for t in range(1, s):
        bt = hist[t]
        hist[t] = _bar(bt["date"], bt["close"], 40.0)
    b0 = hist[0]
    hist[0] = _bar(b0["date"], hist[s]["close"] + 1.0, 45.0)
    return hist


def test_evaluate_stock_three_phase_happy_path():
    hist = _three_phase_synthetic_hist_ok()
    cfg = {
        "evaluation_mode": "three_phase",
        "trend_ma_lookback": 5,
        "retracement_break_eps": 0.02,
        "ma_flat_tol": 0.04,
        "retracement_volume_half_ratio": 0.5,
    }
    out = evaluate_stock(
        hist,
        volume_ratio=3.0,
        boom_lookback_min=15,
        boom_lookback_max=35,
        config=cfg,
    )
    assert out is not None
    assert out["strategy_phase"] == "three_phase_v1"
    assert out["phase_state"]["strategy_phase"] == "three_phase_v1"
    assert out["phase_state"].get("C_limit") is not None
    assert out["breakout_close"] > out["boom_close"]


def test_evaluate_stock_three_phase_rejects_break_floor():
    hist = _three_phase_synthetic_hist_ok()
    mid = hist[5]
    hist[5] = _bar(mid["date"], 40.0, mid["volume"])
    cfg = {
        "evaluation_mode": "three_phase",
        "trend_ma_lookback": 5,
        "retracement_break_eps": 0.02,
        "ma_flat_tol": 0.04,
        "retracement_volume_half_ratio": 0.5,
    }
    assert (
        evaluate_stock(
            hist,
            volume_ratio=3.0,
            boom_lookback_min=15,
            boom_lookback_max=35,
            config=cfg,
        )
        is None
    )


def test_evaluate_stock_three_phase_rejects_retracement_volume():
    hist = _three_phase_synthetic_hist_ok()
    mid = hist[5]
    hist[5] = _bar(mid["date"], mid["close"], 200.0)
    cfg = {
        "evaluation_mode": "three_phase",
        "trend_ma_lookback": 5,
        "retracement_break_eps": 0.02,
        "ma_flat_tol": 0.04,
        "retracement_volume_half_ratio": 0.5,
    }
    assert (
        evaluate_stock(
            hist,
            volume_ratio=3.0,
            boom_lookback_min=15,
            boom_lookback_max=35,
            config=cfg,
        )
        is None
    )


def test_validate_phase2_rejects_close_below_floor():
    hist = _three_phase_synthetic_hist_ok()
    closes = [float(b["close"]) for b in hist]
    vols = [float(b["volume"]) for b in hist]
    s = 24
    o_lim = float(hist[s]["open"])
    l_lim = float(hist[s]["low"])
    v_lim = 300.0
    assert validate_phase2_retracement(
        hist,
        closes,
        vols,
        s,
        o_lim,
        l_lim,
        v_lim,
        eps=0.02,
        vol_half=0.5,
        flat_tol=0.04,
    )
    hist_bad = [dict(b) for b in hist]
    hist_bad[5] = _bar(hist_bad[5]["date"], 40.0, 40.0)
    closes_b = [float(b["close"]) for b in hist_bad]
    assert not validate_phase2_retracement(
        hist_bad,
        closes_b,
        vols,
        s,
        o_lim,
        l_lim,
        v_lim,
        eps=0.02,
        vol_half=0.5,
        flat_tol=0.04,
    )


def test_validate_phase3_entry():
    closes = [51.0, 50.0, 49.0]
    vols = [40.0, 50.0, 60.0]
    assert validate_phase3_entry(closes, vols, c_limit=50.2, v_limit=300.0)
    assert not validate_phase3_entry(closes, vols, c_limit=52.0, v_limit=300.0)
    assert not validate_phase3_entry(closes, vols, c_limit=50.0, v_limit=35.0)
