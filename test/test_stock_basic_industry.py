"""股票基本信息：行业同步、退市筛选、批量采集标志。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.admin import stock_basic_admin  # noqa: E402
from backend_api.utils.industry_board_query import (  # noqa: E402
    resolve_cn_industry_display,
)


def test_resolve_cn_industry_display_prefers_board():
    assert resolve_cn_industry_display(None, "银行") == "银行"
    assert resolve_cn_industry_display("旧行业", "银行") == "银行"
    assert resolve_cn_industry_display("旧行业", None) == "旧行业"
    assert resolve_cn_industry_display("nan", None) is None
    assert resolve_cn_industry_display("BK1019,化学制药", None) == "化学制药"
    assert resolve_cn_industry_display(None, "BK0457") is None


def test_clean_industry_display_text_strips_bk_codes():
    from backend_api.utils.industry_board_query import clean_industry_display_text

    assert clean_industry_display_text("BK1019,化学制药") == "化学制药"
    assert clean_industry_display_text("BK1019") is None
    assert clean_industry_display_text("化学制药,电网设备") == "化学制药,电网设备"


def test_append_common_filters_only_delisted():
    where: list[str] = []
    stock_basic_admin._append_common_filters(
        where,
        empty_shares=False,
        collect_enabled=None,
        delisted_filter="only",
        params={},
    )
    assert stock_basic_admin._only_delisted_name_condition() in where[0]


def test_append_common_filters_exclude_delisted():
    where: list[str] = []
    stock_basic_admin._append_common_filters(
        where,
        empty_shares=False,
        collect_enabled=None,
        delisted_filter="exclude",
        params={},
    )
    assert stock_basic_admin._exclude_delisted_name_condition() in where[0]


@patch.object(
    stock_basic_admin,
    "sync_a_stock_industry_from_boards",
    return_value={"updated": 3, "matched": 5},
)
def test_sync_industry_endpoint(mock_sync):
    app = FastAPI()
    app.include_router(stock_basic_admin.router)

    def _override_admin():
        return MagicMock(username="tester")

    def _override_db():
        db = MagicMock()
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[stock_basic_admin.get_current_admin] = _override_admin
    app.dependency_overrides[stock_basic_admin.get_db] = _override_db
    client = TestClient(app)

    r = client.post("/api/admin/stock-basic/sync-industry?market=CN&only_empty=true")
    assert r.status_code == 200
    assert r.json()["data"]["updated"] == 3
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs.get("only_empty") is True


def test_batch_collect_flag_endpoint():
    app = FastAPI()
    app.include_router(stock_basic_admin.router)

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.rowcount = 2
    mock_db.execute.return_value = mock_result

    def _override_admin():
        return MagicMock(username="tester")

    def _override_db():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[stock_basic_admin.get_current_admin] = _override_admin
    app.dependency_overrides[stock_basic_admin.get_db] = _override_db
    client = TestClient(app)

    with patch.object(stock_basic_admin, "ensure_share_columns"), patch.object(
        stock_basic_admin, "_write_operation_log"
    ):
        r = client.post(
            "/api/admin/stock-basic/collect-flag/batch",
            json={"market": "CN", "codes": ["000001", "600000"], "collect_enabled": False},
        )
    assert r.status_code == 200
    assert r.json()["data"]["affected"] == 2
    mock_db.commit.assert_called()
