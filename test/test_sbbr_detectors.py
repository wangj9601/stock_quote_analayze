"""SBBR 检测器单元测试（无数据库）。"""

from backend_core.strategies.sbbr.bottom_detector import detect_bottom, detect_range_bottom
from backend_core.strategies.sbbr.config import get_default_sbbr_config
from backend_core.strategies.sbbr.defense_exit import calc_defense_band, evaluate_exit_factors
from backend_core.strategies.sbbr.entry_detector import detect_entry
from backend_core.strategies.sbbr.position_advisor import advise_position
from backend_core.strategies.sbbr.size_filter import evaluate_size


def _bar(date, o, h, l, c, v, tr=None):
    return {
        "date": date,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "turnover_rate": tr,
    }


def test_size_filter_ok():
    cfg = get_default_sbbr_config()
    # 总股本 1e8 股 * 50 元 = 50 亿；流通 0.15e8 * 50 = 7.5 亿
    r = evaluate_size(
        total_shares=1e8,
        free_float_shares=0.15e8,
        close=50,
        config=cfg,
    )
    assert r["size_ok"] is True
    assert 20 <= r["total_mv"] <= 200
    assert 5 <= r["circ_mv"] <= 10


def test_size_filter_out_of_range():
    cfg = get_default_sbbr_config()
    r = evaluate_size(total_shares=1e10, free_float_shares=1e10, close=100, config=cfg)
    assert r["size_ok"] is False


def test_range_bottom_touches():
    bars = []
    # 构建窄幅箱体，多次触底
    for i in range(60):
        base = 10.0
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


def test_detect_bottom_wrapper():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-05-{(i%28)+1:02d}", 10, 10.5, 9.8, 10.1, 80) for i in range(70)]
    r = detect_bottom(bars, [0.0] * 70, cfg)
    assert "matched" in r
