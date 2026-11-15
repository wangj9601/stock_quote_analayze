"""收盘行业资金气泡：净流入、流入减流出回退、缺涨跌幅丢弃、轮动叠加。"""

from backend_api.utils.board_flow_bubbles import build_fund_bubbles


def test_bubble_uses_main_net_and_splits_direction():
    payload = build_fund_bubbles(
        "2026-11-13",
        [
            {
                "board_code": "881001",
                "board_name": "半导体",
                "change_percent": 3.2,
                "main_net_inflow": 2.5e8,
            },
            {
                "board_code": "881002",
                "board_name": "银行",
                "change_percent": -1.1,
                "main_net_inflow": -8e8,
            },
            {
                "board_code": "881003",
                "board_name": "空白",
                "change_percent": None,
                "main_net_inflow": 1e8,
            },
        ],
    )
    assert payload["trade_date"] == "2026-11-13"
    assert payload["board_count"] == 2
    assert payload["in_count"] == 1
    assert payload["out_count"] == 1
    assert payload["items"][0]["board_code"] == "881002"
    assert payload["items"][0]["direction"] == "out"
    assert payload["items"][0]["main_net_yi"] == -8
    assert payload["items"][1]["direction"] == "in"
    assert payload["items"][1]["change_percent"] == 3.2


def test_bubble_falls_back_to_inflow_minus_outflow():
    payload = build_fund_bubbles(
        "2026-11-13",
        [
            {
                "board_code": "881010",
                "board_name": "电力",
                "change_percent": 0.4,
                "main_net_inflow": None,
                "inflow_amount": 3e8,
                "outflow_amount": 1e8,
            }
        ],
    )
    assert payload["items"][0]["main_net_inflow"] == 2e8
    assert payload["items"][0]["direction"] == "in"
    assert payload["items"][0]["main_net_yi"] == 2


def test_empty_bubbles_carry_a_note():
    payload = build_fund_bubbles(None, [])
    assert payload["items"] == []
    assert payload["note"]


def _rotation_payload():
    return {
        "benchmark_name": "沪深300",
        "window": 10,
        "note": "",
        "boards": [
            {
                "board_code": "881001",
                "board_name": "半导体",
                "points": [
                    {"trade_date": "2026-11-12", "rs_ratio": 104.1, "rs_momentum": 101.2, "quadrant": "leading"},
                    {"trade_date": "2026-11-13", "rs_ratio": 103.2, "rs_momentum": 99.4, "quadrant": "weakening"},
                    {"trade_date": "2026-11-16", "rs_ratio": 101.0, "rs_momentum": 98.0, "quadrant": "weakening"},
                ],
            }
        ],
    }


def test_bubbles_take_the_rotation_point_of_their_own_trade_date():
    payload = build_fund_bubbles(
        "2026-11-13",
        [
            {
                "board_code": "881001",
                "board_name": "半导体",
                "change_percent": -1.6,
                "main_net_inflow": -1.2e8,
            }
        ],
        rotation=_rotation_payload(),
    )
    item = payload["items"][0]
    # 不能用 11-16 的点：气泡日是 11-13
    assert item["rotation_trade_date"] == "2026-11-13"
    assert item["rotation_quadrant"] == "weakening"
    assert item["rotation_label"] == "转弱"
    assert item["rs_momentum"] == 99.4
    assert item["signal_key"] == "ebb_exit"
    assert payload["rotation"]["enabled"] is True
    assert payload["flow_rotation"]["quadrant_counts"]["weakening"] == 1


def test_bubble_without_rotation_point_is_marked_uncovered():
    payload = build_fund_bubbles(
        "2026-11-13",
        [
            {
                "board_code": "881099",
                "board_name": "新板块",
                "change_percent": 0.6,
                "main_net_inflow": 2e8,
            }
        ],
        rotation=_rotation_payload(),
    )
    item = payload["items"][0]
    assert item["rotation_quadrant"] is None
    assert item["signal_key"] == "uncovered"
    assert payload["flow_rotation"]["uncovered"] == 1


def test_bubbles_without_rotation_keep_pure_flow_view():
    payload = build_fund_bubbles(
        "2026-11-13",
        [
            {
                "board_code": "881001",
                "board_name": "半导体",
                "change_percent": 3.2,
                "main_net_inflow": 2.5e8,
            }
        ],
    )
    assert payload["rotation"]["enabled"] is False
    assert payload["rotation"]["note"] == "未叠加相对轮动"
    assert payload["items"][0]["signal_key"] == "uncovered"
