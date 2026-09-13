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
