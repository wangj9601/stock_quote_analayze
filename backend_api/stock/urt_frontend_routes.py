# -*- coding: utf-8 -*-
"""URT 前台：信号历史 / 计算明细 / 个股强制重算 API。"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import SessionLocal, engine, get_db
from backend_api.models import UrtTraceRecomputeTask
from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.data_loader import URTDataLoader
from backend_core.strategies.urt.signal_detector import build_buy_logic, evaluate_buy_signal
from backend_core.strategies.urt.trace_store import (
    get_trace_freshness,
    query_trace_by_code,
    recompute_trace_for_stock,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["URT Signal"])

_trace_recompute_table_ready = False
_trace_recompute_table_lock = threading.Lock()


def _ensure_trace_recompute_task_table() -> None:
    global _trace_recompute_table_ready
    if _trace_recompute_table_ready:
        return
    with _trace_recompute_table_lock:
        if _trace_recompute_table_ready:
            return
        try:
            UrtTraceRecomputeTask.__table__.create(bind=engine, checkfirst=True)
        except Exception as e:
            logger.warning("创建 urt_trace_recompute_tasks 表失败: %s", e)
            raise
        _trace_recompute_table_ready = True


def _normalize_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _task_row_to_dict(row: UrtTraceRecomputeTask) -> dict:
    return {
        "task_id": row.task_id,
        "status": row.status,
        "progress": row.progress,
        "message": row.message,
        "code": row.code,
        "config_id": row.config_id,
        "config_name": row.config_name,
        "current": row.current,
        "total": row.total,
        "saved_count": row.saved_count,
        "error": row.error,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
    }


def _find_running_trace_recompute(code: str, config_id: int) -> Optional[str]:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = (
            db.query(UrtTraceRecomputeTask)
            .filter(
                UrtTraceRecomputeTask.code == code,
                UrtTraceRecomputeTask.config_id == int(config_id),
                UrtTraceRecomputeTask.status.in_(("pending", "running")),
            )
            .order_by(UrtTraceRecomputeTask.created_at.desc())
            .first()
        )
        return row.task_id if row else None
    finally:
        db.close()


def _create_trace_recompute_task(task_id: str, fields: dict) -> None:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    now = datetime.now()
    try:
        row = UrtTraceRecomputeTask(
            task_id=task_id,
            status=fields.get("status", "pending"),
            progress=int(fields.get("progress") or 0),
            message=fields.get("message"),
            code=fields.get("code"),
            config_id=int(fields.get("config_id") or 0),
            config_name=fields.get("config_name"),
            current=int(fields.get("current") or 0),
            total=int(fields.get("total") or 0),
            saved_count=fields.get("saved_count"),
            error=fields.get("error"),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("创建 URT 重算任务失败 task_id=%s: %s", task_id, e)
        raise
    finally:
        db.close()


def _update_trace_recompute_task(task_id: str, **fields) -> None:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = db.query(UrtTraceRecomputeTask).filter(UrtTraceRecomputeTask.task_id == task_id).first()
        if not row:
            return
        for key, val in fields.items():
            if hasattr(row, key):
                setattr(row, key, val)
        row.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("更新 URT 重算任务失败 task_id=%s: %s", task_id, e)
    finally:
        db.close()


def _get_trace_recompute_task(task_id: str) -> Optional[dict]:
    _ensure_trace_recompute_task_table()
    db = SessionLocal()
    try:
        row = db.query(UrtTraceRecomputeTask).filter(UrtTraceRecomputeTask.task_id == task_id).first()
        if not row:
            return None
        return _task_row_to_dict(row)
    finally:
        db.close()


def _resolve_config_id(db: Session, config_id: Optional[int], cm: URTConfigManager) -> int:
    """解析策略版本：显式 id 优先，否则取生效（is_default）版本。"""
    cm.ensure_default_row(db)
    if config_id is not None:
        return int(config_id)
    effective = cm.resolve_effective_config_id(db)
    if effective is not None:
        return int(effective)
    configs = cm.list_configs(db, active_only=True)
    if configs:
        return int(configs[0]["id"])
    raise HTTPException(status_code=400, detail="无可用 URT 参数版本")


def _config_alignment_meta(cm: URTConfigManager, db: Session, resolved: int) -> Dict[str, Any]:
    effective_id = cm.resolve_effective_config_id(db)
    return {
        "config_id": int(resolved),
        "effective_config_id": int(effective_id) if effective_id is not None else None,
        "is_effective_config": bool(
            effective_id is not None and int(resolved) == int(effective_id)
        ),
        "config_name": _config_display_name(cm, db, int(resolved)),
    }


def _config_display_name(cm: URTConfigManager, db: Session, config_id: int) -> str:
    configs = cm.list_configs(db, active_only=False)
    for c in configs:
        if int(c.get("id") or 0) == int(config_id):
            name = c.get("name") or f"配置{config_id}"
            return f"{name} (默认)" if c.get("is_default") else str(name)
    return f"配置{config_id}"


class UrtTraceRecomputeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    config_id: Optional[int] = Field(None, ge=1, description="URT 策略参数版本 ID")


def _run_trace_recompute_background(
    task_id: str,
    code: str,
    config_id: int,
    config: dict,
    config_display: str,
) -> None:
    db = SessionLocal()
    try:
        _update_trace_recompute_task(task_id, status="running", message="正在清除旧记录…", progress=0)

        def progress_cb(current: int, total: int, msg: str) -> None:
            pct = int(round(current * 100 / total)) if total else 0
            _update_trace_recompute_task(
                task_id,
                progress=min(99, pct),
                message=msg,
                current=current,
                total=total,
            )

        count = recompute_trace_for_stock(
            db,
            code=code,
            config_id=config_id,
            config=config,
            progress_cb=progress_cb,
        )
        _update_trace_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=count,
            current=count,
            total=count,
            message=f"已按「{config_display}」重新计算，写入 {count} 条",
        )
        logger.info("URT 追溯异步重算完成: %s config_id=%s, 写入 %s 条", code, config_id, count)
    except Exception as e:
        logger.exception("URT 追溯异步重算失败 task_id=%s", task_id)
        _update_trace_recompute_task(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )
    finally:
        db.close()


@router.get("/urt-signal-trace")
async def get_urt_signal_trace(
    code: str = Query(..., description="股票代码"),
    config_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    try:
        cm = URTConfigManager()
        cm.ensure_default_row(db)
        configs = cm.list_configs(db, active_only=True)
        resolved = _resolve_config_id(db, config_id, cm)
        align = _config_alignment_meta(cm, db, resolved)
        code_n = _normalize_code(code)
        start_s = str(start_date).strip()[:10] if start_date else None
        end_s = str(end_date).strip()[:10] if end_date else None
        if start_s and end_s and start_s > end_s:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        rows = query_trace_by_code(
            db,
            code=code_n,
            config_id=resolved,
            start_date=start_s or None,
            end_date=end_s or None,
            limit=limit,
        )
        cfg = cm.get_config(resolved, db=db)
        for row in rows:
            bl = build_buy_logic(row, cfg)
            row["buy_logic"] = bl
            row["filter_ok"] = bl.get("filter_ok")
            row["score_ok"] = bl.get("score_ok")
            row["filter_reason"] = bl.get("filter_reason") or None
        freshness = get_trace_freshness(db, config_id=int(resolved), code=code_n)
        return {
            "success": True,
            "code": code_n,
            "config_id": resolved,
            "effective_config_id": align.get("effective_config_id"),
            "is_effective_config": align.get("is_effective_config"),
            "config_name": align.get("config_name"),
            "config_updated_at": freshness.get("config_updated_at"),
            "trace_computed_at": freshness.get("trace_computed_at"),
            "stale": freshness.get("stale"),
            "need_recompute": freshness.get("need_recompute"),
            "configs": configs,
            "start_date": start_s,
            "end_date": end_s,
            "data": rows,
            "total": len(rows),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("urt-signal-trace 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/urt-signal-trace/recompute")
async def start_urt_signal_trace_recompute(
    body: UrtTraceRecomputeRequest,
    db: Session = Depends(get_db),
):
    """
    异步强制重新计算单股 URT 信号历史（当前 config_id）。
    返回 task_id，前端轮询 GET /urt-signal-trace/recompute/{task_id} 获取进度。
    """
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    cm = URTConfigManager()
    resolved_config_id = _resolve_config_id(db, body.config_id, cm)
    config = cm.get_config(resolved_config_id, db=db)
    config_display = _config_display_name(cm, db, resolved_config_id)

    existing = _find_running_trace_recompute(code, resolved_config_id)
    if existing:
        return JSONResponse(
            {
                "success": True,
                "data": {"task_id": existing, "already_running": True},
                "message": "该股票当前策略版本正在重新计算，请稍候",
            }
        )

    task_id = f"urt_trace_recompute_{uuid.uuid4().hex[:12]}"
    _create_trace_recompute_task(
        task_id,
        {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "任务已创建，等待执行…",
            "code": code,
            "config_id": resolved_config_id,
            "config_name": config_display,
            "current": 0,
            "total": 0,
            "saved_count": None,
            "error": None,
        },
    )

    thread = threading.Thread(
        target=_run_trace_recompute_background,
        args=(task_id, code, resolved_config_id, config, config_display),
        daemon=True,
    )
    thread.start()

    return JSONResponse(
        {
            "success": True,
            "data": {
                "task_id": task_id,
                "config_id": resolved_config_id,
                "config_name": config_display,
            },
        }
    )


@router.get("/urt-signal-trace/recompute/{task_id}")
async def get_urt_signal_trace_recompute_status(task_id: str):
    """查询 URT 信号历史强制重算任务进度。"""
    task = _get_trace_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})


@router.get("/urt-score-detail")
async def get_urt_score_detail(
    code: str = Query(...),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD"),
    config_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """URT 信号计算明细：优先 trace.score_detail，否则实时重算。"""
    try:
        cm = URTConfigManager()
        cm.ensure_default_row(db)
        resolved = _resolve_config_id(db, config_id, cm)
        align = _config_alignment_meta(cm, db, resolved)
        cfg = cm.get_config(resolved, db=db)
        code_n = _normalize_code(code)
        freshness = get_trace_freshness(db, config_id=int(resolved), code=code_n)

        # 优先读缓存
        if date:
            from backend_api.models import URTSignalTrace

            cached = (
                db.query(URTSignalTrace)
                .filter(
                    URTSignalTrace.code == code_n,
                    URTSignalTrace.date == str(date)[:10],
                    URTSignalTrace.config_id == int(resolved),
                )
                .first()
            )
            if cached and cached.score_detail:
                fields = {
                    "close": cached.close,
                    "open": cached.open,
                    "ma20": cached.ma20,
                    "yang_count_4": cached.yang_count_4,
                    "yang_count_5": cached.yang_count_5,
                    "volume_multiple": cached.volume_multiple,
                    "volume_ratio": cached.volume_ratio,
                    "turnover_rate": cached.turnover_rate,
                    "filter_reason": None,
                }
                buy_logic = build_buy_logic(
                    {
                        **fields,
                        "score": cached.score,
                        "buy_signal": cached.buy_signal,
                        "score_detail": cached.score_detail,
                    },
                    cfg,
                )
                fields["filter_ok"] = buy_logic.get("filter_ok")
                fields["score_ok"] = buy_logic.get("score_ok")
                fields["filter_reason"] = buy_logic.get("filter_reason") or None
                sd = cached.score_detail if isinstance(cached.score_detail, dict) else {}
                st = sd.get("structure") if isinstance(sd.get("structure"), dict) else {}
                fields["nearest_support"] = st.get("nearest_support")
                fields["nearest_resistance"] = st.get("nearest_resistance")
                return {
                    "success": True,
                    "source": "urt_signal_trace",
                    "code": code_n,
                    "name": cached.name,
                    "date": cached.date,
                    "config_id": resolved,
                    "effective_config_id": align.get("effective_config_id"),
                    "is_effective_config": align.get("is_effective_config"),
                    "config_name": align.get("config_name"),
                    "config_updated_at": freshness.get("config_updated_at"),
                    "trace_computed_at": freshness.get("trace_computed_at"),
                    "stale": freshness.get("stale"),
                    "need_recompute": freshness.get("need_recompute"),
                    "buy_signal": cached.buy_signal,
                    "score": cached.score,
                    "score_detail": cached.score_detail,
                    "buy_logic": buy_logic,
                    "filter_ok": buy_logic.get("filter_ok"),
                    "score_ok": buy_logic.get("score_ok"),
                    "filter_reason": buy_logic.get("filter_reason") or None,
                    "support_levels": st.get("support_levels") or [],
                    "resistance_levels": st.get("resistance_levels") or [],
                    "nearest_support": st.get("nearest_support"),
                    "nearest_resistance": st.get("nearest_resistance"),
                    "fields": fields,
                }

        from backend_core.strategies.urt.signal_detector import history_calendar_days_for_fetch

        loader = URTDataLoader(db)
        effective = URTDataLoader.resolve_effective_history_end_date(db, date)
        start_s, end_s = URTDataLoader.default_date_window(
            history_calendar_days_for_fetch(cfg), effective
        )
        hist = loader.fetch_historical_desc(code_n, start_date=start_s, end_date=end_s)
        hist = [b for b in hist if str(b.get("date") or "")[:10] <= effective]
        detail = evaluate_buy_signal(hist, cfg, require_pass=False)
        if not detail:
            raise HTTPException(status_code=404, detail="数据不足，无法计算明细")
        sd = detail.get("score_detail") if isinstance(detail.get("score_detail"), dict) else {}
        st = sd.get("structure") if isinstance(sd.get("structure"), dict) else {}
        return {
            "success": True,
            "source": "realtime",
            "code": code_n,
            "name": (hist[0].get("name") if hist else None),
            "date": detail.get("signal_date"),
            "config_id": resolved,
            "effective_config_id": align.get("effective_config_id"),
            "is_effective_config": align.get("is_effective_config"),
            "config_name": align.get("config_name"),
            "config_updated_at": freshness.get("config_updated_at"),
            "trace_computed_at": freshness.get("trace_computed_at"),
            "stale": False,
            "need_recompute": freshness.get("need_recompute"),
            "buy_signal": detail.get("buy_signal"),
            "score": detail.get("score"),
            "score_detail": detail.get("score_detail"),
            "buy_logic": detail.get("buy_logic"),
            "filter_ok": detail.get("filter_ok"),
            "score_ok": detail.get("score_ok"),
            "filter_reason": detail.get("filter_reason"),
            "support_levels": detail.get("support_levels") or st.get("support_levels") or [],
            "resistance_levels": detail.get("resistance_levels") or st.get("resistance_levels") or [],
            "nearest_support": detail.get("nearest_support", st.get("nearest_support")),
            "nearest_resistance": detail.get("nearest_resistance", st.get("nearest_resistance")),
            "fields": {
                "close": detail.get("close"),
                "open": detail.get("open"),
                "ma20": detail.get("ma20"),
                "above_ma20": detail.get("above_ma20"),
                "yang_count_4": detail.get("yang_count_4"),
                "yang_count_5": detail.get("yang_count_5"),
                "rule_a_ok": detail.get("rule_a_ok"),
                "rule_b_ok": detail.get("rule_b_ok"),
                "volume_multiple": detail.get("volume_multiple"),
                "volume_ratio": detail.get("volume_ratio"),
                "turnover_rate": detail.get("turnover_rate"),
                "filter_ok": detail.get("filter_ok"),
                "filter_reason": detail.get("filter_reason"),
                "score_ok": detail.get("score_ok"),
                "nearest_support": detail.get("nearest_support", st.get("nearest_support")),
                "nearest_resistance": detail.get("nearest_resistance", st.get("nearest_resistance")),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("urt-score-detail 失败")
        raise HTTPException(status_code=500, detail=str(e))


class URTStockBacktestBody(BaseModel):
    """信号追溯页发起的单股 URT 回测（与管理端 stock_pool_mode=single 等价）。"""

    code: str = Field(..., description="股票代码")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    target_pct: float = Field(0.10, description="目标涨幅，如 0.10 表示 10%")
    horizon_days: int = Field(10, ge=10, le=30, description="持有窗口交易日数（短线默认 10）")
    min_score: Optional[float] = Field(None, ge=0, le=100, description="最低得分")
    use_trace: bool = Field(True, description="是否优先读信号追溯表")
    exit_mode: str = Field("hit_rate", description="hit_rate | risk_exit")
    strategy_config_id: Optional[int] = Field(None, ge=1, description="URT 策略参数版本 ID")


@router.post("/urt-backtest")
async def create_urt_stock_backtest(body: URTStockBacktestBody, db: Session = Depends(get_db)):
    """创建单股 URT 回测任务，供追溯页使用（无需 admin token）。"""
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        from backend_api.admin.urt_admin_routes import BacktestCreateBody, _build_backtest_config
        from backend_core.strategies.urt import backtest_storage, backtest_worker

        bt_body = BacktestCreateBody(
            start_date=str(body.start_date).strip()[:10],
            end_date=str(body.end_date).strip()[:10],
            strategy_config_id=body.strategy_config_id,
            target_pct=float(body.target_pct),
            horizon_days=int(body.horizon_days),
            min_score=body.min_score,
            use_trace=bool(body.use_trace),
            exit_mode=body.exit_mode or "hit_rate",
            stock_pool_mode="single",
            stock_code=code,
        )
        config = _build_backtest_config(db, bt_body)
        task_name = f"URT单股回测_{code}_{body.start_date[:10]}"
        task_id = backtest_storage.create_task(config, name=task_name)
        backtest_worker.start_backtest_task(task_id)
        return {"success": True, "data": {"task_id": task_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建 URT 单股回测任务失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/urt-backtest/{task_id}")
async def get_urt_stock_backtest(task_id: str, db: Session = Depends(get_db)):
    """查询 URT 回测任务状态与结果。"""
    from backend_api.admin.urt_admin_routes import _attach_urt_trade_meta
    from backend_core.strategies.urt import backtest_storage

    row = backtest_storage.get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    if not cfg.get("trade_logic") or not cfg.get("risk_params"):
        try:
            patched = _attach_urt_trade_meta(db, dict(cfg))
            cfg = {**cfg, "trade_logic": patched.get("trade_logic"), "risk_params": patched.get("risk_params")}
            row = {**row, "config": cfg}
        except Exception:
            logger.exception("URT 前台回测详情补齐交易逻辑失败 task=%s", task_id)
    if summary and (not summary.get("trade_logic") or not summary.get("risk_params")):
        row = {
            **row,
            "summary": {
                **summary,
                "trade_logic": summary.get("trade_logic") or cfg.get("trade_logic"),
                "risk_params": summary.get("risk_params") or cfg.get("risk_params"),
            },
        }
    return {"success": True, "data": row}


@router.get("/urt-backtest/{task_id}/export")
async def export_urt_stock_backtest(task_id: str):
    """导出 URT 回测明细 CSV。"""
    from backend_core.strategies.urt import backtest_storage

    raw = backtest_storage.get_details_csv(task_id)
    if not raw:
        raise HTTPException(status_code=404, detail="明细不存在或任务未完成")
    return Response(
        content=raw,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="urt_backtest_{task_id[:8]}.csv"'},
    )
