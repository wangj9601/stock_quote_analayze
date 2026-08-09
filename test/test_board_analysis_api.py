# -*- coding: utf-8 -*-
"""板块分析聚合：过滤与编排冒烟。"""

from backend_core.analysis.board_signals import (
    _enrich_items,
    _filter_gms,
    _filter_rpe,
    _filter_sbbr,
    _filter_urt,
    _slim_reference_levels,
    _strategy_hit_cell,
    collect_leader_mid_strategy_hits,
)
from backend_core.analysis.trade_advice import build_trade_advice


def test_filters():
    # 默认 min_score=0：仅买点
    assert len(_filter_gms([{"left_buy_signal": True}, {"score_total": 80}])) == 1
    # 总分达标
    assert (
        len(
            _filter_gms(
                [{"left_buy_signal": True}, {"score_total": 80}],
                min_score=60,
            )
        )
        == 2
    )
    assert len(_filter_urt([{"buy_signal": True}, {"buy_signal": False}])) == 1
    entry, watch = _filter_sbbr(
        [{"entry_signal": True}, {"bottom_matched": True}, {"entry_signal": False}]
    )
    assert len(entry) == 1 and len(watch) == 1
    assert len(_filter_rpe([{"watch_only": True}, {"signal_type": "x"}])) == 1


def test_sbbr_advice_defense():
    adv = build_trade_advice(
        "sbbr",
        {
            "entry_signal": True,
            "entry_low": 8.5,
            "defense_low": 8.0,
            "defense_high": 8.2,
            "box_resistance": 9.5,
        },
    )
    assert adv["action"] == "buy"
    assert adv["stop_zone"]["basis"] == "defense"


def test_enrich_items_last_close():
    items = _enrich_items(
        "gms",
        [{"code": "000001", "left_buy_signal": True}],
        names={"000001": "平安银行"},
        ref_by_code={},
        last_close_by_code={"000001": 12.345},
    )
    assert items[0]["last_close"] == 12.35
    assert items[0]["name"] == "平安银行"


def test_strategy_hit_cell_labels():
    assert _strategy_hit_cell("gms", None)["hit"] is False
    g = _strategy_hit_cell("gms", {"buy_type": "左侧", "left_buy_signal": True})
    assert g["hit"] and g["label"] == "左侧"
    s = _strategy_hit_cell(
        "sbbr", None, watch_row={"bottom_matched": True, "code": "1"}
    )
    assert s["hit"] and s["label"] == "筑底"


def test_collect_leader_mid_strategy_hits_matrix(monkeypatch):
    """角色子集命中矩阵：不依赖真实 DB 策略引擎。"""

    def fake_payload(*_a, **_k):
        return {
            "board_code": "881101",
            "board_name": "测试板",
            "board_code_source": "tonghuashun",
            "board_change_percent_est": 1.2,
            "stocks": [
                {
                    "code": "600000",
                    "name": "龙头A",
                    "board_role": "leader",
                    "board_role_label": "龙头",
                    "board_role_score": 90,
                    "change_percent": 5.0,
                },
                {
                    "code": "600001",
                    "name": "中军B",
                    "board_role": "mid",
                    "board_role_label": "中军",
                    "board_role_score": 70,
                    "change_percent": 2.0,
                },
            ],
        }

    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        fake_payload,
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._levels_for_codes",
        lambda db, codes: {
            "600000": {
                "last_close": 10.5,
                "kde_support": 10.0,
                "kde_resistance": 11.2,
                "kde_ok": True,
                "reference_levels": {
                    "nearest_fib_support": 9.8,
                    "nearest_cam_resistance": 11.0,
                },
            },
            "600001": {
                "last_close": 8.2,
                "kde_support": 8.0,
                "kde_resistance": 8.8,
                "kde_ok": True,
                "reference_levels": {},
            },
        },
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_gms",
        lambda db, codes: [{"code": "600000", "buy_type": "左侧", "left_buy_signal": True}],
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_urt",
        lambda db, codes: [{"code": "600001", "buy_signal": True}],
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_sbbr",
        lambda db, codes: ([], [{"code": "600000", "bottom_matched": True}]),
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_rpe",
        lambda db, board_kind, board_code=None, board_codes=None: [
            {"code": "600000", "signal_type": "catch_up", "entry_signal": True},
            {"code": "999999", "signal_type": "lead", "watch_only": True},
        ],
    )

    out = collect_leader_mid_strategy_hits(
        db=None,
        board_kind="industry",
        board_code="881101",
    )
    assert out["role_count"] == 2
    assert out["leader_count"] == 1 and out["mid_count"] == 1
    by_code = {x["code"]: x for x in out["items"]}
    assert by_code["600000"]["hits"]["gms"]["hit"] is True
    assert by_code["600000"]["hits"]["sbbr"]["label"] == "筑底"
    assert by_code["600000"]["hits"]["rpe"]["hit"] is True
    assert by_code["600001"]["hits"]["urt"]["hit"] is True
    assert by_code["600001"]["hits"]["gms"]["hit"] is False
    assert by_code["600000"]["last_close"] == 10.5
    assert by_code["600000"]["kde_support"] == 10.0
    assert by_code["600000"]["reference_levels"]["nearest_fib_support"] == 9.8
    # RPE 整板结果中的非角色股不应出现在矩阵
    assert "999999" not in by_code


