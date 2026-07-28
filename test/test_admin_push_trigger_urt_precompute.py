"""管理端按推送任务立即推送 / URT 预计算 date+market 参数。"""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend_api.auth import get_current_admin
from backend_api.push_routes import (
    admin_router as push_admin_router,
    get_config_service,
    get_push_service,
)
from backend_api.admin.urt_admin_routes import router as urt_admin_router


def _admin():
    u = MagicMock()
    u.id = 99
    u.role = "admin"
    return u


def test_admin_trigger_push_config_calls_push_to_user():
    app = FastAPI()
    app.include_router(push_admin_router)
    app.dependency_overrides[get_current_admin] = _admin

    cfg = MagicMock()
    cfg.id = 13
    cfg.user_id = 7
    cfg.enabled = True
    cfg.report_type = "urt_daily"

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.record_id = 150
    mock_result.error_message = None

    config_svc = MagicMock()
    config_svc.get_config_by_id.return_value = cfg
    push_svc = MagicMock()
    push_svc.push_to_user.return_value = mock_result

    app.dependency_overrides[get_config_service] = lambda: config_svc
    app.dependency_overrides[get_push_service] = lambda: push_svc

    client = TestClient(app)
    res = client.post("/api/admin/push/configs/13/trigger")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["record_id"] == 150
    push_svc.push_to_user.assert_called_once()
    kwargs = push_svc.push_to_user.call_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["config_id"] == 13
    assert kwargs["force"] is False
    assert str(kwargs["push_time"]).startswith("M")
    assert len(str(kwargs["push_time"])) <= 10


def test_admin_trigger_push_disabled_requires_force():
    app = FastAPI()
    app.include_router(push_admin_router)
    app.dependency_overrides[get_current_admin] = _admin

    cfg = MagicMock()
    cfg.id = 13
    cfg.user_id = 7
    cfg.enabled = False
    cfg.report_type = "urt_daily"

    config_svc = MagicMock()
    config_svc.get_config_by_id.return_value = cfg
    push_svc = MagicMock()
    app.dependency_overrides[get_config_service] = lambda: config_svc
    app.dependency_overrides[get_push_service] = lambda: push_svc

    client = TestClient(app)
    res = client.post("/api/admin/push/configs/13/trigger")
    assert res.status_code == 400
    push_svc.push_to_user.assert_not_called()

    mock_result = MagicMock(success=True, record_id=1, error_message=None)
    push_svc.push_to_user.return_value = mock_result
    res2 = client.post("/api/admin/push/configs/13/trigger?force=true")
    assert res2.status_code == 200
    assert push_svc.push_to_user.call_args.kwargs["force"] is True


def test_urt_precompute_run_accepts_date_and_market():
    app = FastAPI()
    app.include_router(urt_admin_router)
    client = TestClient(app)

    with patch(
        "backend_core.strategies.urt.scheduled_precompute.run_urt_precompute_for_config"
    ) as for_cfg, patch("threading.Thread") as Th:

        def _immediate(*args, **kwargs):
            target = kwargs.get("target") or (args[0] if args else None)
            t = MagicMock()
            t.start = lambda: target() if target else None
            return t

        Th.side_effect = _immediate
        res = client.post(
            "/api/admin/urt/precompute/run?date=2026-07-27&market=HK&config_id=1"
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        assert body["market"] == "HK"
        assert body["date"] == "2026-07-27"
        for_cfg.assert_called_once()
        assert for_cfg.call_args.kwargs.get("trade_date") == "2026-07-27"
        assert for_cfg.call_args.kwargs.get("market") == "HK"


def test_urt_precompute_run_rejects_bad_market():
    app = FastAPI()
    app.include_router(urt_admin_router)
    client = TestClient(app)
    res = client.post("/api/admin/urt/precompute/run?market=US")
    assert res.status_code == 400
