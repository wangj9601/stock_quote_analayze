# -*- coding: utf-8 -*-
"""ZHAB 检测器：涨停后高位蓄势 / 再突破 / 失效样例。"""

from backend_core.strategies.zhab.detector import evaluate_zhab_bars, env_allows_executable
from backend_core.recommend.scoring import apply_anti_chase


def _bar(date, o, h, lo, c, vol, chg=None):
    return {
        "date": date,
        "open": o,
        "high": h,
        "low": lo,
        "close": c,
        "volume": vol,
        "change_percent": chg,
    }


def _pad(n=30, base=10.0, start="2025-01-01"):
    """平稳前导 K 线。"""
    from datetime import datetime, timedelta

    d0 = datetime.strptime(start, "%Y-%m-%d")
    bars = []
    for i in range(n):
        d = (d0 + timedelta(days=i)).strftime("%Y-%m-%d")
        bars.append(_bar(d, base, base + 0.1, base - 0.1, base, 1.0e6, 0.2))
    return bars


def test_env_cold_season_blocks_executable():
    ok, note = env_allows_executable(
        season="冬",
        gates_passed=4,
        gates_total=4,
        cold_seasons=["秋", "冬"],
        gates_pass_ratio_min=0.5,
    )
    assert ok is False
    assert "冬" in note


def test_setup_after_limit_up_shrink():
    """涨停 → 3 日缩量抬高低点 → 蓄势观察（未突破）。"""
    bars = _pad(40, base=10.0)
    # 涨停日：大阳放量
    bars.append(_bar("2025-02-10", 10.0, 11.0, 9.95, 11.0, 5.0e6, 10.0))
    # 整理 3 日：缩量、高位窄幅
    bars.append(_bar("2025-02-11", 10.9, 11.05, 10.7, 10.85, 2.0e6, -1.3))
    bars.append(_bar("2025-02-12", 10.85, 11.0, 10.75, 10.9, 1.8e6, 0.5))
    bars.append(_bar("2025-02-13", 10.9, 11.02, 10.8, 10.95, 1.6e6, 0.4))

    hit = evaluate_zhab_bars(
        bars,
        code="600000",
        asof_date="2025-02-13",
        zt_dates=["2025-02-10"],
        in_mainline=True,
        require_mainline=True,
        season="夏",
        gates_passed=3,
        gates_total=4,
    )
    assert hit is not None
    assert hit["signal_type"] == "setup"
    assert hit["setup_ok"] is True
    assert hit["entry_signal"] is False
    assert hit["consol_days"] == 3
    assert hit["detail"]["dims"]["zone"] is True
    assert hit["detail"]["dims"]["volume_atr"] is True


def test_breakout_with_volume_confirm():
    """涨停后缩量整理，再放量突破上沿。"""
    bars = _pad(40, base=10.0)
    bars.append(_bar("2025-02-10", 10.0, 11.0, 9.95, 11.0, 5.0e6, 10.0))
    bars.append(_bar("2025-02-11", 10.9, 11.05, 10.7, 10.85, 2.0e6, -1.3))
    bars.append(_bar("2025-02-12", 10.85, 11.0, 10.75, 10.9, 1.8e6, 0.5))
    bars.append(_bar("2025-02-13", 10.9, 11.02, 10.8, 10.95, 1.6e6, 0.4))
    # 突破日：收盘站上整理高点，量 ≥ 1.5× 整理均量
    bars.append(_bar("2025-02-14", 11.0, 11.4, 10.95, 11.35, 4.0e6, 3.6))

    hit = evaluate_zhab_bars(
        bars,
        code="600000",
        asof_date="2025-02-14",
        zt_dates=["2025-02-10"],
        in_mainline=True,
        season="夏",
        gates_passed=3,
        gates_total=4,
    )
    assert hit is not None
    assert hit["signal_type"] == "breakout"
    assert hit["entry_signal"] is True
    assert hit["detail"]["breakout_vol_ratio"] >= 1.5


