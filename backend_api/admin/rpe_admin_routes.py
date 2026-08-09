"""RPE 管理端：配置 / 回测 / 手动预计算 / 选股结果。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend_api.auth import get_current_admin
from backend_api.models import Admin
from backend_core.strategies.rpe.backtest_runner import start_backtest_async
from backend_core.strategies.rpe.backtest_storage import RPEBacktestStorage
from backend_core.strategies.rpe.config import RPEConfigManager
from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface
from backend_core.strategies.rpe.scheduled_precompute import run_rpe_precompute

router = APIRouter(prefix="/api/admin/rpe", tags=["admin-rpe"])


def _require_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    """管理后台 JWT（is_admin）鉴权，勿用 get_current_user（查 User 表会 401）。"""
    return admin


class ConfigCreateReq(BaseModel):
    name: str
    description: str = ""
    config_params: Optional[Dict[str, Any]] = None
    set_default: bool = False


class ConfigUpdateReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    precompute_enabled: Optional[bool] = None


class BacktestCreateReq(BaseModel):
    task_name: Optional[str] = None
    start_date: str
    end_date: str
    backtest_type: str = "signal_hit_rate"
    target_relative_pct: float = 0.08
    horizon_days: int = 40
    strategy_config_id: Optional[int] = None
    board_code: Optional[str] = None
    max_boards: int = 10
    date_step: int = 5


@router.get("/strategy-configs")
def admin_list_configs(_user: Admin = Depends(_require_admin)):
    return {"items": RPEConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: Admin = Depends(_require_admin)):
    return RPEConfigManager().create_config(
        name=body.name,
        config_params=body.config_params,
        description=body.description,
        set_default=body.set_default,
    )


@router.put("/strategy-configs/{config_id}/update")
def admin_update_config(config_id: int, body: ConfigUpdateReq, _user: Admin = Depends(_require_admin)):
    try:
        return RPEConfigManager().update_config(config_id, body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: Admin = Depends(_require_admin)):
    try:
        return RPEConfigManager().set_default(config_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/backtests")
def admin_create_backtest(body: BacktestCreateReq, _user: Admin = Depends(_require_admin)):
    storage = RPEBacktestStorage()
    cfg = body.dict()
    task_id = storage.create_task(cfg, name=body.task_name)
    start_backtest_async(task_id, cfg)
    return {"task_id": task_id, "status": "pending"}


@router.get("/backtests")
def admin_list_backtests(limit: int = 50, _user: Admin = Depends(_require_admin)):
    return {"items": RPEBacktestStorage().list_tasks(limit=limit)}


@router.get("/backtests/{task_id}")
def admin_get_backtest(task_id: str, _user: Admin = Depends(_require_admin)):
    row = RPEBacktestStorage().get_task(task_id)
    if not row:
        raise HTTPException(404, "task not found")
    return row


@router.post("/precompute/trigger")
def admin_trigger_precompute(
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    max_boards: Optional[int] = 20,
    _user: Admin = Depends(_require_admin),
):
    return run_rpe_precompute(config_id=config_id, trade_date=trade_date, max_boards=max_boards)


@router.get("/selection-results")
def admin_selection_results(
    date: Optional[str] = None,
    config_id: Optional[int] = None,
    entry_only: bool = False,
    signal_type: Optional[str] = None,
    max_results: int = 200,
    _user: Admin = Depends(_require_admin),
):
    return RPEFrontendInterface.get_selection_results(
        date=date,
        config_id=config_id,
        scope="cn",
        entry_only=entry_only,
        signal_type=signal_type,
        max_results=max_results,
    )
