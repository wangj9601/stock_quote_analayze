# -*- coding: utf-8 -*-
"""概念板行情列表 / 详情冒烟（与行业板对称）。"""

from types import SimpleNamespace

from backend_api.utils import industry_board_query as q


def test_fetch_concept_board_list_merges_slope(monkeypatch):
    catalog = [
        {
            "board_code": "885311",
            "board_name": "智能电网",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 40,
            "member_count": 40,
        }
    ]
    monkeypatch.setattr(
        q,
        "fetch_concept_board_catalog",
        lambda db, **kwargs: catalog,
    )
    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda db, codes, board_kind="concept": {
            "885311": {
                "sector_slope": 0.0012,
                "sector_slope_window": 60,
                "slope_asof_date": "2026-08-08",
                "member_count_used": 40,
            }
        },
    )
    out = q.fetch_concept_board_list_with_metrics(SimpleNamespace(), board_code_source="tonghuashun")
    assert len(out) == 1
    assert out[0]["board_kind"] == "concept"
    assert out[0]["sector_slope"] == 0.0012
    assert out[0]["board_strong"] is True
    assert out[0]["board_env"] == "strong"


def test_fetch_concept_board_detail_uses_concept_kind(monkeypatch):
    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda *a, **k: {
            "board_code": "885311",
            "board_name": "智能电网",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda *a, **k: {
            "885311": {
                "sector_slope": -0.002,
                "sector_slope_window": 60,
                "slope_asof_date": "2026-08-08",
                "member_count_used": 12,
            }
        },
    )
    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "backend_core.board_roles.service.extract_leader_mid_from_payload",
        lambda payload: {"leaders": [], "mids": []},
    )

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchone=lambda: (12,))

        def rollback(self):
            pass

    detail = q.fetch_concept_board_detail(_DB(), "885311", include_roles=True)
    assert detail["board_kind"] == "concept"
    assert detail["board_weak"] is True
    assert detail["sector_slope"] == -0.002
