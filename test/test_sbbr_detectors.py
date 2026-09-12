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
    # 总股本 1e9 股 * 10 元 = 100 亿市值；流通股本 6e8 股 = 6 亿股（两侧都达标）
    r = evaluate_size(
        total_shares=1e9,
        free_float_shares=6e8,
        close=10,
        config=cfg,
    )
    assert r["size_ok"] is True
    assert 20 <= r["total_mv"] <= 300
    assert r["circ_shares_yi"] > 5


def test_size_filter_out_of_range():
    cfg = get_default_sbbr_config()
    # 总市值过大且流通股本过小 → 双侧都不达标
    r = evaluate_size(total_shares=1e10, free_float_shares=0.8e8, close=100, config=cfg)
    assert r["size_ok"] is False


def test_size_filter_or_total_ok_shares_fail():
    cfg = get_default_sbbr_config()
    # 总市值 100 亿合格，流通股本 2.54 亿股不达标 → OR 仍通过
    r = evaluate_size(total_shares=1e9, free_float_shares=2.54e8, close=10, config=cfg)
    assert r["size_ok"] is True
    assert r["size_reason"] == "total_ok"


def test_size_filter_or_shares_ok_total_fail():
    cfg = get_default_sbbr_config()
    # 总市值过大，流通股本 20 亿股 > 5 → OR 通过
    r = evaluate_size(total_shares=1e10, free_float_shares=20e8, close=100, config=cfg)
    assert r["size_ok"] is True
    assert r["circ_shares_yi"] == 20.0
    assert r["size_reason"] == "circ_shares_ok"


def test_size_filter_circ_shares_too_small_and_tiny_mv():
    cfg = get_default_sbbr_config()
    # 总市值过小 + 流通股本过小 → 不通过
    r = evaluate_size(total_shares=1e8, free_float_shares=0.8e8, close=10, config=cfg)
    assert r["size_ok"] is False
    assert r["circ_shares_yi"] == 0.8


def test_size_filter_match_mode_all_requires_both():
    cfg = get_default_sbbr_config()
    cfg["size"]["match_mode"] = "all"
    r = evaluate_size(total_shares=1e9, free_float_shares=2.54e8, close=10, config=cfg)
    assert r["size_ok"] is False


def test_range_bottom_touches():
    bars = []
    # 构建窄幅箱体，多次触底（真横盘，不应被趋势过滤误杀）
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
        max_range_pct=0.35,
        touch_tol_pct=0.03,
        min_touches=3,
        max_touches=20,
        require_up_vol_gt_down=False,
    )
    assert res["matched"] is True
    assert res["mode"] == "range_accumulation"


def _declining_channel_bars(n: int = 60, start: float = 12.0, end: float = 9.5):
    """合成下跌通道：高点在前、低点持续下移，振幅可能仍 < 0.60。"""
    bars = []
    for i in range(n):
        t = i / max(n - 1, 1)
        c = start + (end - start) * t
        # 小幅日内波动，整体下行
        h = c * 1.015
        l = c * 0.985
        vol = 80 + (i % 7) * 5
        month = 1 + i // 28
        day = (i % 28) + 1
        bars.append(_bar(f"2024-{month:02d}-{day:02d}", c, h, l, c, vol))
    return bars


def test_range_bottom_rejects_declining_channel():
    """下跌通道即使振幅未超旧阈值，也应被趋势/新低/高前低后等过滤拒绝。"""
    bars = _declining_channel_bars()
    # 故意放宽振幅，确保是过滤器而非 range_too_wide 拦住
    res = detect_range_bottom(
        bars,
        lookback=60,
        max_range_pct=0.60,
        touch_tol_pct=0.03,
        min_touches=1,
        max_touches=60,
        require_up_vol_gt_down=False,
    )
    assert res["matched"] is False
    assert res["mode"] is None
    reason = (res.get("detail") or {}).get("reason")
    assert reason in {
        "close_drop_too_steep",
        "close_slope_too_negative",
        "new_low_sequence",
        "high_before_low",
        "ma_env_reject",
    }


def test_range_bottom_true_sideways_passes():
    """真横盘：窄幅震荡 + 有限次触底，默认过滤下应命中。"""
    bars = []
    touch_days = {5, 20, 35, 50}  # 恰好 4 次贴近下沿
    for i in range(60):
        if i in touch_days:
            c, low, high, vol = 9.95, 9.90, 10.05, 55
        else:
            # 低点远离支撑容差带（support*1.02），避免误计触底
            c = 10.22 + (i % 5) * 0.02
            low, high = 10.12, c + 0.05
            vol = 120 if (i % 2 == 0) else 100
        month = 1 + i // 28
        day = (i % 28) + 1
        bars.append(_bar(f"2024-{month:02d}-{day:02d}", c, high, low, c, vol))
    cfg = get_default_sbbr_config()
    res = detect_bottom(bars, [0.0] * len(bars), cfg)
    assert res["matched"] is True
    assert res["mode"] == "range_accumulation"
    assert 3 <= int(res.get("touches") or 0) <= 4


