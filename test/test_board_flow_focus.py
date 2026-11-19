"""单板块资金位置与相对轮动：排名、日期回退、轨迹截断、缺数据不猜信号。"""

from backend_api.utils.board_flow_focus import build_board_flow_focus


def _flow(*rows):
    return list(rows)


def _row(code, name, date, change, net):
    return {
        "board_code": code,
        "board_name": name,
        "trade_date": date,
        "change_percent": change,
        "main_net_inflow": net,
    }


def _points(n, start_quadrant="lagging"):
    quads = ["lagging", "improving", "leading", "weakening"]
    out = []
    for i in range(n):
        out.append(
            {
                "trade_date": f"2026-10-{(i % 28) + 1:02d}",
                "rs_ratio": 90 + i,
                "rs_momentum": 95 + i * 0.1,
                "quadrant": quads[i % 4],
            }
        )
    out[-1]["quadrant"] = start_quadrant
    return out


def test_focus_ranks_the_board_and_keeps_last_15_trail_points():
    points = []
    for i in range(20):
        day = 1 + i
        points.append(
            {
                "trade_date": f"2026-11-{day:02d}" if day <= 18 else "2026-11-18",
                "rs_ratio": 100 + i * 0.1,
                "rs_momentum": 99 + i * 0.1,
                "quadrant": "leading" if i >= 18 else "improving",
            }
        )
    # 11-19 晚于资金日，不能进轨迹
    points.append(
        {
            "trade_date": "2026-11-19",
            "rs_ratio": 120,
            "rs_momentum": 120,
            "quadrant": "leading",
        }
    )
    payload = build_board_flow_focus(
        "881001",
        _flow(
            _row("881001", "半导体", "2026-11-18", 3.2, 2.5e8),
            _row("881002", "银行", "2026-11-18", -1.1, -8e8),
            _row("881003", "电力", "2026-11-18", 0.4, 1e8),
            _row("881001", "半导体", "2026-11-17", 1.0, 1e8),
        ),
        points,
        requested_date="2026-11-18",
    )
    assert payload["available"] is True
    assert payload["trade_date"] == "2026-11-18"
    assert payload["date_note"] == ""
    flow = payload["flow"]
    assert flow["change_percent"] == 3.2
    assert flow["main_net_yi"] == 2.5
    assert flow["direction"] == "in"
    assert flow["net_rank"] == 1
    assert flow["change_rank"] == 1
    assert flow["universe"] == 3
    assert payload["rotation"]["quadrant"] == "leading"
    assert payload["rotation"]["label"] == "领先"
    assert len(payload["rotation"]["trail"]) == 15
    assert payload["rotation"]["trail"][-1]["trade_date"] <= "2026-11-18"
    assert payload["rotation"]["trail"][0]["trade_date"] < payload["rotation"]["trail"][-1]["trade_date"]
    assert payload["signal"]["signal_key"] == "main_uptrend"
    assert payload["signal"]["signal_label"] == "主升确认"


def test_focus_falls_back_to_latest_flow_on_or_before_requested_date():
    payload = build_board_flow_focus(
        "881002",
        _flow(
            _row("881001", "半导体", "2026-11-13", 1.0, 3e8),
            _row("881002", "银行", "2026-11-13", -0.5, -2e8),
            _row("881001", "半导体", "2026-11-18", 2.0, 4e8),
        ),
        [
            {"trade_date": "2026-11-13", "rs_ratio": 101.2, "rs_momentum": 99.1, "quadrant": "weakening"},
            {"trade_date": "2026-11-18", "rs_ratio": 110, "rs_momentum": 110, "quadrant": "leading"},
        ],
        requested_date="2026-11-14",
    )
    assert payload["trade_date"] == "2026-11-13"
    assert "2026-11-13" in payload["date_note"]
    assert payload["flow"]["net_rank"] == 2
    assert payload["flow"]["universe"] == 2
    assert payload["rotation"]["trade_date"] == "2026-11-13"
    assert payload["rotation"]["quadrant"] == "weakening"
    assert payload["signal"]["signal_key"] == "ebb_exit"


def test_focus_keeps_flow_when_rotation_is_missing():
    payload = build_board_flow_focus(
        "881001",
        _flow(_row("881001", "半导体", "2026-11-18", 1.2, 2e8)),
        [],
        requested_date="2026-11-18",
    )
    assert payload["available"] is True
    assert payload["flow"]["main_net_yi"] == 2
    assert payload["rotation"]["available"] is False
    assert payload["rotation"]["trail"] == []
    assert "轮动" in payload["rotation"]["note"]
    assert payload["signal"]["signal_key"] == "uncovered"


def test_focus_without_flow_does_not_guess_a_signal():
    payload = build_board_flow_focus(
        "881001",
        [],
        [
            {"trade_date": "2026-11-18", "rs_ratio": 103, "rs_momentum": 101, "quadrant": "leading"},
        ],
        board_kind="concept",
        requested_date="2026-11-18",
    )
    assert payload["available"] is False
    assert payload["flow"] is None
    assert "概念" in payload["note"]
    assert payload["signal"]["signal_key"] == "uncovered"
    assert payload["rotation"]["trail"] == []


def test_latest_day_is_used_when_no_date_is_requested():
    payload = build_board_flow_focus(
        "881003",
        _flow(
            _row("881003", "电力", "2026-11-12", 0.2, 5e7),
            _row("881003", "电力", "2026-11-18", -0.4, -1e8),
            _row("881004", "煤炭", "2026-11-18", 1.5, 3e8),
        ),
        [
            {"trade_date": "2026-11-18", "rs_ratio": 98, "rs_momentum": 97, "quadrant": "lagging"},
        ],
    )
    assert payload["trade_date"] == "2026-11-18"
    assert payload["date_note"] == ""
    assert payload["flow"]["direction"] == "out"
    assert payload["flow"]["net_rank"] == 2
    assert payload["flow"]["change_rank"] == 2
    assert payload["signal"]["signal_key"] == "bleeding"
