"""推荐简报：评分/防追高/分散/导出单元测试。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime
from decimal import Decimal
import json

from backend_core.recommend.scoring import (
    apply_anti_chase,
    apply_diversification,
    compute_recommend_score,
    pick_role_from_tags,
)
from backend_core.recommend.kpi import compute_brief_concentration_kpi
from backend_core.recommend.export import build_recommend_excel
from backend_core.recommend.store import sanitize_brief_json


def test_sanitize_brief_json_dates_and_decimal():
    payload = {
        "slope_asof_date": date(2026, 9, 12),
        "generated": datetime(2026, 9, 12, 15, 30, 0),
        "amt": Decimal("12.5"),
        "nested": [{"trade_date": date(2026, 9, 10), "nan": float("nan")}],
    }
    clean = sanitize_brief_json(payload)
    assert clean["slope_asof_date"] == "2026-09-12"
    assert clean["generated"].startswith("2026-09-12")
    assert clean["amt"] == 12.5
    assert clean["nested"][0]["trade_date"] == "2026-09-10"
    assert clean["nested"][0]["nan"] is None
    # 必须可被标准 json 编码
    json.dumps(clean)


def test_role_bonus_and_score():
    assert pick_role_from_tags([{"label": "龙头", "id": "board_leader"}])[0] == "leader"
    assert pick_role_from_tags([{"label": "中军"}])[0] == "mid"
    s, d = compute_recommend_score(
        strategies=["urt", "gms"],
        best_score=80,
        advice_action="buy",
        role="leader",
        board_weak=False,
    )
    assert s > 30
    assert d["resonance"] == 20
    assert d["role_bonus"] > 0
    assert "total" in d
    s2, d2 = compute_recommend_score(
        strategies=["urt", "gms"],
        best_score=80,
        advice_action="buy",
        role="leader",
        board_weak=True,
    )
    assert s2 < s  # 板弱角色不加分
    assert d2["role_bonus"] == 0
    assert d2["role_zeroed_by_board_weak"] is True


def test_anti_chase_limit_up():
    action, reasons = apply_anti_chase(
        action="buy",
        quote={"is_limit_up": True, "close": 10},
        advice={"buy_zone": {"price": 9.5}},
    )
    assert action == "watch"
    assert "limit_up" in reasons


def test_anti_chase_far_above_zone():
    action, reasons = apply_anti_chase(
        action="buy",
        quote={"is_limit_up": False, "close": 12},
        advice={"buy_zone": {"price": 10, "high": 10.2}},
    )
    assert action == "watch"
    assert "far_above_buy_zone" in reasons


def test_diversification_caps():
    items = []
    for i in range(5):
        items.append(
            {
                "code": f"00000{i}",
                "action": "buy",
                "stance": "买入",
                "board_code": "B1" if i < 3 else "B2",
                "recommend_score": 100 - i,
                "constraint_reasons": [],
            }
        )
    # also add boards beyond theme cap
    for i in range(5, 10):
        items.append(
            {
                "code": f"00001{i}",
                "action": "buy",
                "stance": "买入",
                "board_code": f"T{i}",
                "recommend_score": 50 - i,
                "constraint_reasons": [],
            }
        )
    out = apply_diversification(items, max_per_board=2, max_theme_boards=3)
    buys = [x for x in out if x["action"] == "buy"]
    # B1 最多 2；主题板最多 3
    assert sum(1 for x in buys if x["board_code"] == "B1") <= 2
    assert len({x["board_code"] for x in buys}) <= 3


def test_kpi_concentration():
    items = [
        {"action": "buy", "board_code": "A", "role": "leader"},
        {"action": "buy", "board_code": "A", "role": "mid"},
        {"action": "buy", "board_code": "B", "role": "normal"},
        {"action": "watch", "board_code": "C", "role": "leader"},
    ]
    kpi = compute_brief_concentration_kpi(items)
    assert kpi["executable_count"] == 3
    assert kpi["board_counts"]["A"] == 2
    assert kpi["board_hhi"] > 0


def test_export_xlsx(tmp_path):
    brief = {
        "horizon": "daily",
        "asof_date": "2026-09-12",
        "plan_for": "2026-09-12",
        "market_stance": "neutral",
        "summary": {"disclaimer": "规则合成参考，非投资建议"},
        "items": [
            {
                "code": "000001",
                "name": "测试",
                "action": "buy",
                "stance": "买入",
                "primary_strategy": "urt",
                "strategies": ["urt"],
                "role_label": "龙头",
                "board_name": "银行",
                "recommend_score": 40,
                "buy_zone": {"price": 10},
                "stop_zone": {"price": 9},
                "summary": "测试摘要",
            },
            {
                "code": "000002",
                "name": "观察票",
                "action": "watch",
                "stance": "观察",
                "primary_strategy": "gms",
                "strategies": ["gms"],
                "role_label": "普通",
                "recommend_score": 10,
            },
        ],
        "risk_observe": [{"code": "600000", "name": "风险", "note": "破支撑关注"}],
        "kpi": {"board_hhi": 0.5},
    }
    path = build_recommend_excel(brief, output_dir=str(tmp_path))
    assert os.path.exists(path)
    assert path.endswith(".xlsx")


def test_node_registry_has_recommend():
    from backend_core.data_collectors.workflow.node_registry import get_node

    n = get_node("stock_recommend_brief")
    assert n is not None
    assert n.key == "stock_recommend_brief"


def test_node_registry_has_recommend_late():
    from backend_core.data_collectors.workflow.node_registry import get_node

    n = get_node("stock_recommend_brief_late")
    assert n is not None
    assert n.key == "stock_recommend_brief_late"


def test_normalize_minmax_and_rpe():
    from backend_core.recommend.normalize import (
        apply_normalized_best_score,
        map_rpe_z_to_raw,
        normalize_strategy_scores,
    )

    assert 50 < map_rpe_z_to_raw(2.0) <= 100
    by = {
        "urt": [{"code": "1", "score": 10}, {"code": "2", "score": 90}],
        "sbbr": [{"code": "3"}],
        "rpe": [{"code": "4", "score": 1.5}],
    }
    normed = normalize_strategy_scores(by)
    urt_norms = sorted(r["quality_norm"] for r in normed["urt"])
    assert urt_norms[0] == 0.0
    assert urt_norms[1] == 100.0
    assert normed["sbbr"][0]["quality_norm"] == 50.0
    assert normed["rpe"][0]["quality_norm"] is not None

    merged = {
        "1": {
            "strategies": ["urt"],
            "strategy_rows": {"urt": normed["urt"][0]},
        },
        "2": {
            "strategies": ["urt", "csb"],
            "strategy_rows": {
                "urt": normed["urt"][1],
                "csb": {"quality_norm": 80.0, "quality_raw": 80.0},
            },
        },
    }
    apply_normalized_best_score(merged, regime_weights={"csb": 1.2, "urt": 0.8})
    assert merged["2"]["best_score"] is not None
    assert merged["2"]["best_score"] >= merged["1"]["best_score"]


def test_e_slope_mapping_and_combine():
    from backend_core.recommend.env import combine_e_slope, slope_to_e_multiplier

    assert slope_to_e_multiplier(None) == 1.0
    assert slope_to_e_multiplier(0.01) >= 0.9
    e_neg = slope_to_e_multiplier(-0.01)
    assert 0.2 <= e_neg <= 0.4
    info = combine_e_slope(0.9, -0.02)
    assert info["e_slope"] == min(info["e_market"], info["e_board"])
    assert "floor_hit" in info


def test_score_formula_eslope_and_sr():
    s1, d1 = compute_recommend_score(
        strategies=["urt"],
        best_score=100,
        advice_action="buy",
        role="mid",
        board_weak=False,
        e_slope=1.0,
        s_sr=0.0,
    )
    s2, d2 = compute_recommend_score(
        strategies=["urt"],
        best_score=100,
        advice_action="buy",
        role="mid",
        board_weak=False,
        e_slope=0.4,
        s_sr=0.0,
    )
    assert s2 < s1
    assert d2["e_slope"] == 0.4
    assert d2["s_base"] == d1["s_base"]
    s3, d3 = compute_recommend_score(
        strategies=["urt"],
        best_score=100,
        advice_action="buy",
        role="mid",
        board_weak=False,
        e_slope=1.0,
        s_sr=100.0,
    )
    assert s3 > s1
    assert d3["s_sr"] == 100.0
    assert "formula_version" in d3


def test_regime_primary_strategy():
    from backend_core.recommend.regime import (
        classify_regime,
        pick_primary_strategy,
        regime_quality_weights,
    )

    r_range = classify_regime(market_slope_20=-0.001)
    assert r_range["regime"] == "range"
    r_trend = classify_regime(market_slope_20=0.01)
    assert r_trend["regime"] == "trend"
    assert pick_primary_strategy(["urt", "gms", "csb"], "range") == "csb"
    assert pick_primary_strategy(["urt", "gms", "csb"], "trend") == "gms"
    wr = regime_quality_weights("range")
    wt = regime_quality_weights("trend")
    assert wr.get("csb", 1) >= wt.get("csb", 1)
    assert wt.get("gms", 1) >= wr.get("gms", 1)


def test_late_session_filters():
    from backend_core.recommend.daily_brief import apply_late_session_filters

    items = [
        {
            "code": "000001",
            "action": "buy",
            "stance": "买入",
            "buy_zone": {"high": 10.0, "price": 9.8},
            "constraint_reasons": [],
            "summary": "ok",
        },
        {
            "code": "000002",
            "action": "buy",
            "stance": "买入",
            "buy_zone": {"high": 10.0},
            "constraint_reasons": [],
            "summary": "ok",
        },
    ]
    quotes = {
        "000001": {"open": 10.0, "high": 11.0, "low": 9.9, "close": 10.05},  # 长上影
        "000002": {"open": 10.0, "high": 10.2, "low": 9.5, "close": 9.5},  # 假突破
    }
    out, n = apply_late_session_filters(items, quotes)
    assert n >= 1
    assert all(x["action"] == "watch" for x in out)
    reasons = set()
    for x in out:
        reasons.update(x.get("constraint_reasons") or [])
    assert "late_upper_shadow" in reasons or "late_false_break" in reasons


def test_sr_score_and_merge_advice():
    from backend_core.recommend.sr_levels import _score_sr, merge_advice_with_sr

    assert 0 <= _score_sr(10.0, 9.5, 11.0) <= 100
    advice = {"action": "buy", "buy_zone": None, "stop_zone": None}
    sr = {
        "ok": True,
        "s_sr": 70.0,
        "p_sup": 9.5,
        "p_res": 11.0,
        "buy_zone": {"low": 9.3, "high": 9.7, "price": 9.5},
        "stop_zone": {"price": 9.1},
        "take_profit": {"price": 11.0},
    }
    merged = merge_advice_with_sr(advice, sr)
    assert merged.get("buy_zone")
    assert merged.get("stop_zone")


def test_strategy_priority_includes_csb():
    from backend_core.recommend.config import STRATEGY_PRIORITY, strategy_priority_for_regime

    assert "csb" in STRATEGY_PRIORITY
    assert strategy_priority_for_regime("range")[0] == "csb"
    assert strategy_priority_for_regime("trend")[0] == "gms"
