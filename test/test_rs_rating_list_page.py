# -*- coding: utf-8 -*-
"""list_rs_ratings_page：A/H 排行查询参数与空数据路径。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parents[1]
for p in (str(project_root), str(project_root / "backend_api"), str(project_root / "backend_core")):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_core.indicators.rs_rating.service import list_rs_ratings_page  # noqa: E402


def test_list_rs_ratings_page_empty_when_no_asof():
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = (None,)
    out = list_rs_ratings_page(db, market="CN", page=1, page_size=20)
    assert out["success"] is True
    assert out["data"] == []
    assert out["asof"] is None
    assert "预计算" in (out.get("message") or "")


def test_list_rs_ratings_page_cn_maps_rows():
    db = MagicMock()

    def _execute(sql, params=None):
        sql_s = str(sql)
        m = MagicMock()
        if "MAX(date)" in sql_s:
            m.fetchone.return_value = ("2026-09-22",)
            return m
        if "COUNT(1)" in sql_s:
            m.scalar.return_value = 1
            return m
        m.mappings.return_value.all.return_value = [
            {
                "code": "600519",
                "name": "贵州茅台",
                "date": "2026-09-22",
                "rs_rating": 95,
                "rs_raw": 1.23,
                "roc_63": 0.1,
                "roc_126": 0.2,
                "roc_189": 0.3,
                "roc_252": 0.4,
                "universe_size": 4000,
                "coverage_ratio": 0.9,
            }
        ]
        return m

    db.execute.side_effect = _execute
    with patch(
        "backend_api.utils.cn_listed_board_filter.normalize_multi_board_segments",
        return_value=[],
    ):
        out = list_rs_ratings_page(db, market="CN", page=1, page_size=50)
    assert out["success"] is True
    assert out["asof"] == "2026-09-22"
    assert out["market"] == "CN"
    assert out["total"] == 1
    assert out["data"][0]["code"] == "600519"
    assert out["data"][0]["rs_rating"] == 95
    assert out["data"][0]["strength_label"]


def test_list_rs_ratings_page_hk_uses_hk_tables():
    db = MagicMock()
    seen = []

    def _execute(sql, params=None):
        sql_s = str(sql)
        seen.append(sql_s)
        m = MagicMock()
        if "MAX(date)" in sql_s:
            m.fetchone.return_value = ("2026-09-20",)
            return m
        if "COUNT(1)" in sql_s:
            m.scalar.return_value = 0
            return m
        m.mappings.return_value.all.return_value = []
        return m

    db.execute.side_effect = _execute
    out = list_rs_ratings_page(db, market="HK", page=1, page_size=20)
    assert out["market"] == "HK"
    assert any("rs_ratings_hk" in s for s in seen)
    assert any("stock_basic_info_hk" in s for s in seen)
    assert out["data"] == []


if __name__ == "__main__":
    test_list_rs_ratings_page_empty_when_no_asof()
    test_list_rs_ratings_page_cn_maps_rows()
    test_list_rs_ratings_page_hk_uses_hk_tables()
    print("test_rs_rating_list_page.py: all passed")
