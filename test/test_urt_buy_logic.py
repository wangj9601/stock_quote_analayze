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
        "structure_rr_hard_gate_enabled": False,
        "overheat_hard_gate_enabled": False,
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
        "ma_bull_mid_gate_ok": True,
        "buy_signal": True,
        "filter_reason": "ok",
        "score_detail": {"parts": {"ma_bull": {"score": 7.5}}},
    }
    logic = build_buy_logic(detail, cfg)
    assert logic["buy_signal"] is True
    assert logic["filter_ok"] is True
    assert logic["score_ok"] is True
    assert logic["formula"].startswith("买点")
    ids = [s["id"] for s in logic["steps"]]
    assert ids == [
        "above_ma",
        "yang",
        "volume_multiple",
        "yang_medium",
        "ma_bull",
        "ma_bull_mid_gate",
        "min_score",
    ]
    assert all(s["pass"] for s in logic["steps"])
    mid = next(s for s in logic["steps"] if s["id"] == "yang_medium")
    assert mid["required"] is False
    bull = next(s for s in logic["steps"] if s["id"] == "ma_bull")
    assert bull["required"] is False


def test_build_buy_logic_fail_volume():
    cfg = {
        "ma_period": 20,
        "volume_multiple": 2.5,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "use_turnover": False,
        "use_volume_ratio": False,
        "structure_rr_hard_gate_enabled": False,
        "overheat_hard_gate_enabled": False,
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


def test_build_buy_logic_medium_yang_and_ma_bull_hard():
    cfg = {
        "ma_period": 20,
        "volume_multiple": 2.5,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "use_yang_medium": True,
        "require_ma_bull": True,
        "yang_medium_rules": [
            {"window": 10, "min_up_days": 6},
            {"window": 15, "min_up_days": 8},
            {"window": 20, "min_up_days": 10},
        ],
        "ma_bull_periods": [5, 10, 20],
        "structure_rr_hard_gate_enabled": False,
        "overheat_hard_gate_enabled": False,
    }
    detail = {
        "close": 10.5,
        "ma20": 10.0,
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "yang_count_10": 5,
        "yang_count_15": 8,
        "yang_count_20": 10,
        "yang_medium_ok": False,
        "ma_bull_ok": False,
        "ma5": 10.0,
        "ma10": 10.1,
        "ma20_stack": 10.2,
        "rule_a_ok": True,
        "rule_b_ok": True,
        "volume_multiple": 2.8,
        "score": 86,
    }
    logic = build_buy_logic(detail, cfg)
    assert logic["filter_ok"] is False
    mid = next(s for s in logic["steps"] if s["id"] == "yang_medium")
    assert mid["required"] is True and mid["pass"] is False
    bull = next(s for s in logic["steps"] if s["id"] == "ma_bull")
    assert bull["required"] is True and bull["pass"] is False
    assert "中期阳线" in logic["formula_detail"]
    assert "多头" in logic["formula_detail"]


def test_build_buy_logic_structure_hard_gate_blocks():
    cfg = {
        "ma_period": 20,
        "volume_multiple": 3.0,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "structure_rr_hard_gate_enabled": True,
        "overheat_hard_gate_enabled": False,
        "structure_hang_min_upside_pct": 0.08,
    }
    detail = {
        "close": 10.5,
        "ma20": 10.0,
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "rule_a_ok": True,
        "rule_b_ok": True,
        "volume_multiple": 3.5,
        "score": 86,
        "filter_ok": True,
        "score_ok": True,
        "structure_gate_ok": False,
        "structure_hard_gate": {"blocked": True, "reasons": ["悬空离支撑"]},
    }
    logic = build_buy_logic(detail, cfg)
    assert logic["buy_signal"] is False
    assert logic["structure_gate_ok"] is False
    gate = next(s for s in logic["steps"] if s["id"] == "structure_hard_gate")
    assert gate["required"] is True and gate["pass"] is False
    assert "悬空" in gate["actual"]


def test_build_buy_logic_hydrates_from_score_detail_trace_row():
    """模拟 urt_signal_trace 回放：顶层缺 ma5/中期阳/过热，仅 score_detail 有。"""
    cfg = {
        "ma_period": 20,
        "volume_multiple": 2.5,
        "min_score": 70,
        "yang_rule_a": {"window": 4, "min_up_days": 3},
        "yang_rule_b": {"window": 5, "min_up_days": 4},
        "use_yang_medium": True,
        "require_ma_bull": True,
        "yang_medium_rules": [
            {"window": 10, "min_up_days": 6},
            {"window": 15, "min_up_days": 8},
            {"window": 20, "min_up_days": 10},
        ],
        "ma_bull_periods": [5, 10, 20],
        "structure_rr_hard_gate_enabled": False,
        "overheat_hard_gate_enabled": True,
        "overheat_lookback_days": 10,
        "overheat_hard_pct": 0.25,
        "overheat_bias_hard_pct": 0.20,
    }
    # 表列仅有 ma20 / 短阳 / 量能；扩展字段只在 score_detail
    detail = {
        "close": 31.8,
        "ma20": 31.5935,
        "above_ma20": True,
        "yang_count_4": 3,
        "yang_count_5": 4,
        "rule_a_ok": True,
        "rule_b_ok": True,
        "volume_multiple": 3.2,
        "score": 82,
        "buy_signal": False,
        "score_detail": {
            "inputs": {
                "ma5": 32.1,
                "ma10": 31.9,
                "yang_count_10": 7,
                "yang_count_15": 9,
                "yang_count_20": 11,
            },
            "parts": {
                "yang_medium": {
                    "ok": True,
                    "items": [
                        {"window": 10, "count": 7, "min_up_days": 6},
                        {"window": 15, "count": 9, "min_up_days": 8},
                        {"window": 20, "count": 11, "min_up_days": 10},
                    ],
                },
                "ma_bull": {
                    "ok": False,
                    "bear_ok": False,
                    "ma5": 32.1,
                    "ma10": 31.9,
                    "ma20_stack": 31.5935,
                },
            },
            "ret_from_low_n": 0.12,
            "ma20_bias": 0.0065,
            "overheat_lookback_days": 10,
            "overheat_hard_gate": {"blocked": False, "reasons": []},
        },
    }
    logic = build_buy_logic(detail, cfg)
    mid = next(s for s in logic["steps"] if s["id"] == "yang_medium")
    assert "10日阳=7" in mid["actual"] and "None" not in mid["actual"]
    assert mid["pass"] is True
    bull = next(s for s in logic["steps"] if s["id"] == "ma_bull")
    assert "MA5=32.1" in bull["actual"] and "MA10=31.9" in bull["actual"]
    assert "None" not in bull["actual"]
    assert bull["pass"] is False
    oh = next(s for s in logic["steps"] if s["id"] == "overheat_hard_gate")
    assert "涨幅=12.0%" in oh["actual"]
    assert "乖离=0.7%" in oh["actual"]
    assert "—" not in oh["actual"]
