"""RPE 管理端：配置 / 回测 / 手动预计算 / 选股结果。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
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


def _resolve_signals_config_id(db: Session, config_id: Optional[int]) -> int:
    """信号查询：显式 config 校验存在；缺省先 default，再预计算启用版，再无则 400。"""
    from backend_api.models import RPEStrategyConfig

    if config_id is not None:
        row = (
            db.query(RPEStrategyConfig)
            .filter(RPEStrategyConfig.id == int(config_id))
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"参数版本不存在: {config_id}")
        return int(config_id)
    row = (
        db.query(RPEStrategyConfig)
        .filter(RPEStrategyConfig.is_default.is_(True))
        .order_by(RPEStrategyConfig.id.asc())
        .first()
    )
    if not row:
        row = (
            db.query(RPEStrategyConfig)
            .filter(RPEStrategyConfig.precompute_enabled.is_(True))
            .order_by(RPEStrategyConfig.id.asc())
            .first()
        )
    if not row:
        raise HTTPException(status_code=400, detail="无可用 RPE 参数版本")
    return int(row.id)


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


@router.get("/signals")
def list_admin_signals(
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，空则取行情最新日"),
    config_id: Optional[int] = Query(None, description="参数版本；空则默认/预计算版本"),
    code: Optional[str] = Query(None, description="可选股票代码"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: Admin = Depends(_require_admin),
):
    """管理端只读：按日查询预计算入场信号。仅读 rpe_signal_trace，禁止调用 engine.screen。"""
    date_s = (trade_date or "").strip()[:10] or None
    if not date_s:
        from backend_core.strategies.rpe.data_loader import RPEDataLoader

        date_s = RPEDataLoader(db).resolve_trade_date()
    cid = _resolve_signals_config_id(db, config_id)
    from backend_core.strategies.rpe.signal_storage import list_admin_entry_signals

    try:
        return list_admin_entry_signals(
            db,
            trade_date=date_s,
            config_id=cid,
            code=code,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