def test_breakout_cold_season_watch_only():
    bars = _pad(40, base=10.0)
    bars.append(_bar("2025-02-10", 10.0, 11.0, 9.95, 11.0, 5.0e6, 10.0))
    bars.append(_bar("2025-02-11", 10.9, 11.05, 10.7, 10.85, 2.0e6, -1.3))
    bars.append(_bar("2025-02-12", 10.85, 11.0, 10.75, 10.9, 1.8e6, 0.5))
    bars.append(_bar("2025-02-13", 10.9, 11.02, 10.8, 10.95, 1.6e6, 0.4))
    bars.append(_bar("2025-02-14", 11.0, 11.4, 10.95, 11.35, 4.0e6, 3.6))

    hit = evaluate_zhab_bars(
        bars,
        code="600000",
        asof_date="2025-02-14",
        zt_dates=["2025-02-10"],
        in_mainline=True,
        season="冬",
        gates_passed=4,
        gates_total=4,
    )
    assert hit is not None
    assert hit["signal_type"] == "breakout"
    assert hit["entry_signal"] is False
    assert hit["detail"]["env_ok"] is False


def test_reject_high_volume_stall():
    """整理期放巨量滞涨 → 不构成蓄势。"""
    bars = _pad(40, base=10.0)
    bars.append(_bar("2025-02-10", 10.0, 11.0, 9.95, 11.0, 5.0e6, 10.0))
    bars.append(_bar("2025-02-11", 10.9, 11.2, 10.7, 10.9, 6.0e6, -0.9))  # 量 > 70% 涨停量
    bars.append(_bar("2025-02-12", 10.9, 11.1, 10.75, 10.95, 5.5e6, 0.5))
    bars.append(_bar("2025-02-13", 10.95, 11.15, 10.8, 11.0, 5.2e6, 0.4))

    hit = evaluate_zhab_bars(
        bars,
        code="600000",
        asof_date="2025-02-13",
        zt_dates=["2025-02-10"],
        in_mainline=True,
        season="夏",
        gates_passed=3,
        gates_total=4,
    )
    assert hit is None


def test_invalid_break_support():
    bars = _pad(40, base=10.0)
    bars.append(_bar("2025-02-10", 10.0, 11.0, 9.95, 11.0, 5.0e6, 10.0))
    bars.append(_bar("2025-02-11", 10.9, 11.05, 10.7, 10.85, 2.0e6, -1.3))
    bars.append(_bar("2025-02-12", 10.85, 11.0, 10.75, 10.9, 1.8e6, 0.5))
    # 跌破涨停日最低 / 箱体下沿
    bars.append(_bar("2025-02-13", 10.5, 10.6, 9.5, 9.6, 3.0e6, -12.0))

    hit = evaluate_zhab_bars(
        bars,
        code="600000",
        asof_date="2025-02-13",
        zt_dates=["2025-02-10"],
        in_mainline=True,
        season="夏",
        gates_passed=3,
        gates_total=4,
    )
    assert hit is not None
    assert hit["signal_type"] == "invalid"
    assert hit["setup_ok"] is False


def test_anti_chase_exempts_zhab_breakout_n_day_gain():
    action, reasons = apply_anti_chase(
        action="buy",
        quote={"close": 12.0, "n_day_gain_pct": 25.0, "is_limit_up": False},
        advice={"buy_zone": {"price": 11.0, "high": 11.2}},
        strategies=["zhab"],
        primary_strategy="zhab",
        signal_type="breakout",
    )
    assert action == "buy"
    assert reasons == []


def test_anti_chase_still_blocks_limit_up():
    action, reasons = apply_anti_chase(
        action="buy",
        quote={"close": 12.0, "n_day_gain_pct": 5.0, "is_limit_up": True},
        advice={"buy_zone": {"price": 11.0}},
        strategies=["zhab"],
        primary_strategy="zhab",
        signal_type="breakout",
    )
    assert action == "watch"
    assert "limit_up" in reasons
