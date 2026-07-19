# -*- coding: utf-8 -*-
"""URT 买点判断逻辑结构化输出。"""

from backend_core.strategies.urt.signal_detector import build_buy_logic


def test_build_buy_logic_pass():
    cfg = {
        "ma_period": 20,
        "volume_multiple": 2.5,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "use_turnover": False,
        "use_volume_ratio": False,
    }
    detail = {
        "close": 10.5,
        "ma20": 10.0,
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "rule_a_ok": True,
        "rule_b_ok": True,
        "volume_multiple": 2.8,
        "score": 86,
        "filter_ok": True,
        "score_ok": True,
        "buy_signal": True,
        "filter_reason": "ok",
    }
    logic = build_buy_logic(detail, cfg)
    assert logic["buy_signal"] is True
    assert logic["filter_ok"] is True
    assert logic["score_ok"] is True
    assert logic["formula"].startswith("买点")
    ids = [s["id"] for s in logic["steps"]]
    assert ids == ["above_ma", "yang", "volume_multiple", "min_score"]
    assert all(s["pass"] for s in logic["steps"])


def test_build_buy_logic_fail_volume():
    cfg = {
        "ma_period": 20,
        "volume_multiple": 2.5,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "use_turnover": False,
        "use_volume_ratio": False,
    }
    detail = {
        "close": 10.5,
        "ma20": 10.0,
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 2,
        "rule_a_ok": True,
        "rule_b_ok": False,
        "volume_multiple": 1.2,
        "score": 80,
    }
    logic = build_buy_logic(detail, cfg)
    assert logic["filter_ok"] is False
    assert logic["buy_signal"] is False
    vol_step = next(s for s in logic["steps"] if s["id"] == "volume_multiple")
    assert vol_step["pass"] is False
