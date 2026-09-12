# -*- coding: utf-8 -*-
"""板块近2月涨停 / 本轮起涨点分析单元测试。"""

from types import SimpleNamespace

from backend_api.utils import industry_board_query as q


def _meta_patch(monkeypatch):
    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda *a, **k: {
            "board_code": "881101",
            "board_name": "测试板",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(
        q,
        "list_board_constituent_codes",
        lambda *a, **k: [
            {"code": "600519", "name": "贵州茅台"},
            {"code": "300001", "name": "特锐德"},
            {"code": "000001", "name": "平安银行"},
            {"code": "000002", "name": "万科A"},
        ],
    )


def test_fetch_board_recent_limit_up_stocks_empty_constituents(monkeypatch):
    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda *a, **k: {
            "board_code": "881101",
            "board_name": "测试板",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(q, "list_board_constituent_codes", lambda *a, **k: [])

    out = q.fetch_board_recent_limit_up_stocks(
        SimpleNamespace(), "industry", "881101", days=60
    )
    assert out is not None
    assert out["board_code"] == "881101"
    assert out["total"] == 0
    assert out["stocks"] == []
    assert out["constituent_count"] == 0
    assert out["days"] == 60
    assert out["wave_start_mode"] == "board_start"


def test_board_start_wave_and_stats_from_wave(monkeypatch):
    """2026-02-01 仅1只；2026-02-10 起两只同日涨停 → 起涨点 02-10。"""
    _meta_patch(monkeypatch)

    events = [
        ("600519", "2026-02-01"),  # 单只，不构成启动
        ("600519", "2026-02-10"),
        ("300001", "2026-02-10"),
        ("600519", "2026-02-11"),
        ("600519", "2026-02-12"),
        ("000001", "2026-02-20"),
    ]

    class _Result:
        def fetchall(self):
            return list(events)

    class _DB:
        def execute(self, sql, params=None):
            assert isinstance(params["start_date"], str)
            assert params["main_thr"] == 9.8
            assert params["gem_thr"] == 19.8
            return _Result()

    out = q.fetch_board_recent_limit_up_stocks(
        _DB(), "industry", "881101", days=60, wave_start_mode="board_start", start_min_count=2
    )
    assert out["wave_start_date"] == "2026-02-10"
    assert out["wave_start_day_limit_up_count"] == 2
    assert out["peak_limit_up_count"] == 2
    assert out["total"] == 3
    by_code = {s["code"]: s for s in out["stocks"]}
    assert "600519" in by_code
    # 起涨后：10/11/12 三板，连板≈3
    assert by_code["600519"]["limit_up_count"] == 3
    assert by_code["600519"]["max_consecutive"] == 3
    assert by_code["600519"]["first_limit_up_date"] == "2026-02-10"
    # 02-01 的单板不应计入自起涨统计
    assert by_code["300001"]["limit_up_count"] == 1
    assert by_code["000001"]["limit_up_count"] == 1


def test_leader_first_wave(monkeypatch):
    _meta_patch(monkeypatch)
    events = [
        ("000001", "2026-02-05"),
        ("000001", "2026-02-06"),
        ("600519", "2026-02-08"),
        ("600519", "2026-02-09"),
        ("600519", "2026-02-10"),
        ("300001", "2026-02-10"),
    ]

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchall=lambda: list(events))

    out = q.fetch_board_recent_limit_up_stocks(
        _DB(),
        "concept",
        "881101",
        days=60,
        wave_start_mode="leader_first",
        # 自动龙头应为 600519（3次）
    )
    assert out["leader_code"] == "600519"
    assert out["wave_start_date"] == "2026-02-08"
    by_code = {s["code"]: s for s in out["stocks"]}
    assert "000001" not in by_code  # 龙头首板前的涨停不计入
    assert by_code["600519"]["limit_up_count"] == 3


def test_scan_window_includes_all(monkeypatch):
    _meta_patch(monkeypatch)
    events = [
        ("600519", "2026-02-01"),
        ("300001", "2026-02-15"),
    ]

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchall=lambda: list(events))

    out = q.fetch_board_recent_limit_up_stocks(
        _DB(), "industry", "881101", days=60, wave_start_mode="scan_window"
    )
    assert out["wave_start_date"] == out["scan_start_date"]
    assert out["total"] == 2


def test_fetch_board_recent_limit_up_stocks_missing_board(monkeypatch):
    monkeypatch.setattr(q, "resolve_board_for_roles", lambda *a, **k: None)
    assert q.fetch_board_recent_limit_up_stocks(SimpleNamespace(), "industry", "NOPE") is None
