# -*- coding: utf-8 -*-
"""LDS 龙头战法：带动性 / 身份 / 右侧。"""

from backend_core.strategies.lds.detector import (
    evaluate_candidate,
    merge_hits_by_code,
    score_drive,
    score_follow,
    score_identity,
    score_liquidity,
    score_recog,
    score_sync,
)


def test_follow_full_when_zt_enough():
    assert score_follow(zt_n=3, up_ratio=0.3, cfg={}) >= 95
    assert score_follow(zt_n=0, up_ratio=0.0, cfg={}) < 20


def test_lonely_rejected():
    cand = {
        "code": "002724",
        "name": "海洋王",
        "role": "board_leader",
        "board_code": "881101",
        "board_name": "照明",
        "board_count": 4,
        "change_percent": 10.0,
        "amount": 1e8,
        "mv_yi": 40.0,
        "board_role_score": 20.0,
        "zt_n": 1,
        "up_ratio": 0.1,
        "board_median_chg": -1.0,
        "had_bomb_weak_board": True,
        "amount_pctile": 30.0,
        "height_pctile": 100.0,
        "seal_yi": 0.1,
        "is_height_stock": True,
        "net_inflow_yi": -1.0,
        "vol_ratio_actual": 0.8,
        "had_diverge": False,
        "on_mainline": True,
    }
    out = evaluate_candidate(cand, cfg={})
    assert out is None


def test_strong_board_leader_hits():
    cand = {
        "code": "600000",
        "name": "主线龙",
        "role": "board_leader",
        "board_code": "881001",
        "board_name": "养殖业",
        "board_count": 3,
        "change_percent": 10.0,
        "amount": 2e9,
        "mv_yi": 80.0,
        "board_role_score": 88.0,
        "zt_n": 5,
        "up_ratio": 0.75,
        "board_median_chg": 3.5,
        "had_bomb_weak_board": False,
        "amount_pctile": 85.0,
        "height_pctile": 80.0,
        "seal_yi": 5.0,
        "is_height_stock": False,
        "net_inflow_yi": 2.0,
        "vol_ratio_actual": 2.0,
        "had_diverge": True,
        "on_mainline": True,
        "is_primary": True,
    }
    out = evaluate_candidate(cand, cfg={})
    assert out is not None
    assert out["status"] == "hit"
    assert out["role"] == "board_leader"
    assert out["is_lonely"] is False
    assert out["identity_score"] >= 55
    assert out["watch_ready"] is True
    assert out["same_as_height"] is False


def test_height_alone_not_enough():
    """最高板但带动极差 → 不出 hit。"""
    cand = {
        "code": "002724",
        "name": "孤高标",
        "role": "market_leader",
        "board_code": "",
        "board_name": "",
        "board_count": 6,
        "change_percent": 10.0,
        "amount": 5e7,
        "mv_yi": 35.0,
        "board_role_score": 10.0,
        "zt_n": 1,
        "up_ratio": 0.05,
        "board_median_chg": -2.0,
        "had_bomb_weak_board": True,
        "amount_pctile": 20.0,
        "height_pctile": 100.0,
        "seal_yi": 0.05,
        "is_height_stock": True,
        "net_inflow_yi": -2.0,
        "vol_ratio_actual": 0.5,
        "had_diverge": False,
        "on_mainline": False,
        "is_primary": True,
        "market_leader_score": 400.0,
    }
    out = evaluate_candidate(cand, cfg={})
    assert out is None


def test_watch_ready_false_when_no_diverge_no_inflow():
    cand = {
        "code": "600001",
        "name": "观察龙",
        "role": "board_leader",
        "board_code": "881001",
        "board_name": "养殖业",
        "board_count": 2,
        "change_percent": 9.9,
        "amount": 1.5e9,
        "mv_yi": 60.0,
        "board_role_score": 80.0,
        "zt_n": 4,
        "up_ratio": 0.7,
        "board_median_chg": 2.0,
        "had_bomb_weak_board": False,
        "amount_pctile": 80.0,
        "height_pctile": 60.0,
        "seal_yi": 3.0,
        "is_height_stock": False,
        "net_inflow_yi": -5.0,
        "vol_ratio_actual": 0.9,
        "had_diverge": False,
        "on_mainline": True,
        "is_primary": True,
    }
    out = evaluate_candidate(cand, cfg={})
    assert out is not None
    assert out["status"] == "hit"
    assert out["watch_ready"] is False


def test_drive_components_weighted():
    a = score_follow(5, 0.8, {})
    b = score_sync(10.0, 3.0, had_bomb_weak_board=False, cfg={})
    c = 90.0
    d = score_drive(a, b, c, {})
    assert 0 <= d <= 100
    assert d > 70


def test_merge_hits_by_code_dedupes_boards():
    rows = [
        {
            "code": "002929",
            "name": "润建股份",
            "role": "board_leader",
            "board_code": "a",
            "board_name": "算力租赁",
            "identity_score": 80.05,
            "drive_score": 91.31,
            "watch_ready": False,
            "is_primary": True,
            "same_as_height": False,
            "board_count": 3,
            "identity_reasons": ["r1"],
            "watch_reasons": [],
            "detail": {},
        },
        {
            "code": "002929",
            "name": "润建股份",
            "role": "board_leader",
            "board_code": "b",
            "board_name": "信创",
            "identity_score": 79.64,
            "drive_score": 90.4,
            "watch_ready": True,
            "is_primary": True,
            "same_as_height": False,
            "board_count": 3,
            "identity_reasons": [],
            "watch_reasons": ["资金承接"],
            "detail": {},
        },
        {
            "code": "603278",
            "name": "大业股份",
            "role": "market_leader",
            "board_code": "",
            "board_name": "",
            "identity_score": 78.19,
            "drive_score": 94.5,
            "watch_ready": False,
            "is_primary": True,
            "same_as_height": False,
            "board_count": 4,
            "identity_reasons": [],
            "watch_reasons": [],
            "detail": {},
        },
        {
            "code": "603278",
            "name": "大业股份",
            "role": "board_leader",
            "board_code": "c",
            "board_name": "某板",
            "identity_score": 70.0,
            "drive_score": 80.0,
            "watch_ready": False,
            "is_primary": True,
            "same_as_height": False,
            "board_count": 4,
            "identity_reasons": [],
            "watch_reasons": [],
            "detail": {},
        },
    ]
    merged = merge_hits_by_code(rows)
    assert len(merged) == 2
    by = {r["code"]: r for r in merged}
    rj = by["002929"]
    assert "算力租赁" in (rj.get("board_name") or "")
    assert "信创" in (rj.get("board_name") or "")
    assert rj["watch_ready"] is True
    assert rj["identity_score"] == 80.05
    dy = by["603278"]
    assert dy["role"] == "market_leader"
    assert "某板" in (dy.get("board_name") or "") or (dy.get("detail") or {}).get("boards")
