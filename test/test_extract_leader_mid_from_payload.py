"""extract_leader_mid_from_payload 单元测试。"""

from __future__ import annotations

from backend_core.board_roles.classify import ROLE_LEADER, ROLE_MID
from backend_core.board_roles.service import extract_leader_mid_from_payload


def test_extract_empty_payload():
    out = extract_leader_mid_from_payload(None)
    assert out["leaders"] == []
    assert out["mids"] == []
    assert out["board_code"] is None

    out2 = extract_leader_mid_from_payload({})
    assert out2["leaders"] == []
    assert out2["mids"] == []


def test_extract_leader_and_mid_sorted_by_score():
    payload = {
        "board_code": "BK0481",
        "board_name": "半导体",
        "board_code_source": "tonghuashun",
        "board_change_percent_est": 3.5,
        "stocks": [
            {
                "code": "2",
                "name": "中军乙",
                "change_percent": 4.0,
                "board_role": ROLE_MID,
                "board_role_score": 70,
                "role_reason": "中军跟涨",
            },
            {
                "code": "000001",
                "name": "龙头甲",
                "change_percent": 9.0,
                "board_role": ROLE_LEADER,
                "board_role_score": 90,
                "role_reason": "短线领涨",
            },
            {
                "code": "000003",
                "name": "普通",
                "change_percent": 1.0,
                "board_role": None,
                "board_role_score": 10,
            },
            {
                "code": "000004",
                "name": "中军甲",
                "change_percent": 5.0,
                "board_role": ROLE_MID,
                "board_role_score": 80,
                "role_reason": "中军跟涨",
            },
            {
                "code": "000005",
                "name": "龙头乙",
                "change_percent": 8.0,
                "board_role": ROLE_LEADER,
                "board_role_score": 85,
                "role_reason": "短线领涨",
            },
        ],
    }
    out = extract_leader_mid_from_payload(payload)
    assert out["board_code"] == "BK0481"
    assert out["board_name"] == "半导体"
    assert out["board_code_source"] == "tonghuashun"
    assert out["board_change_percent_est"] == 3.5
    assert [x["code"] for x in out["leaders"]] == ["000001", "000005"]
    assert [x["code"] for x in out["mids"]] == ["000004", "000002"]
    assert out["leaders"][0]["board_role_label"] == "龙头"
    assert out["mids"][0]["board_role_label"] == "中军"
    assert out["mids"][1]["code"] == "000002"  # 短码补零


def test_extract_skips_blank_code():
    payload = {
        "board_code": "X",
        "board_name": "X",
        "stocks": [
            {"code": "", "name": "空", "board_role": ROLE_LEADER, "board_role_score": 99},
            {"code": "600000", "name": "有", "board_role": ROLE_LEADER, "board_role_score": 1},
        ],
    }
    out = extract_leader_mid_from_payload(payload)
    assert len(out["leaders"]) == 1
    assert out["leaders"][0]["code"] == "600000"
