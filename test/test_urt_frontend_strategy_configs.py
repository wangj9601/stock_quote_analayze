# -*- coding: utf-8 -*-
"""URT 前台参数版本列表接口（不连真实库时用 mock）。"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_list_urt_strategy_configs_public_shape():
    from backend_api.stock.urt_public_frontend_routes import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    fake_rows = [
        {
            "id": 1,
            "name": "默认",
            "version_label": "v1",
            "description": "d",
            "is_default": True,
            "precompute_enabled": True,
            "updated_at": "2026-08-19T10:00:00",
            "config_params": {"min_score": 72, "volume_multiple": 3.2},
        },
        {
            "id": 2,
            "name": "激进",
            "version_label": None,
            "description": None,
            "is_default": False,
            "precompute_enabled": False,
            "updated_at": "2026-08-18T10:00:00",
            "config_params": {"min_score": 65, "volume_multiple": 2.5},
        },
    ]

    with patch("backend_api.stock.urt_public_frontend_routes.URTConfigManager") as Mgr:
        inst = Mgr.return_value
        inst.ensure_default_row = MagicMock()
        inst.list_configs = MagicMock(return_value=fake_rows)
        inst.get_config = MagicMock(
            side_effect=lambda cid, db=None: {
                1: {"min_score": 72, "volume_multiple": 3.2},
                2: {"min_score": 65, "volume_multiple": 2.5},
            }.get(int(cid), {})
        )
        inst.get_config_meta = MagicMock(
            return_value={
                "config_id": 1,
                "name": "默认",
                "min_score": 72,
                "volume_multiple": 3.2,
            }
        )
        # override get_db dependency
        from backend_api.database import get_db

        def _db():
            yield MagicMock()

        app.dependency_overrides[get_db] = _db
        client = TestClient(app)
        res = client.get("/api/frontend/urt/strategy-configs")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["default_config_id"] == 1
        assert body["effective_config_id"] == 1
        assert body["effective"]["min_score"] == 72
        assert len(body["data"]) == 2
        assert body["data"][0]["name"] == "默认"
        assert body["data"][0]["min_score"] == 72
        assert body["data"][0]["volume_multiple"] == 3.2
        # updated_at 可选透出（有则便于前台陈旧判断）
        assert "updated_at" in body["data"][0]
