"""环境同步：Key 鉴权、策略 name upsert、观察股缺用户跳过。"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.env_sync.auth import hash_sync_key, verify_sync_key
from backend_api.env_sync.gateway_routes import router as gateway_router
from backend_api.env_sync.admin_routes import router as admin_router
from backend_api.env_sync.services.strategy_configs import (
    export_strategy_configs,
    import_strategy_configs,
)
from backend_api.env_sync.services.trade_observe import import_trade_observe
from backend_api.models import (
    Base,
    EnvSyncServerConfig,
    GMSStrategyConfig,
    UrtTradeObserveStock,
    User,
)


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_expand_modules_granular():
    from backend_api.env_sync import (
        DEFAULT_RESOURCES,
        ALL_RESOURCES,
        expand_modules,
        needs_date_range,
    )

    assert expand_modules(None) == list(DEFAULT_RESOURCES)
    assert "historical_quotes" not in expand_modules(None)
    assert expand_modules(["urt_strategy_configs"]) == ["urt_strategy_configs"]
    assert expand_modules(["gms_trade"]) == [
        "gms_trade_observe_stocks",
        "gms_trade_observe_history",
        "gms_formal_trades",
    ]
    assert "gms_strategy_configs" in expand_modules(["strategy_configs"])
    assert expand_modules(["basic_info"]) == ["stock_basic_info", "stock_basic_info_hk"]
    assert expand_modules(["quotes"]) == ["historical_quotes", "historical_quotes_hk"]
    assert expand_modules(["adj_factors"]) == ["stock_adj_factor"]
    assert expand_modules(["stock_adj_factor"]) == ["stock_adj_factor"]
    assert expand_modules(["permissions"]) == [
        "frontend_permissions",
        "frontend_roles",
        "role_permissions",
    ]
    assert expand_modules(["permissions_resources"]) == [
        "frontend_permissions",
        "frontend_roles",
        "role_permissions",
    ]
    assert expand_modules(["stock_basic"]) == ["stock_basic_info", "stock_basic_info_hk"]
    assert "frontend_permissions" not in expand_modules(None)
    assert needs_date_range(["historical_quotes"]) is True
    assert needs_date_range(["stock_adj_factor"]) is False
    assert needs_date_range(["stock_basic_info"]) is False
    assert set(ALL_RESOURCES) >= set(DEFAULT_RESOURCES)
    assert "frontend_permissions" in ALL_RESOURCES
    assert "stock_adj_factor" in ALL_RESOURCES
    assert "stock_adj_factor" not in expand_modules(None)
    try:
        expand_modules(["no_such"])
        assert False
    except ValueError:
        pass


def test_filter_modules_for_bundle():
    from backend_api.env_sync import filter_modules_for_bundle

    mods = [
        "gms_strategy_configs",
        "frontend_permissions",
        "frontend_roles",
        "stock_basic_info",
    ]
    assert filter_modules_for_bundle("permissions_resources", mods) == [
        "frontend_permissions",
        "frontend_roles",
    ]
    assert filter_modules_for_bundle("strategy_configs", mods) == [
        "gms_strategy_configs",
    ]
    assert filter_modules_for_bundle("stock_basic", mods) == ["stock_basic_info"]
    assert filter_modules_for_bundle("adj_factors", ["stock_adj_factor", "historical_quotes"]) == [
        "stock_adj_factor"
    ]
    assert filter_modules_for_bundle("unknown_bundle", mods) == []


def test_quotes_require_date_range(db):
    from backend_api.env_sync.services import export_modules
    from backend_api.env_sync.services.market_data import (
        import_quotes,
        validate_date_range,
    )
    from backend_api.models import HistoricalQuotes
    from datetime import date

    try:
        validate_date_range(None, None, require=True)
        assert False
    except ValueError:
        pass

    try:
        export_modules(db, ["historical_quotes"])
        assert False
    except ValueError as e:
        assert "start_date" in str(e)

    db.add(
        HistoricalQuotes(
            code="000001",
            name="平安银行",
            date=date(2024, 1, 2),
            open=10.0,
            close=10.5,
            high=10.6,
            low=9.9,
            volume=1000,
        )
    )
    db.add(
        HistoricalQuotes(
            code="000001",
            name="平安银行",
            date=date(2024, 1, 10),
            open=11.0,
            close=11.2,
            high=11.3,
            low=10.8,
            volume=2000,
        )
    )
    db.commit()

    out = export_modules(
        db,
        ["historical_quotes"],
        start_date="2024-01-01",
        end_date="2024-01-05",
    )
    rows = out["bundles"]["quotes"]["items"]["historical_quotes"]
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-01-02"

    # 清空后按包导入
    db.query(HistoricalQuotes).delete()
    db.commit()
    result = import_quotes(db, out["bundles"]["quotes"])
    assert result["created"] == 1
    assert db.query(HistoricalQuotes).count() == 1


def test_iter_adj_factor_push_chunks():
    from backend_api.env_sync.services.market_data import iter_adj_factor_push_chunks

    rows = [
        {
            "code": "000001",
            "trade_date": "2024-01-01",
            "source": "sina",
            "adj_factor": 1.0 + i * 0.01,
        }
        for i in range(25)
    ]
    bundle = {
        "module": "adj_factors",
        "items": {"stock_adj_factor": rows},
        "date_range": {"mode": "full"},
    }
    parts = iter_adj_factor_push_chunks(bundle, chunk_rows=10)
    assert len(parts) == 3
    assert len(parts[0]["items"]["stock_adj_factor"]) == 10
    assert len(parts[2]["items"]["stock_adj_factor"]) == 5
    assert parts[1]["chunk"]["offset"] == 10
    assert parts[1]["chunk"]["total"] == 25
    assert iter_adj_factor_push_chunks(bundle, chunk_rows=100) == [bundle]


def test_push_adj_rows_adaptive_splits_on_502(monkeypatch):
    from backend_api.env_sync import admin_routes
    from backend_api.env_sync.remote_http import RemoteResponse

    calls = {"n": 0, "sizes": []}

    def fake_post(url, *, headers=None, json_body=None, timeout=30.0):
        calls["n"] += 1
        rows = json_body["bundles"]["adj_factors"]["items"]["stock_adj_factor"]
        calls["sizes"].append(len(rows))
        if len(rows) > 80:
            return RemoteResponse(status_code=502, text="bad gateway")
        return RemoteResponse(
            status_code=200,
            text='{"results":{"adj_factors":{"created":%d,"updated":0,"skipped":0,"errors":[]}}}'
            % len(rows),
        )

    monkeypatch.setattr(admin_routes.remote_http, "post", fake_post)
    merged: dict = {}
    batches: list = []
    rows = [{"code": "000001", "trade_date": "2024-01-01", "source": "sina", "adj_factor": 1.0}] * 200
    admin_routes._push_adj_rows_adaptive(
        url="https://example.test/api/env-sync/v1/import",
        headers={},
        batch_mods=["stock_adj_factor"],
        base_bundle={"module": "adj_factors", "items": {}},
        rows=rows,
        label="adj_factors[1/1]",
        merged_results=merged,
        push_batches=batches,
    )
    assert merged["adj_factors"]["created"] == 200
    assert any(s > 80 for s in calls["sizes"])  # 先大后拆
    assert all(s <= 80 for s in calls["sizes"] if s != 200) or max(
        s for s in calls["sizes"] if s <= 80
    ) <= 80
    assert len(batches) >= 2


def test_adj_factors_full_and_long_range_roundtrip(db):
    from datetime import date

    from backend_api.env_sync.services import export_modules
    from backend_api.env_sync.services.market_data import (
        DEFAULT_ADJ_FACTOR_MAX_DAYS,
        import_adj_factors,
        validate_date_range,
    )
    from backend_api.models import StockAdjFactor

    db.add(
        StockAdjFactor(
            code="000001",
            trade_date=date(2024, 1, 2),
            source="sina",
            adj_factor=1.25,
        )
    )
    db.add(
        StockAdjFactor(
            code="000001",
            trade_date=date(2024, 1, 10),
            source="sina",
            adj_factor=1.3,
        )
    )
    db.commit()

    # 不填日期 = 全库
    full = export_modules(db, ["stock_adj_factor"])
    assert full.get("date_range", {}).get("mode") == "full"
    full_rows = full["bundles"]["adj_factors"]["items"]["stock_adj_factor"]
    assert len(full_rows) == 2

    # 按区间过滤
    out = export_modules(
        db,
        ["stock_adj_factor"],
        start_date="2024-01-01",
        end_date="2024-01-05",
    )
    rows = out["bundles"]["adj_factors"]["items"]["stock_adj_factor"]
    assert len(rows) == 1
    assert rows[0]["trade_date"] == "2024-01-02"
    assert rows[0]["source"] == "sina"
    assert abs(float(rows[0]["adj_factor"]) - 1.25) < 1e-9

    # 10 年以上区间允许（默认约 11 年）
    validate_date_range(
        "2015-01-01",
        "2025-12-31",
        require=False,
        max_days=DEFAULT_ADJ_FACTOR_MAX_DAYS,
        label="复权因子",
    )
    long_out = export_modules(
        db,
        ["stock_adj_factor"],
        start_date="2015-01-01",
        end_date="2025-12-31",
    )
    assert len(long_out["bundles"]["adj_factors"]["items"]["stock_adj_factor"]) == 2

    db.query(StockAdjFactor).delete()
    db.commit()
    result = import_adj_factors(db, out["bundles"]["adj_factors"])
    assert result["created"] == 1
    row = db.query(StockAdjFactor).filter_by(code="000001").first()
    assert row is not None
    assert abs(row.adj_factor - 1.25) < 1e-9

    # 再次导入应更新
    rows[0]["adj_factor"] = 1.5
    result2 = import_adj_factors(db, out["bundles"]["adj_factors"])
    assert result2["updated"] == 1
    assert abs(db.query(StockAdjFactor).filter_by(code="000001").first().adj_factor - 1.5) < 1e-9


def test_stock_basic_roundtrip(db):
    from backend_api.env_sync.services.market_data import export_stock_basic, import_stock_basic
    from backend_api.models import StockBasicInfo

    db.add(StockBasicInfo(code="000001", name="平安银行", industry="银行"))
    db.commit()
    bundle = export_stock_basic(db, tables={"stock_basic_info"})
    db.query(StockBasicInfo).delete()
    db.commit()
    result = import_stock_basic(db, bundle, tables={"stock_basic_info"})
    assert result["created"] == 1
    row = db.query(StockBasicInfo).filter_by(code="000001").first()
    assert row is not None
    assert row.name == "平安银行"


def test_permissions_resources_roundtrip(db):
    from backend_api.env_sync.services import export_modules, import_modules
    from backend_api.env_sync.services.permissions_resources import (
        export_permissions_resources,
        import_permissions_resources,
    )
    from backend_api.models import FrontendPermission, FrontendRole, RolePermission

    db.add(
        FrontendPermission(
            code="menu.root",
            name="根菜单",
            level=1,
            parent_code=None,
            channel_code=None,
            sort_order=1,
            is_active=True,
        )
    )
    db.add(
        FrontendPermission(
            code="menu.child",
            name="子菜单",
            level=2,
            parent_code="menu.root",
            channel_code="web",
            sort_order=2,
            is_active=True,
        )
    )
    role = FrontendRole(
        code="standard",
        name="标准用户",
        description="desc",
        is_system=True,
    )
    db.add(role)
    db.flush()
    root = db.query(FrontendPermission).filter_by(code="menu.root").first()
    child = db.query(FrontendPermission).filter_by(code="menu.child").first()
    db.add(RolePermission(role_id=role.id, permission_id=root.id))
    db.add(RolePermission(role_id=role.id, permission_id=child.id))
    db.commit()

    bundle = export_permissions_resources(db)
    assert len(bundle["items"]["frontend_permissions"]) == 2
    assert len(bundle["items"]["frontend_roles"]) == 1
    assert len(bundle["items"]["role_permissions"]) == 2
    assert bundle["items"]["role_permissions"][0]["role_code"] == "standard"

    # 清空后整包导入
    db.query(RolePermission).delete()
    db.query(FrontendPermission).delete()
    db.query(FrontendRole).delete()
    db.commit()

    result = import_permissions_resources(db, bundle)
    assert result["created"] >= 3  # 2 perms + 1 role + links
    assert db.query(FrontendPermission).count() == 2
    assert db.query(FrontendRole).filter_by(code="standard").first() is not None
    assert db.query(RolePermission).count() == 2

    # upsert：改名后再次导入应 updated
    bundle["items"]["frontend_permissions"][0]["name"] = "根菜单改"
    result2 = import_permissions_resources(
        db, bundle, tables=["frontend_permissions"]
    )
    assert result2["updated"] >= 1
    assert (
        db.query(FrontendPermission).filter_by(code="menu.root").first().name
        == "根菜单改"
    )

    # 编排层：仅勾选权限模块
    out = export_modules(db, ["frontend_permissions", "frontend_roles"])
    assert "permissions_resources" in out["bundles"]
    assert "role_permissions" not in out["bundles"]["permissions_resources"]["items"]
    imported = import_modules(
        db,
        out["bundles"],
        modules=["frontend_permissions", "frontend_roles"],
    )
    assert "permissions_resources" in imported["results"]


def test_verify_sync_key_hash(db):
    raw = "test-secret-key-abc"
    db.add(
        EnvSyncServerConfig(
            id=1,
            enabled=True,
            sync_key_hash=hash_sync_key(raw),
            key_hint="test",
            updated_at=datetime.now(),
        )
    )
    db.commit()
    assert verify_sync_key(db, raw) is True
    assert verify_sync_key(db, "wrong") is False
    assert verify_sync_key(db, "") is False


def test_gateway_requires_key(db):
    app = FastAPI()
    app.include_router(gateway_router)

    def _db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    res = client.get("/api/env-sync/v1/health")
    assert res.status_code == 401

    db.add(
        EnvSyncServerConfig(
            id=1,
            enabled=True,
            sync_key_hash=hash_sync_key("k1"),
            updated_at=datetime.now(),
        )
    )
    db.commit()
    res2 = client.get(
        "/api/env-sync/v1/health",
        headers={"Authorization": "Bearer k1"},
    )
    assert res2.status_code == 200
    assert res2.json()["success"] is True


def test_strategy_import_by_name(db):
    db.add(
        GMSStrategyConfig(
            name="default",
            config_params={"a": 1},
            is_active=True,
            is_default=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    )
    db.commit()
    bundle = {
        "module": "strategy_configs",
        "items": {
            "gms_strategy_configs": [
                {
                    "name": "default",
                    "config_params": {"a": 2},
                    "is_active": True,
                    "is_default": True,
                },
                {
                    "name": "v2",
                    "config_params": {"b": 3},
                    "is_active": True,
                    "is_default": False,
                },
            ],
            "urt_strategy_configs": [],
            "rpe_strategy_configs": [],
            "sbbr_strategy_configs": [],
            "gms_runtime_config": [],
        },
    }
    result = import_strategy_configs(db, bundle)
    assert result["updated"] >= 1
    assert result["created"] >= 1
    row = db.query(GMSStrategyConfig).filter_by(name="default").first()
    assert row.config_params["a"] == 2
    assert db.query(GMSStrategyConfig).filter_by(name="v2").first() is not None

    exported = export_strategy_configs(db)
    assert "gms_strategy_configs" in exported["items"]


def test_observe_skips_missing_user(db):
    db.add(
        User(
            id=1,
            username="alice",
            email="a@example.com",
            password_hash="x",
            role="user",
            status="active",
        )
    )
    db.commit()
    bundle = {
        "module": "trade_observe",
        "items": {
            "urt_trade_observe_stocks": [
                {
                    "username": "alice",
                    "market": "CN",
                    "code": "000001",
                    "name": "平安银行",
                },
                {
                    "username": "nobody",
                    "market": "CN",
                    "code": "000002",
                    "name": "万科",
                },
            ]
        },
    }
    result = import_trade_observe(db, bundle)
    assert result["created"] == 1
    assert result["skipped"] >= 1
    assert db.query(UrtTradeObserveStock).count() == 1


def test_admin_pull_mocks_remote(db):
    app = FastAPI()
    app.include_router(admin_router)

    admin = MagicMock()
    admin.id = 9
    admin.username = "admin"
    app.dependency_overrides[get_current_admin] = lambda: admin

    def _db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _db

    from backend_api.models import EnvSyncClientConfig

    db.add(
        EnvSyncClientConfig(
            id=1,
            enabled=True,
            prod_base_url="http://prod.example",
            sync_key="secret",
            updated_at=datetime.now(),
        )
    )
    db.commit()

    fake_export = {
        "success": True,
        "modules": ["strategy_configs"],
        "bundles": {
            "strategy_configs": {
                "module": "strategy_configs",
                "items": {
                    "gms_strategy_configs": [
                        {
                            "name": "pulled",
                            "config_params": {},
                            "is_active": True,
                            "is_default": False,
                        }
                    ],
                    "urt_strategy_configs": [],
                    "rpe_strategy_configs": [],
                    "sbbr_strategy_configs": [],
                    "gms_runtime_config": [],
                },
            }
        },
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return fake_export

        text = ""

    with patch(
        "backend_api.env_sync.admin_routes.remote_http.get",
        return_value=FakeResp(),
    ):
        client = TestClient(app)
        res = client.post(
            "/api/admin/env-sync/pull",
            json={"modules": ["strategy_configs"]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["success"] is True
        assert db.query(GMSStrategyConfig).filter_by(name="pulled").first() is not None


def test_admin_push_filters_modules_per_bundle(db):
    """Push 分批时 modules 只含当前 bundle 细项，且含 permissions_resources。"""
    from backend_api.models import EnvSyncClientConfig, FrontendPermission

    app = FastAPI()
    app.include_router(admin_router)

    admin = MagicMock()
    admin.id = 9
    admin.username = "admin"
    app.dependency_overrides[get_current_admin] = lambda: admin

    def _db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _db

    db.add(
        EnvSyncClientConfig(
            id=1,
            enabled=True,
            prod_base_url="http://prod.example",
            sync_key="secret",
            updated_at=datetime.now(),
        )
    )
    db.add(
        FrontendPermission(
            code="menu.root",
            name="根",
            level=1,
            parent_code=None,
            channel_code=None,
            sort_order=1,
            is_active=True,
        )
    )
    db.add(
        GMSStrategyConfig(
            name="push-cfg",
            config_params={},
            is_active=True,
            is_default=False,
        )
    )
    db.commit()

    posted = []

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"success": True, "results": {"ok": True}}

    def _fake_post(url, headers=None, json_body=None, timeout=None):
        posted.append(json_body)
        return FakeResp()

    with patch(
        "backend_api.env_sync.admin_routes.remote_http.post",
        side_effect=_fake_post,
    ):
        client = TestClient(app)
        res = client.post(
            "/api/admin/env-sync/push",
            json={
                "modules": [
                    "gms_strategy_configs",
                    "frontend_permissions",
                ]
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["success"] is True

    assert len(posted) == 2
    by_bundle = {next(iter(p["bundles"].keys())): p for p in posted}
    assert "strategy_configs" in by_bundle
    assert "permissions_resources" in by_bundle
    assert by_bundle["strategy_configs"]["modules"] == ["gms_strategy_configs"]
    assert by_bundle["permissions_resources"]["modules"] == ["frontend_permissions"]
    # 不得把权限细项塞进策略批次
    assert "frontend_permissions" not in (
        by_bundle["strategy_configs"]["modules"] or []
    )


def test_remote_fail_detail_unknown_module_hint():
    from backend_api.env_sync.admin_routes import _remote_fail_detail

    msg = _remote_fail_detail(
        "生产 import[permissions_resources]",
        400,
        '{"detail":"未知同步模块: frontend_permissions"}',
    )
    assert "部署" in msg
    assert "frontend_permissions" in msg
