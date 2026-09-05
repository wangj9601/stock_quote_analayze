"""SBBR 管理端：配置 / 回测 / 手动预计算。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.models import Admin
from backend_core.strategies.sbbr.backtest_runner import start_backtest_async
from backend_core.strategies.sbbr.backtest_storage import SBBRBacktestStorage
from backend_core.strategies.sbbr.config import SBBRConfigManager
from backend_core.strategies.sbbr.scheduled_precompute import run_sbbr_precompute

router = APIRouter(prefix="/api/admin/sbbr", tags=["admin-sbbr"])


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
    stock_pool_mode: str = Field(
        "market",
        description="market | industry_board | concept_board | stocks",
    )
    industry_board_codes: Optional[List[str]] = None
    concept_board_codes: Optional[List[str]] = None
    stock_codes: Optional[List[str]] = None


def _validate_backtest_scope(body: BacktestCreateReq) -> str:
    mode = (body.stock_pool_mode or "market").strip().lower()
    if mode not in ("market", "industry_board", "concept_board", "stocks"):
        raise HTTPException(400, f"不支持的 stock_pool_mode: {mode}")
    # 兼容：显式传入 stock_pool 时跳过范围必填校验
    if body.stock_pool:
        return mode
    if mode == "industry_board" and not (body.industry_board_codes or []):
        raise HTTPException(400, "请选择行业板块")
    if mode == "concept_board" and not (body.concept_board_codes or []):
        raise HTTPException(400, "请选择概念板块")
    if mode == "stocks" and not (body.stock_codes or []):
        raise HTTPException(400, "请输入个股代码")
    return mode


def _build_backtest_config(db: Session, body: BacktestCreateReq) -> Dict[str, Any]:
    """解析股票池并写入 config（market 不塞 codes，由 runner 走 build_size_universe）。"""
    from backend_core.strategies.double_bottom.universe import resolve_stock_pool

    mode = _validate_backtest_scope(body)
    cfg = body.dict()
    cfg["stock_pool_mode"] = mode

    # 显式 stock_pool 优先（兼容旧调用）
    if body.stock_pool:
        codes = [str(c).strip() for c in body.stock_pool if str(c).strip()]
        cfg["stock_pool"] = codes
        cfg["scope_meta"] = {
            "stock_pool_mode": mode,
            "board_codes": [],
            "stock_count": len(codes),
            "universe_limit": body.universe_limit,
            "source": "explicit_stock_pool",
        }
        return cfg

    if mode == "market":
        cfg["stock_pool"] = None
        cfg["scope_meta"] = {
            "stock_pool_mode": "market",
            "board_codes": [],
            "stock_count": None,
            "universe_limit": body.universe_limit,
            "source": "build_size_universe",
        }
        return cfg

    try:
        pool = resolve_stock_pool(
            db,
            stock_pool_mode=mode,
            industry_board_codes=body.industry_board_codes,
            concept_board_codes=body.concept_board_codes,
            stock_codes=body.stock_codes,
            universe_limit=body.universe_limit,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    codes = list(pool.get("codes") or [])
    if not codes:
        raise HTTPException(400, "股票池为空，请检查数据范围")

    scope_meta = dict(pool.get("scope_meta") or {})
    scope_meta["source"] = "resolve_stock_pool"
    cfg["stock_pool"] = codes
    cfg["scope_meta"] = scope_meta
    cfg["industry_board_codes"] = body.industry_board_codes
    cfg["concept_board_codes"] = body.concept_board_codes
    cfg["stock_codes"] = body.stock_codes
    return cfg


@router.get("/strategy-configs")
def admin_list_configs(_user: Admin = Depends(_require_admin)):
    return {"items": SBBRConfigManager().list_configs(active_only=False)}


@router.post("/strategy-configs")
def admin_create_config(body: ConfigCreateReq, _user: Admin = Depends(_require_admin)):
    return SBBRConfigManager().create_config(
        name=body.name,
        config_params=body.config_params,
        description=body.description,
        set_default=body.set_default,
    )


@router.put("/strategy-configs/{config_id}/update")
def admin_update_config(config_id: int, body: ConfigUpdateReq, _user: Admin = Depends(_require_admin)):
    try:
        return SBBRConfigManager().update_config(config_id, body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/strategy-configs/{config_id}/default")
def admin_set_default(config_id: int, _user: Admin = Depends(_require_admin)):
    try:
        return SBBRConfigManager().set_default(config_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/backtests")
def admin_create_backtest(
    body: BacktestCreateReq,
    db: Session = Depends(get_db),
    _user: Admin = Depends(_require_admin),
):
    storage = SBBRBacktestStorage()
    cfg = _build_backtest_config(db, body)
    task_id = storage.create_task(cfg, name=body.task_name)
    start_backtest_async(task_id, cfg)
    return {"task_id": task_id, "status": "pending", "scope_meta": cfg.get("scope_meta")}


@router.get("/backtests")
def admin_list_backtests(limit: int = 50, _user: Admin = Depends(_require_admin)):
    return {"items": SBBRBacktestStorage().list_tasks(limit=limit)}


@router.get("/backtests/{task_id}")
def admin_get_backtest(task_id: str, _user: Admin = Depends(_require_admin)):
    row = SBBRBacktestStorage().get_task(task_id)
    if not row:
        raise HTTPException(404, "task not found")
    return row


@router.post("/precompute/trigger")
def admin_trigger_precompute(
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    _user: Admin = Depends(_require_admin),
):
    return run_sbbr_precompute(config_id=config_id, trade_date=trade_date)