def test_slim_reference_levels_drops_heavy_fields():
    slim = _slim_reference_levels(
        {
            "ok": True,
            "nearest_fib_support": 1.0,
            "volume_profile": {"ok": True, "poc": 2.0, "bins": [1, 2, 3]},
            "fibonacci": {"swing_high": 3.0, "zigzag": [{"a": 1}]},
            "confluence_zones": {
                "ok": True,
                "nearest_support_zone": {"center": 1.1},
                "supports": [{"center": 1.1}],
            },
        }
    )
    assert slim["nearest_fib_support"] == 1.0
    assert "bins" not in slim["volume_profile"]
    assert "zigzag" not in slim["fibonacci"]
    assert slim["confluence_zones"]["nearest_support_zone"]["center"] == 1.1


def test_collect_leader_mid_all_boards(monkeypatch):
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._list_boards_for_kind",
        lambda db, board_kind, board_code_source="tonghuashun": [
            {"board_code": "881101", "board_name": "板A", "board_code_source": "tonghuashun"},
            {"board_code": "881102", "board_name": "板B", "board_code_source": "tonghuashun"},
        ],
    )

    def fake_payload(db, board_type, board_code, board_code_source=None, board_name=None, **_k):
        if board_code == "881101":
            return {
                "board_code": "881101",
                "board_name": "板A",
                "stocks": [
                    {
                        "code": "600000",
                        "name": "龙A",
                        "board_role": "leader",
                        "board_role_label": "龙头",
                        "board_role_score": 90,
                    }
                ],
            }
        return {
            "board_code": "881102",
            "board_name": "板B",
            "stocks": [
                {
                    "code": "600000",
                    "name": "龙A",
                    "board_role": "mid",
                    "board_role_label": "中军",
                    "board_role_score": 60,
                },
                {
                    "code": "600002",
                    "name": "中B",
                    "board_role": "mid",
                    "board_role_label": "中军",
                    "board_role_score": 55,
                },
            ],
        }

    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        fake_payload,
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._levels_for_codes",
        lambda db, codes: {},
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_gms",
        lambda db, codes: [],
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_urt",
        lambda db, codes: [],
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_sbbr",
        lambda db, codes: ([], []),
    )
    monkeypatch.setattr(
        "backend_core.analysis.board_signals._run_rpe",
        lambda db, board_kind, board_code=None, board_codes=None: [],
    )

    out = collect_leader_mid_strategy_hits(
        db=None, board_kind="industry", board_code="all"
    )
    assert out["board"]["all_boards"] is True
    assert out["board"]["board_count"] == 2
    assert out["role_count"] == 2  # 600000 去重 + 600002
    by_code = {x["code"]: x for x in out["items"]}
    assert by_code["600000"]["board_role"] == "leader"
    assert "板A" in by_code["600000"]["board_labels"]
    assert "板B" in by_code["600000"]["board_labels"]

    out2 = collect_leader_mid_strategy_hits(
        db=None,
        board_kind="industry",
        board_codes=["881101", "881102"],
    )
    assert out2["board"]["multi_boards"] is True
    assert out2["board"]["all_boards"] is False
    assert out2["board"]["board_count"] == 2
    assert out2["role_count"] == 2