def test_frozen_box_resistance_stable_after_new_high():
    """首次命中后锁定箱阻；后续窗内新高只反映在 window_high，不抬升 box_resistance。"""
    from backend_core.strategies.sbbr.bottom_detector import detect_range_bottom_with_freeze

    bars = []
    touch_days = {5, 20, 35, 50}
    for i in range(60):
        if i in touch_days:
            c, low, high, vol = 9.95, 9.90, 10.05, 55
        else:
            c = 10.22 + (i % 5) * 0.02
            low, high = 10.12, c + 0.05
            vol = 120 if (i % 2 == 0) else 100
        month = 1 + i // 28
        day = (i % 28) + 1
        bars.append(_bar(f"2024-{month:02d}-{day:02d}", c, high, low, c, vol))

    cfg = get_default_sbbr_config()
    first = detect_range_bottom_with_freeze(bars, cfg)
    assert first.get("matched") is True
    assert first.get("detail", {}).get("box_frozen") is True
    locked_res = float(first["resistance"])
    locked_sup = float(first["support"])

    # 再追加若干日：抬高新高，但仍在箱体内（未上破 5%）
    for j in range(5):
        c = 10.35 + j * 0.02
        # 新高略高于原窗口，但低于 locked_res * 1.05
        high = min(locked_res * 1.04, c + 0.15)
        bars.append(
            _bar(
                f"2024-03-{j+1:02d}",
                c,
                high,
                max(locked_sup * 1.05, c - 0.1),
                c,
                110,
            )
        )

    later = detect_range_bottom_with_freeze(bars, cfg)
    assert later.get("matched") is True
    assert abs(float(later["resistance"]) - locked_res) < 1e-9
    assert abs(float(later["support"]) - locked_sup) < 1e-9
    win_hi = later.get("window_high")
    assert win_hi is not None
    # 滚动窗最高可以高于冻结阻力
    assert float(win_hi) >= locked_res - 1e-9


def test_detect_bottom_wrapper_uses_tight_range_default():
    cfg = get_default_sbbr_config()
    assert abs(float(cfg["bottom"]["max_range_pct"]) - 0.35) < 1e-9
    bars = [_bar(f"2024-05-{(i % 28) + 1:02d}", 10, 10.5, 9.8, 10.1, 80) for i in range(70)]
    r = detect_bottom(bars, [0.0] * 70, cfg)
    assert "matched" in r


def test_entry_requires_bottom():
    cfg = get_default_sbbr_config()
    bars = [_bar(f"2024-03-{i+1:02d}", 10, 11, 9, 10 + i * 0.01, 100) for i in range(30)]
    r = detect_entry(bars, [-0.01] * 10, bottom_matched=False, config=cfg)
    assert r["entry_signal"] is False


def test_entry_market_soft_filter_still_computed():
    """大盘共振默认仅计算：未达标也不挡入场；开启 require 后才硬筛。"""
    cfg = get_default_sbbr_config()
    assert cfg["entry"]["require_market_sync_down"] is False

    # 构造：底部已匹配前提下，尽量满足上穿/缩量/微放量
    bars = []
    for i in range(30):
        # 前段缩量，末两日穿越 MA 并微放量
        vol = 50 if i < 25 else (40 if i < 29 else 55)
        c = 9.5 if i < 28 else (9.8 if i == 28 else 10.5)
        bars.append(_bar(f"2024-03-{i+1:02d}", c, c + 0.2, c - 0.2, c, vol))

    # 大盘近5日上涨 → market_ok=False
    mrets = [0.01] * 20
    soft = detect_entry(bars, mrets, bottom_matched=True, config=cfg)
    assert soft["market_ok"] is False
    assert soft.get("market_required") is False
    # 其它条件若过，入场可不受大盘影响
    if soft.get("cross_up") and soft.get("shrink_ok") and soft.get("expand_ok"):
        assert soft["entry_signal"] is True

    cfg_hard = get_default_sbbr_config()
    cfg_hard["entry"]["require_market_sync_down"] = True
    hard = detect_entry(bars, mrets, bottom_matched=True, config=cfg_hard)
    assert hard["market_ok"] is False
    assert hard["entry_signal"] is False


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
