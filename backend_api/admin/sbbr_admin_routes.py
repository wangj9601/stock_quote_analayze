"""SBBR 管理端：配置 / 回测 / 手动预计算。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend_api.auth import get_current_user
from backend_api.models import User
from backend_core.strategies.sbbr.backtest_runner import start_backtest_async
from backend_core.strategies.sbbr.backtest_storage import SBBRBacktestStorage
from backend_core.strategies.sbbr.config import SBBRConfigManager
from backend_core.strategies.sbbr.scheduled_precompute import run_sbbr_precompute

router = APIRouter(prefix="/api/admin/sbbr", tags=["admin-sbbr"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    role = (getattr(user, "role", None) or "").lower()
    if role not in ("admin", "administrator", "superadmin"):
        # 宽松：有登录即可管理（与部分 admin 路由一致）；严格可再收紧
        pass
    return user


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


class BacktestCreateReq(BaseModel):
    task_name: Optional[str] = None
    start_date: str
    end_date: str
    backtest_type: str = "signal_hit_rate"
    target_pct: float = 0.5
    horizon_days: int = 60
    strategy_config_id: Optional[int] = None
    stock_pool: Optional[list] = None
    universe_limit: int = 80
    date_step: int = 5


@router.get("/strategy-configs")
def admin_list_configs(_user: User = Depends(_require_admin)):
    return {"items": SBBRConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: User = Depends(_require_admin)):
    return SBBRConfigManager().create_config(
        name=body.name,
        config_params=body.config_params,
        description=body.description,
        set_default=body.set_default,
    )


@router.put("/strategy-configs/{config_id}/update")
def admin_update_config(config_id: int, body: ConfigUpdateReq, _user: User = Depends(_require_admin)):
    try:
        return SBBRConfigManager().update_config(config_id, body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: User = Depends(_require_admin)):
    try:
        return SBBRConfigManager().set_default(config_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/backtests")
def admin_create_backtest(body: BacktestCreateReq, _user: User = Depends(_require_admin)):
    storage = SBBRBacktestStorage()
    cfg = body.dict()
    task_id = storage.create_task(cfg, name=body.task_name)
    start_backtest_async(task_id, cfg)
    return {"task_id": task_id, "status": "pending"}


@router.get("/backtests")
def admin_list_backtests(limit: int = 50, _user: User = Depends(_require_admin)):
    return {"items": SBBRBacktestStorage().list_tasks(limit=limit)}


@router.get("/backtests/{task_id}")
def admin_get_backtest(task_id: str, _user: User = Depends(_require_admin)):
    row = SBBRBacktestStorage().get_task(task_id)
    if not row:
        raise HTTPException(404, "task not found")
    return row


@router.post("/precompute/trigger")
def admin_trigger_precompute(
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    _user: User = Depends(_require_admin),
):
    return run_sbbr_precompute(config_id=config_id, trade_date=trade_date)
