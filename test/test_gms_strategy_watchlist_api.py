import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.models import (  # noqa: E402
    Base,
    StockBasicInfo,
    StockBasicInfoHK,
    GMSRuntimeConfig,
    GMSBacktestTask,
)
from backend_api.admin import gms_admin_routes  # noqa: E402


def _build_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add(StockBasicInfo(code="000001", name="平安银行"))
    db.add(StockBasicInfo(code="600000", name="浦发银行"))
    db.add(StockBasicInfoHK(code="00700", name="腾讯控股"))
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(gms_admin_routes.router)
    app.dependency_overrides[gms_admin_routes.get_db] = override_get_db
    return TestClient(app)


def test_gms_strategy_version_and_stock_crud():
    client = _build_client()

    create_version_resp = client.post(
        "/api/admin/gms/strategy-versions",
        json={
            "strategy_code": "GMS",
            "version_name": "基础版本",
            "version_no": 1,
            "description": "用于测试",
            "is_active": True,
            "created_by": "tester",
        },
    )
    assert create_version_resp.status_code == 200
    version_id = create_version_resp.json()["data"]["id"]

    create_stock_resp = client.post(
        "/api/admin/gms/strategy-version-stocks",
        json={
            "version_id": version_id,
            "market": "A",
            "stock_code": "000001",
            "status": "active",
            "sort_order": 1,
        },
    )
    assert create_stock_resp.status_code == 200
    stock_id = create_stock_resp.json()["data"]["id"]

    # JSON 中股票代码为数字时也应能写入（库表 code 为字符串，后端须绑定 str）
    create_num = client.post(
        "/api/admin/gms/strategy-version-stocks",
        json={
            "version_id": version_id,
            "market": "A",
            "stock_code": 600000,
            "status": "active",
            "sort_order": 2,
        },
    )
    assert create_num.status_code == 200
    assert create_num.json()["data"]["stock_code"] == "600000"

    list_resp = client.get(f"/api/admin/gms/strategy-version-stocks?version_id={version_id}&page=1&page_size=20")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 2

    update_resp = client.put(
        f"/api/admin/gms/strategy-version-stocks/{stock_id}",
        json={"remark": "重点观察"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["remark"] == "重点观察"

    delete_resp = client.delete(f"/api/admin/gms/strategy-version-stocks/{stock_id}")
    assert delete_resp.status_code == 200


def test_gms_strategy_batch_import_validation_and_dedupe():
    client = _build_client()

    create_version_resp = client.post(
        "/api/admin/gms/strategy-versions",
        json={"strategy_code": "GMS", "version_name": "导入版本", "version_no": 2},
    )
    version_id = create_version_resp.json()["data"]["id"]

    import_resp = client.post(
        "/api/admin/gms/strategy-version-stocks/batch-import",
        json={
            "version_id": version_id,
            "items": [
                {"market": "A", "stock_code": "000001"},
                {"market": "HK", "stock_code": "00700"},
                {"market": "A", "stock_code": "000001"},
                {"market": "A", "stock_code": "999999"},
            ],
        },
    )
    assert import_resp.status_code == 200
    data = import_resp.json()["data"]
    assert data["success_count"] == 2
    assert data["skip_count"] == 1
    assert data["fail_count"] == 1
    assert len(data["fail_details"]) == 1


def test_gms_scoring_mechanisms_and_penalty_types():
    client = _build_client()

    mech_resp = client.get("/api/admin/gms/scoring-mechanisms")
    assert mech_resp.status_code == 200
    mech_ids = {m["id"] for m in mech_resp.json()["data"]}
    assert "tiered_dual_max" in mech_ids
    assert "tiered_dual_penalty" in mech_ids

    penalty_resp = client.get("/api/admin/gms/penalty-rule-types")
    assert penalty_resp.status_code == 200
    penalty_ids = {p["id"] for p in penalty_resp.json()["data"]}
    assert "close_below_ma60" in penalty_ids


def test_gms_strategy_version_scoring_create_and_update():
    client = _build_client()

    create_resp = client.post(
        "/api/admin/gms/strategy-versions",
        json={
            "strategy_code": "GMS",
            "version_name": "增强打分测试",
            "version_no": 901,
            "scoring_mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "close_below_ma60", "enabled": True, "points": 10, "label": "低于MA60"},
            ],
            "created_by": "tester",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    version = create_resp.json()["data"]
    assert version["scoring_mechanism"] == "tiered_dual_penalty"
    assert version.get("config_id")
    version_id = version["id"]

    full_resp = client.get(f"/api/admin/gms/strategy-versions/{version_id}/full")
    assert full_resp.status_code == 200
    full = full_resp.json()["data"]
    assert full["config"] is not None
    scoring = (full["config"].get("config_params") or {}).get("scoring") or {}
    assert scoring.get("mechanism") == "tiered_dual_penalty"

    update_resp = client.put(
        f"/api/admin/gms/strategy-versions/{version_id}/scoring",
        json={
            "scoring_mechanism": "tiered_dual_penalty",
            "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 15}],
            "config": {"scoring": {"watch_threshold": 65}},
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["penalty_rules"][0]["points"] == 15

    bad_resp = client.put(
        f"/api/admin/gms/strategy-versions/{version_id}/scoring",
        json={
            "scoring_mechanism": "tiered_dual_max",
            "penalty_rules": [{"id": "close_below_ma60", "enabled": True, "points": 10}],
        },
    )
    assert bad_resp.status_code == 400


def test_gms_create_penalty_version_without_rules_rejected():
    client = _build_client()

    bad_create = client.post(
        "/api/admin/gms/strategy-versions",
        json={
            "strategy_code": "GMS",
            "version_name": "无效增强版",
            "version_no": 902,
            "scoring_mechanism": "tiered_dual_penalty",
            "penalty_rules": [],
        },
    )
    assert bad_create.status_code == 400
