# -*- coding: utf-8 -*-
"""行业板块同花顺 ↔ 东财代码映射单测。"""

from datetime import datetime
from types import SimpleNamespace


def test_prefer_board_quote_prefers_fresher_when_quality_equal():
    from backend_api.utils import industry_board_query as q

    stale = {
        "change_percent": 2.08,
        "update_time": "2026-08-10 16:03:09",
        "quote_board_code": "881178",
        "volume": 555.58,
    }
    fresh = {
        "change_percent": 0.79,
        "update_time": "2026-09-02 15:36:16",
        "quote_board_code": "BK0740",
        "volume": 471.27,
    }
    picked = q._prefer_board_quote(stale, fresh)
    assert picked["quote_board_code"] == "BK0740"
    assert picked["update_time"] == "2026-09-02 15:36:16"


def test_resolve_industry_board_quote_uses_code_map():
    from backend_api.utils import industry_board_query as q

    by_code = {
        "881178": {
            "change_percent": 2.08,
            "update_time": "2026-08-10 16:03:09",
            "quote_board_code": "881178",
        },
        "BK0740": {
            "change_percent": 0.79,
            "update_time": "2026-09-02 15:36:16",
            "quote_board_code": "BK0740",
        },
    }
    by_name = {"教育": by_code["881178"]}
    quote = q._resolve_industry_board_quote(
        by_code,
        by_name,
        board_code="881178",
        board_name="教育",
        ths_to_em={"881178": "BK0740"},
        em_to_ths={"BK0740": "881178"},
    )
    assert quote["quote_board_code"] == "BK0740"
    assert quote["change_percent"] == 0.79


def test_rebuild_name_exact_maps(monkeypatch):
    from backend_api.utils import industry_board_code_map as m

    class FakeResult:
        def __init__(self, rows=None, rowcount=0):
            self._rows = rows or []
            self.rowcount = rowcount

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class FakeDb:
        def execute(self, sql, params=None):
            s = str(sql)
            params = params or {}
            if "FROM industry_board_basic_info" in s and "SELECT board_code" in s:
                return FakeResult(
                    [
                        ("881178", "教育", "tonghuashun"),
                        ("BK0740", "教育", "eastmoney"),
                        ("881101", "半导体", "tonghuashun"),
                        ("BK0477", "半导体", "eastmoney"),
                    ]
                )
            if "FROM concept_board_basic_info" in s and "SELECT board_code" in s:
                return FakeResult(
                    [
                        ("885801", "人工智能", "tonghuashun"),
                        ("BK0800", "人工智能", "eastmoney"),
                    ]
                )
            if "SET is_active = FALSE" in s and "match_method" in s:
                return FakeResult(rowcount=0)
            if "WHERE board_kind = :kind AND ths_board_code = :ths" in s:
                return FakeResult([])
            if "WHERE board_kind = :kind AND em_board_code = :em" in s:
                return FakeResult([])
            if "INSERT INTO" in s:
                return FakeResult(rowcount=1)
            if "CREATE TABLE" in s or "CREATE INDEX" in s:
                return FakeResult()
            return FakeResult()

        def commit(self):
            pass

        def rollback(self):
            pass

    stats = m.rebuild_name_exact_maps(FakeDb(), board_kind="industry", replace_auto=True)
    assert stats["pair_candidates"] == 2
    assert stats["inserted"] == 2

    concept_stats = m.rebuild_name_exact_maps(
        FakeDb(), board_kind="concept", replace_auto=True
    )
    assert concept_stats["pair_candidates"] == 1
    assert concept_stats["inserted"] == 1


def test_upsert_and_resolve_peer_with_sqlite_like_session():
    """用内存假 Session 验证 upsert 返回结构（不连真实 PG）。"""
    from backend_api.utils import industry_board_code_map as m

    stored = {}

    class FakeResult:
        def __init__(self, rows=None, rowcount=0):
            self._rows = rows or []
            self.rowcount = rowcount

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def fetchall(self):
            return self._rows

    class FakeDb:
        def execute(self, sql, params=None):
            s = str(sql)
            params = params or {}
            if "CREATE TABLE" in s or "CREATE INDEX" in s:
                return FakeResult()
            if "UPDATE" in s and "is_active = FALSE" in s and "被新映射覆盖" in s:
                return FakeResult(rowcount=0)
            if "INSERT INTO" in s:
                stored["ths"] = params["ths"]
                stored["em"] = params["em"]
                stored["name"] = params.get("name")
                return FakeResult(rowcount=1)
            if "SELECT id, board_kind" in s:
                row = SimpleNamespace(
                    _mapping={
                        "id": 1,
                        "board_kind": "industry",
                        "board_name": stored.get("name"),
                        "ths_board_code": stored.get("ths"),
                        "em_board_code": stored.get("em"),
                        "match_method": "manual",
                        "confidence": 100,
                        "is_active": True,
                        "note": None,
                        "created_at": datetime(2026, 9, 3, 12, 0, 0),
                        "updated_at": datetime(2026, 9, 3, 12, 0, 0),
                    }
                )
                return FakeResult([row])
            return FakeResult()

    row = m.upsert_code_map(
        FakeDb(),
        ths_board_code="881178",
        em_board_code="BK0740",
        board_name="教育",
        match_method="manual",
    )
    assert row["ths_board_code"] == "881178"
    assert row["em_board_code"] == "BK0740"
    assert row["board_name"] == "教育"
