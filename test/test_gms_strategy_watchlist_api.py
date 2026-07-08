import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.models import (  # noqa: E402
    Base,
    StockBasicInfo,
    StockBasicInfoHK,
    IndustryBoardConstituent,
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
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS industry_board_basic_info (
                board_code TEXT PRIMARY KEY,
                board_name TEXT
            )
            """
        )
    )
    db.add(StockBasicInfo(code="000001", name="平安银行"))
    db.add(StockBasicInfo(code="600000", name="浦发银行"))
    db.add(StockBasicInfoHK(code="00700", name="腾讯控股", industry="互联网"))
    db.add(IndustryBoardConstituent(board_code="BK0479", stock_code="000001", stock_name="平安银行"))
    db.add(IndustryBoardConstituent(board_code="BK0479", stock_code="600000", stock_name="浦发银行"))
    db.execute(
        text(
            "INSERT INTO industry_board_basic_info (board_code, board_name) VALUES ('BK0479', '银行')"
        )
    )
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
    assert create_stock_resp.json()["data"].get("industry") == "银行"

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
    industries = {item["stock_code"]: item.get("industry") for item in list_resp.json()["data"]}
    assert industries.get("000001") == "银行"
    assert industries.get("600000") == "银行"

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


def test_gms_strategy_batch_import_clear_existing():
    client = _build_client()

    create_version_resp = client.post(
        "/api/admin/gms/strategy-versions",
        json={"strategy_code": "GMS", "version_name": "清空导入版本", "version_no": 3},
    )
    version_id = create_version_resp.json()["data"]["id"]

    seed_resp = client.post(
        "/api/admin/gms/strategy-version-stocks/batch-import",
        json={
            "version_id": version_id,
            "items": [{"market": "A", "stock_code": "000001"}],
        },
    )
    assert seed_resp.status_code == 200
    assert seed_resp.json()["data"]["success_count"] == 1

    import_resp = client.post(
        "/api/admin/gms/strategy-version-stocks/batch-import",
        json={
            "version_id": version_id,
            "clear_existing": True,
            "items": [{"market": "A", "stock_code": "600000"}],
        },
    )
    assert import_resp.status_code == 200
    data = import_resp.json()["data"]
    assert data["cleared_count"] == 1
    assert data["success_count"] == 1

    list_resp = client.get(
        f"/api/admin/gms/strategy-version-stocks?version_id={version_id}&page=1&page_size=50"
    )
    assert list_resp.status_code == 200
    rows = list_resp.json()["data"]
    codes = {r["stock_code"] for r in rows}
    assert codes == {"600000"}


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
    assert "observation_range_amplitude" in penalty_ids


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


def _unbind_version_config(client, version_id: int) -> None:
    """模拟迁移遗留：策略版本未绑定 config_id。"""
    override = client.app.dependency_overrides[gms_admin_routes.get_db]
    gen = override()
    db = next(gen)
    try:
        from backend_api.models import GMSStrategyVersion

        row = db.query(GMSStrategyVersion).filter(GMSStrategyVersion.id == version_id).first()
        assert row is not None
        row.config_id = None
        db.commit()
    finally:
        gen.close()


def test_gms_strategy_version_scoring_auto_bind_config():
    """未绑定 config 的历史版本，保存打分时自动绑定或创建 config。"""
    client = _build_client()

    create_resp = client.post(
        "/api/admin/gms/strategy-versions",
        json={
            "strategy_code": "GMS",
            "version_name": "未绑定测试",
            "version_no": 88,
            "created_by": "tester",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    version_id = create_resp.json()["data"]["id"]
    _unbind_version_config(client, version_id)

    save_resp = client.put(
        f"/api/admin/gms/strategy-versions/{version_id}/scoring",
        json={
            "scoring_mechanism": "tiered_dual_penalty",
            "penalty_rules": [
                {"id": "close_below_ma60", "enabled": True, "points": 20, "label": "低于MA60"},
            ],
            "config": {"scoring": {"watch_threshold": 60}},
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    saved = save_resp.json()["data"]
    assert saved.get("config_id")
    assert saved["scoring_mechanism"] == "tiered_dual_penalty"
    assert saved["penalty_rules"][0]["points"] == 20


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
