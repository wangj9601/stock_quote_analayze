# -*- coding: utf-8 -*-
"""CSB 核心检测单测（无 DB）。"""

from backend_core.strategies.csb.channel import compute_channel_state, count_squeeze_days
from backend_core.strategies.csb.config import CSB_BREAKOUT, CSB_PROBE, CSB_SETUP, get_default_csb_config
from backend_core.strategies.csb.defense_exit import check_false_break
from backend_core.strategies.csb.entry_detector import detect_entry
from backend_core.strategies.csb.setup_detector import detect_setup
from backend_core.strategies.csb.strategy_engine import compute_score_detail, evaluate_one


def _make_bars(n: int = 280, base: float = 10.0) -> list:
    bars = []
    for i in range(n):
        c = base + (i % 7) * 0.01
        bars.append(
            {
                "date": f"2024-01-{i+1:02d}" if i < 31 else f"2024-02-{(i-30):02d}",
                "open": c - 0.02,
                "high": c + 0.05,
                "low": c - 0.05,
                "close": c,
                "volume": 1_000_000 + i * 1000,
                "turnover_rate": 2.5,
            }
        )
    return bars


def test_default_config():
    cfg = get_default_csb_config()
    assert cfg["channel"]["ma_squeeze_pct"] == 0.04
    assert cfg["backtest"]["horizon_days"] == 10


def test_channel_state_runs():
    bars = _make_bars()
    st = compute_channel_state(bars, get_default_csb_config())
    assert st.get("ok") is True
    assert st.get("ma20") is not None


def test_false_break():
    bars = [
        {"date": "2024-03-01", "close": 11.0, "high": 11.2, "low": 10.8},
        {"date": "2024-03-02", "close": 10.5, "high": 10.9, "low": 10.4},
    ]
    fb = check_false_break(bars, breakout_date="2024-03-01", channel_upper=10.8, false_break_days=3)
    assert fb.get("false_break") is True


def test_evaluate_one_returns_structure():
    bars = _make_bars()
    row = evaluate_one(bars, code="000001", name="测试", config=get_default_csb_config())
    assert row is not None
    assert "code" in row
    assert "score" in row
    assert "setup_ok" in row
    assert "detail" in row
    assert "score_detail" in row
    assert row["score_detail"].get("parts")
    assert row["detail"].get("score") == row["score_detail"]
    assert abs(float(row["score"]) - float(row["score_detail"]["total"])) < 1e-9


def test_compute_score_detail_probe_parts():
    result = {
        "channel": {"squeeze_days": 19, "squeeze_pct": 0.022},
        "touch_count": 4,
        "dry_vol": {"dry_ok": True},
        "turnover_ok": True,
        "signal_type": CSB_PROBE,
    }
    sd = compute_score_detail(result, get_default_csb_config())
    # min(25, 19*1.2)=22.8 + max(0,15*(1-0.022/0.06))=9.5 + min(15,16)=15 +10 +10 +12 = 79.3
    assert sd["parts"]["squeeze_days"]["score"] == 22.8
    assert sd["parts"]["entry_type"]["score"] == 12.0
    assert abs(sd["total"] - 79.3) < 1e-9


def test_score_premium_after_30_squeeze_days():
    result = {
        "channel": {"squeeze_days": 30, "squeeze_pct": 0.02},
        "touch_count": 2,
        "dry_vol": {"dry_ok": True},
        "turnover_ok": True,
        "spring_ok": True,
        "signal_type": CSB_BREAKOUT,
        "vol_expand_mult": 2.0,
    }
    sd = compute_score_detail(result, get_default_csb_config())
    assert sd["parts"]["squeeze_premium"]["score"] == 8.0
    assert sd["parts"]["spring"]["score"] == 6.0


def test_support_tests_cluster_counts_once():
    from backend_core.strategies.csb.setup_detector import count_support_tests

    bars = []
    # 连续贴下轨 3 天只算 1 次，离开后再回来算第 2 次
    seq = [
        (10.00, 10.05),
        (9.98, 10.02),
        (9.99, 10.04),
        (10.35, 10.50),
        (10.00, 10.08),
    ]
    for i, (low, close) in enumerate(seq):
        bars.append(
            {
                "date": f"2024-05-{i+1:02d}",
                "open": close,
                "high": close + 0.05,
                "low": low,
                "close": close,
                "volume": 1_000_000,
            }
        )
    n = count_support_tests(
        bars,
        lower=10.0,
        touch_tol_pct=0.015,
        leave_pct=0.03,
        lookback=10,
        config=get_default_csb_config(),
    )
    assert n == 2


