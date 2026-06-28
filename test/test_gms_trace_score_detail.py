"""GMS 信号追溯：得分明细与选股页对齐"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.stock.gms_trace_routes import (
    _calculator_score_detail_meta,
    _row_dict_to_score_detail,
)
from backend_api.stock.stock_screening_routes import _inject_gms_score_detail_meta


class TestGmsTraceScoreDetail:
    def test_calculator_meta_has_weight_keys(self):
        config = {
            "scoring": {
                "mechanism": "tiered_dual_max",
                "accumulation": {"s_threshold": 85, "a_threshold": 70},
                "momentum": {"full_threshold": 90, "batch_threshold": 80},
            }
        }
        meta = _calculator_score_detail_meta(config)
        assert "weight_acc_fz" in meta
        assert "acc_fz_tiers" in meta
        assert meta["accumulation_s_threshold"] == 85

    def test_row_dict_to_score_detail_includes_ma60_and_weights(self):
        config = {"scoring": {"mechanism": "tiered_dual_penalty"}}
        calc_meta = {
            "weight_acc_fz": 30,
            "acc_fz_tiers": [2.5, 1.5],
            "accumulation_s_threshold": 85,
        }
        row = {
            "score_total": 75.0,
            "score_accumulation": 80.0,
            "score_momentum": 75.0,
            "ma60_d": 10.5,
            "d": 11.0,
            "delta": 0.5,
        }
        sd = _row_dict_to_score_detail(row, calc_meta, config)
        assert sd["ma60_d"] == 10.5
        assert sd["weight_acc_fz"] == 30
        assert sd["scoring_mechanism"] == "tiered_dual_penalty"
        assert sd["score_base_total"] == 80.0

    def test_inject_meta_fills_strategy_version(self):
        sd = {"score_total": 90}
        meta = {
            "strategy_config_id": 2,
            "strategy_config_name": "gms_penalty",
            "scoring_mechanism": "tiered_dual_penalty",
            "scoring_mechanism_label": "增强版·阶梯+减分",
        }
        out = _inject_gms_score_detail_meta(sd, meta)
        assert out["strategy_config_id"] == 2
        assert out["strategy_config_name"] == "gms_penalty"
        assert out["scoring_mechanism_label"] == "增强版·阶梯+减分"
