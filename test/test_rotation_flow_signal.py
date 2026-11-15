"""资金流 × 轮动象限的交叉信号：矩阵分类、未覆盖兜底、汇总名单。"""

from backend_core.analysis.rotation_flow_signal import (
    classify_flow_rotation,
    summarize_flow_rotation,
)


def test_leading_with_outflow_is_a_reversal_alert():
    signal = classify_flow_rotation("leading", "out")
    assert signal["signal_key"] == "reversal_alert"
    assert signal["signal_label"] == "兑现预警"
    assert signal["signal_level"] == "risk"


def test_leading_with_inflow_confirms_the_trend():
    signal = classify_flow_rotation("leading", "in")
    assert signal["signal_key"] == "main_uptrend"
    assert signal["signal_level"] == "strong"


def test_improving_with_inflow_is_the_best_left_side_combo():
    signal = classify_flow_rotation("improving", "in")
    assert signal["signal_label"] == "改善承接"
    assert signal["signal_level"] == "strong"


def test_lagging_with_outflow_is_still_bleeding():
    signal = classify_flow_rotation("lagging", "out")
    assert signal["signal_label"] == "持续失血"
    assert signal["signal_level"] == "risk"


def test_missing_quadrant_falls_back_to_uncovered():
    for quadrant in (None, "", "unknown"):
        signal = classify_flow_rotation(quadrant, "in")
        assert signal["signal_key"] == "uncovered"
        assert signal["signal_level"] == "unknown"


def test_flat_direction_is_uncovered_not_guessed():
    signal = classify_flow_rotation("leading", "flat")
    assert signal["signal_key"] == "uncovered"


def test_summary_counts_quadrants_and_picks_alerts():
    items = [
        {"board_code": "1", "board_name": "银行", "direction": "in", "main_net_yi": 61.8,
         "rotation_quadrant": "improving", "signal_level": "strong",
         "signal_key": "improve_bid", "signal_label": "改善承接"},
        {"board_code": "2", "board_name": "软件开发", "direction": "out", "main_net_yi": -127.5,
         "rotation_quadrant": "leading", "signal_level": "risk",
         "signal_key": "reversal_alert", "signal_label": "兑现预警"},
        {"board_code": "3", "board_name": "元件", "direction": "out", "main_net_yi": -113.4,
         "rotation_quadrant": "leading", "signal_level": "risk",
         "signal_key": "reversal_alert", "signal_label": "兑现预警"},
        {"board_code": "4", "board_name": "无轮动", "direction": "out", "main_net_yi": -3,
         "rotation_quadrant": None, "signal_level": "unknown",
         "signal_key": "uncovered", "signal_label": "未覆盖"},
    ]
    summary = summarize_flow_rotation(items)
    assert summary["covered"] == 3
    assert summary["uncovered"] == 1
    assert summary["quadrant_counts"]["leading"] == 2
    assert summary["quadrant_counts"]["improving"] == 1
    assert [alert["board_name"] for alert in summary["alerts"]] == ["软件开发", "元件"]
    assert [item["board_name"] for item in summary["supports"]] == ["银行"]