def test_ma250_requires_flat_or_up_slope():
    from backend_core.strategies.csb.setup_detector import check_ma250_defense

    flat = []
    down = []
    for i in range(280):
        flat.append({"close": 10.0, "date": f"d{i}"})
        down.append({"close": 30.0 - i * 0.05, "date": f"d{i}"})
    cfg = get_default_csb_config()
    assert check_ma250_defense(flat, cfg)["ma250_ok"] is True
    assert check_ma250_defense(down, cfg)["ma250_ok"] is False


def test_breakout_uses_turnover_and_channel_upper():
    from backend_core.strategies.csb.entry_detector import detect_breakout

    bars = []
    for i in range(21):
        bars.append(
            {
                "date": f"2024-04-{i+1:02d}",
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 5_000_000,
                "turnover_rate": 1.0,
            }
        )
    bars[-1] = {
        "date": "2024-04-21",
        "open": 10.0,
        "high": 10.32,
        "low": 9.95,
        "close": 10.30,
        "volume": 100,
        "turnover_rate": 3.0,
    }
    setup = {"setup_ok": True, "channel": {"upper": 10.0, "lower": 9.5, "hh20": 12.0}}
    r = detect_breakout(bars, setup, get_default_csb_config())
    assert r["entry_signal"] is True
    assert r["resistance"] == 10.0
    assert r["vol_expand_mult"] == 3.0


def test_breakout_rejects_long_upper_shadow():
    from backend_core.strategies.csb.entry_detector import detect_breakout

    bars = []
    for i in range(21):
        bars.append(
            {
                "date": f"2024-04-{i+1:02d}",
                "open": 10,
                "high": 10.1,
                "low": 9.9,
                "close": 10,
                "volume": 1e6,
                "turnover_rate": 1.0,
            }
        )
    # 实体 0.30，上影 0.10 → 比例 0.33 > 0.20
    bars[-1] = {
        "date": "2024-04-21",
        "open": 10.0,
        "high": 10.40,
        "low": 9.95,
        "close": 10.30,
        "volume": 1e6,
        "turnover_rate": 3.0,
    }
    setup = {"setup_ok": True, "channel": {"upper": 10.0}}
    r = detect_breakout(bars, setup, get_default_csb_config())
    assert r["entry_signal"] is False
    assert r["shadow_ok"] is False


def test_probe_rejects_plain_yang_away_from_lower():
    from backend_core.strategies.csb.entry_detector import detect_probe

    bars = []
    for i in range(25):
        vol = 2_000_000 if i < 20 else 500_000
        bars.append(
            {
                "date": f"2024-07-{i+1:02d}",
                "open": 10.0,
                "high": 10.2,
                "low": 9.95,
                "close": 10.15,
                "volume": vol,
                "turnover_rate": 1.0,
            }
        )
    setup = {"setup_ok": True, "channel": {"lower": 8.0, "upper": 10.2}}
    r = detect_probe(bars, setup, get_default_csb_config())
    assert r["entry_signal"] is False


def test_spring_bar():
    from backend_core.strategies.csb.setup_detector import bar_is_spring

    prev = [{"volume": 1_000_000, "close": 10} for _ in range(20)]
    bar = {"open": 10.0, "high": 10.1, "low": 9.85, "close": 10.02, "volume": 200_000}
    assert bar_is_spring(
        bar,
        lower=10.0,
        pierce_min_pct=0.01,
        pierce_max_pct=0.02,
        vol_avg=1_000_000,
        vol_ratio_max=0.55,
    )
    assert not bar_is_spring(
        {**bar, "low": 9.5},
        lower=10.0,
        pierce_min_pct=0.01,
        pierce_max_pct=0.02,
        vol_avg=1_000_000,
        vol_ratio_max=0.55,
    )
    _ = prev


def test_lps_confirm():
    from backend_core.strategies.csb.entry_detector import confirm_lps

    bo = {"open": 10.0, "close": 10.4, "low": 9.9, "volume": 2_000_000, "turnover_rate": 4}
    today = {"open": 10.15, "high": 10.4, "low": 10.05, "close": 10.30, "volume": 800_000, "turnover_rate": 1.5}
    r = confirm_lps(today, bo, channel_upper=10.2, config=get_default_csb_config())
    assert r["entry_signal"] is True

