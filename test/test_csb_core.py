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
