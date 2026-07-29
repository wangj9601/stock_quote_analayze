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
    assert needs_date_range(["historical_quotes"]) is True
    assert needs_date_range(["stock_basic_info"]) is False
    assert set(ALL_RESOURCES) >= set(DEFAULT_RESOURCES)
    try:
        expand_modules(["no_such"])
        assert False
    except ValueError:
        pass


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
