"""SBBR 检测器单元测试（无数据库）。"""

from backend_core.strategies.sbbr.bottom_detector import detect_bottom, detect_range_bottom
from backend_core.strategies.sbbr.config import get_default_sbbr_config
from backend_core.strategies.sbbr.defense_exit import calc_defense_band, evaluate_exit_factors
from backend_core.strategies.sbbr.entry_detector import detect_entry
from backend_core.strategies.sbbr.position_advisor import advise_position
from backend_core.strategies.sbbr.size_filter import evaluate_size
from backend_core.strategies.sbbr.support_confirm import evaluate_support_confirm


def _bar(date, o, h, l, c, v, tr=None, amount=None):
    return {
        "date": date,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "turnover_rate": tr,
        "amount": amount,
    }


def test_size_filter_ok():
    cfg = get_default_sbbr_config()
    # 总股本 1e8 股 * 50 元 = 50 亿；流通 0.8e8 * 50 = 40 亿
    r = evaluate_size(
        total_shares=1e8,
        free_float_shares=0.8e8,
        close=50,
        config=cfg,
    )
    assert r["size_ok"] is True
    assert 20 <= r["total_mv"] <= 200
    assert 20 <= r["circ_mv"] <= 200


def test_size_filter_out_of_range():
    cfg = get_default_sbbr_config()
    r = evaluate_size(total_shares=1e10, free_float_shares=1e10, close=100, config=cfg)
    assert r["size_ok"] is False


def test_range_bottom_touches():
    bars = []
    # 构建窄幅箱体，多次触底
    for i in range(60):
        if i % 15 == 0:
            c = 9.8
            low = 9.7
            vol = 50
        else:
            c = 10.2 + (i % 5) * 0.05
            low = 10.0
            vol = 120 if c > 10.1 else 40
        bars.append(_bar(f"2024-01-{i+1:02d}" if i < 28 else f"2024-02-{(i-27):02d}", c, c + 0.3, low, c, vol))
    res = detect_range_bottom(
        bars,
        lookback=60,
        max_range_pct=0.6,
        touch_tol_pct=0.03,
        min_touches=3,
        max_touches=20,
        require_up_vol_gt_down=False,
    )
    assert res["matched"] is True or res["touches"] >= 3


def test_entry_requires_bottom():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-03-{i+1:02d}", 10, 11, 9, 10 + i * 0.01, 100) for i in range(30)]
    r = detect_entry(bars, [-0.01] * 10, bottom_matched=False, config=cfg)
    assert r["entry_signal"] is False


def test_defense_band_and_exit():
    cfg = get_default_sbbr_config()
    band = calc_defense_band(10.0, cfg)
    assert band["defense_low"] < 10.0
    assert band["defense_high"] == 10.0

    bars = []
    price = 10.0
    for i in range(40):
        price *= 1.02
        bars.append(_bar(f"2024-04-{i+1:02d}", price, price * 1.01, price * 0.99, price, 200, tr=25.0))
    ex = evaluate_exit_factors(bars, entry_price=10.0, config=cfg)
    assert ex["space_ok"] is True
    assert ex["any_ok"] is True


def test_exit_consolidate_uses_entry_idx():
    """入场前的虚高不应计入高位盘整参考高点。"""
    cfg = get_default_sbbr_config()
    bars = []
    # 前 20 日高点 20，入场后横盘在 11 附近
    for i in range(20):
        bars.append(_bar(f"2024-01-{i+1:02d}", 20, 20.5, 19.5, 20.0, 100, tr=5.0))
    for i in range(20):
        c = 11.0 + (i % 3) * 0.05
        bars.append(_bar(f"2024-02-{i+1:02d}", c, c + 0.1, c - 0.1, c, 100, tr=5.0))
    # 若按全序列高点 20，last≈11.1 远低于 85%*20，consolidate 应失败
    ex_all = evaluate_exit_factors(bars, entry_price=11.0, entry_idx=None, config=cfg)
    assert ex_all["consolidate_ok"] is False
    # 自入场后高点约 11.x，近 15 日窄幅且贴高 → 可成立
    ex_post = evaluate_exit_factors(bars, entry_price=11.0, entry_idx=20, config=cfg)
    assert ex_post["consolidate_ok"] is True


def test_exit_turnover_missing_and_fallback():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-06-{i+1:02d}", 10, 10.2, 9.8, 10.0, 100, tr=None, amount=None) for i in range(10)]
    ex = evaluate_exit_factors(bars, entry_price=10.0, config=cfg)
    assert ex["turnover_ok"] is False
    assert ex["turnover_reason"] == "missing_data"

    # amount / (ff * close) * 100；ff=1e8, close=10, amount=2e9 → 20% 日换手，5 日=100
    bars2 = [
        _bar(f"2024-06-{i+1:02d}", 10, 10.2, 9.8, 10.0, 100, tr=None, amount=2e9) for i in range(10)
    ]
    ex2 = evaluate_exit_factors(
        bars2, entry_price=10.0, free_float_shares=1e8, config=cfg
    )
    assert ex2["turnover_ok"] is True
    assert ex2["turnover_sum"] >= 100.0


def test_support_confirm_box_and_kde():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-07-{i+1:02d}", 10, 10.5, 9.8, 12.0, 100) for i in range(25)]
    ok = evaluate_support_confirm(
        close=12.0,
        defense_low=9.5,
        defense_breached=False,
        nearest_support=10.0,
        kde_ok=True,
        box_resistance=11.5,
        bars=bars,
        config=cfg,
    )
    assert ok["confirmed"] is True

    fail_kde = evaluate_support_confirm(
        close=12.0,
        defense_low=9.5,
        defense_breached=False,
        nearest_support=12.5,
        kde_ok=True,
        box_resistance=11.5,
        bars=bars,
        config=cfg,
    )
    assert fail_kde["confirmed"] is False
    assert fail_kde["reason"] == "below_nearest_support"

    # 无箱体阻力：要求站上 MA20
    panic_ok = evaluate_support_confirm(
        close=12.0,
        defense_low=9.5,
        defense_breached=False,
        nearest_support=10.0,
        kde_ok=True,
        box_resistance=None,
        bars=bars,
        config=cfg,
    )
    assert panic_ok["confirmed"] is True


def test_position_advisor_probe_and_cap():
    cfg = get_default_sbbr_config()
    a = advise_position(
        current_stage=None,
        allocated_pct=0,
        open_positions=0,
        total_capital=500_000,
        has_new_support=True,
        config=cfg,
    )
    assert a["next_action"] == "probe"
    assert a["max_open_positions"] == 2  # 小资金

    b = advise_position(
        current_stage="probe",
        allocated_pct=50,
        open_positions=1,
        total_capital=2_000_000,
        has_new_support=True,
        config=cfg,
    )
    assert b["next_action"] == "add"

    c = advise_position(
        current_stage="probe",
        allocated_pct=50,
        open_positions=1,
        total_capital=2_000_000,
        has_new_support=False,
        config=cfg,
    )
    assert c["next_action"] == "hold_probe"


def test_detect_bottom_wrapper():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-05-{(i%28)+1:02d}", 10, 10.5, 9.8, 10.1, 80) for i in range(70)]
    r = detect_bottom(bars, [0.0] * 70, cfg)
    assert "matched" in r
