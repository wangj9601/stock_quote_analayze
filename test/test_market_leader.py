# -*- coding: utf-8 -*-
"""市场总龙头 / 资金焦点识别。"""

from backend_core.market_review.market_leader import (
    build_capital_focus,
    pick_market_leader,
)
from backend_core.market_review.render import render_markdown


def test_empty_zt_pool_no_leader():
    out = pick_market_leader([], main_name="养殖业")
    assert out is None


def test_single_zt_is_leader():
    rows = [
        {
            "code": "001201",
            "name": "东瑞股份",
            "board_count": 1,
            "seal_fund": 3.4e7,
            "industry": "养殖业",
        }
    ]
    out = pick_market_leader(rows, main_name="养殖业")
    assert out["code"] == "001201"
    assert out["board_count"] == 1
    assert out["alternates"] == []
    assert any("主线" in r for r in out["reasons"])


def test_height_not_always_leader_when_mainline_seal_stronger():
    """高标边角 vs 主线强封：主线可凭封单+主线加分胜出。"""
    rows = [
        {
            "code": "002724",
            "name": "海洋王",
            "board_count": 4,
            "seal_fund": 1e6,
            "industry": "照明设备",
        },
        {
            "code": "600000",
            "name": "主线龙",
            "board_count": 3,
            "seal_fund": 8e8,
            "industry": "养殖业",
        },
        {
            "code": "600001",
            "name": "跟风A",
            "board_count": 3,
            "seal_fund": 2e7,
            "industry": "养殖业",
        },
        {
            "code": "600002",
            "name": "跟风B",
            "board_count": 3,
            "seal_fund": 1e7,
            "industry": "养殖业",
        },
    ]
    out = pick_market_leader(rows, main_name="养殖业")
    assert out["code"] == "600000"
    assert out["name"] == "主线龙"
    assert len(out["alternates"]) >= 1
    assert out["alternates"][0]["code"] in ("002724", "600001", "600002")


def test_capital_focus_from_flow_top():
    flow = [
        {"code": "300750", "name": "宁德时代", "net_inflow_yi": 18.79},
        {"code": "002463", "name": "沪电股份", "net_inflow_yi": 8.69},
    ]
    zt_codes = {"001201"}
    cf = build_capital_focus(flow, zt_codes)
    assert cf["code"] == "300750"
    assert cf["is_limit_up"] is False
    assert cf["source"] == "flow_top"


def test_same_ticket_flags_both():
    rows = [
        {
            "code": "300750",
            "name": "宁德时代",
            "board_count": 2,
            "seal_fund": 5e8,
            "industry": "电池",
        }
    ]
    leader = pick_market_leader(rows, main_name="电池")
    flow = [{"code": "300750", "name": "宁德时代", "net_inflow_yi": 20.0}]
    cf = build_capital_focus(flow, {"300750"})
    assert leader["code"] == cf["code"]
    leader["same_as_capital_focus"] = leader["code"] == cf["code"]
    assert leader["same_as_capital_focus"] is True
    assert cf["is_limit_up"] is True


def test_render_section_market_leader():
    snap = {
        "trade_date": "2026-10-21",
        "vol_trillion": 1.43,
        "cb_count": 16,
        "height": 4,
        "prev_cb_return": 2.39,
        "lo_value": -6.55,
        "hi_value": 87.06,
        "sp_value": 93.61,
        "limit_source": "zt_pool_em",
        "season": "夏",
        "viewpoint_md": "测",
        "advice_md": "建议",
        "hard_gates": {"rate": "1/5", "items": []},
        "rules_json": {"summary": "摘要", "signals": [], "quadrant": "—", "sp_eve": False, "delta": {}},
        "mainline_json": {
            "policy": "concept_primary",
            "rows": [],
            "summary": "无",
            "industry_confirm": {"rows": [], "summary": "无", "count": 0},
            "sector": {
                "ladder": {"b2": 12, "b3": 1, "b4plus": 3},
                "height_stock": {"code": "002724", "name": "海洋王", "board_count": 4},
                "market_leader": {
                    "code": "600000",
                    "name": "主线龙",
                    "board_count": 3,
                    "seal_yi": 8.0,
                    "score": 412.0,
                    "reasons": ["连板 3", "主线匹配", "封单靠前"],
                    "alternates": [
                        {"code": "002724", "name": "海洋王", "board_count": 4, "score": 400.0}
                    ],
                    "same_as_capital_focus": False,
                },
                "capital_focus": {
                    "code": "300750",
                    "name": "宁德时代",
                    "net_inflow_yi": 18.79,
                    "source": "flow_top",
                    "is_limit_up": False,
                },
            },
        },
        "season_detail": {"season": "夏", "cb": 16, "height": 4, "prev_cb_return": 2.39},
    }
    md = render_markdown(snap)
    assert "市场总龙头与资金焦点" in md
    assert "主线龙" in md
    assert "宁德时代" in md
    assert "最高板" in md
