# -*- coding: utf-8 -*-
"""CSB 信号定时预计算。

日终/区间入库与选股门槛分离：默认只写入「买点且 score≥地板分」（默认 50，
可用 CSB_PRECOMPUTE_MIN_SCORE 或配置 precompute_min_score 覆盖）；
选股/回测读侧仍按版本 min_score（默认 80）过滤。扫描占位仍写。
"""

from __future__ import annotations

import copy
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE_MIN_SCORE = 50.0

# 进程内区间刷新进度（与 daemon 线程同进程；多 worker 时仅本 worker 可见）
_TRACE_REFRESH_LOCK = threading.Lock()
_TRACE_REFRESH_STATUS: Dict[int, Dict[str, Any]] = {}


def resolve_csb_precompute_storage_min_score(cfg: Optional[Dict[str, Any]] = None) -> float:
    """预计算入库地板分。环境变量优先，其次配置，默认 50。"""
    raw = (os.getenv("CSB_PRECOMPUTE_MIN_SCORE") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            pass
    if isinstance(cfg, dict) and cfg.get("precompute_min_score") is not None:
        try:
            return max(0.0, float(cfg.get("precompute_min_score")))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_STORAGE_MIN_SCORE


def cfg_with_precompute_storage_floor(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """扫描用配置：把 min_score 换成入库地板分，其它参数不变。"""
    out = copy.deepcopy(cfg or {})
    out["min_score"] = resolve_csb_precompute_storage_min_score(cfg)
    return out


def filter_csb_rows_for_storage(
    rows: List[Dict[str, Any]],
    *,
    min_score: float,
) -> List[Dict[str, Any]]:
    """保留买点且 score≥地板分的行（与 screen(require_entry=True) 口径一致）。"""
    kept: List[Dict[str, Any]] = []
    floor = float(min_score)
    for r in rows or []:
        if not (r.get("entry_signal") or r.get("buy_signal")):
            continue
        try:
            score = float(r.get("score") if r.get("score") is not None else -1)
        except (TypeError, ValueError):
            score = -1.0
        if score >= floor:
            kept.append(r)
    return kept


def get_csb_trace_refresh_status(config_id: Optional[int] = None) -> Dict[str, Any]:
    """查询区间强制刷新进度。config_id 为空时返回最近一次任务。"""
    with _TRACE_REFRESH_LOCK:
        if config_id is not None:
            st = _TRACE_REFRESH_STATUS.get(int(config_id))
            return dict(st) if st else {"phase": "idle", "config_id": int(config_id)}
        if not _TRACE_REFRESH_STATUS:
            return {"phase": "idle"}
        latest = max(
            _TRACE_REFRESH_STATUS.values(),
            key=lambda x: str(x.get("started_at") or ""),
        )
        return dict(latest)


def _set_csb_trace_refresh_status(config_id: int, **fields: Any) -> None:
    cid = int(config_id)
    with _TRACE_REFRESH_LOCK:
        cur = dict(_TRACE_REFRESH_STATUS.get(cid) or {})
        cur.update(fields)
        cur["config_id"] = cid
        cur["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _TRACE_REFRESH_STATUS[cid] = cur


def begin_csb_trace_refresh_status(
    config_id: int,
    *,
    start_date: str,
    end_date: str,
    purge_first: bool,
) -> tuple[Dict[str, Any], bool]:
    """启动前写入 running。返回 (状态, already_running)。"""
    cid = int(config_id)
    with _TRACE_REFRESH_LOCK:
        cur = _TRACE_REFRESH_STATUS.get(cid)
        if cur and str(cur.get("phase") or "") == "running":
            return dict(cur), True
        st = {
            "phase": "running",
            "config_id": cid,
            "start_date": str(start_date)[:10],
            "end_date": str(end_date)[:10],
            "purge_first": bool(purge_first),
            "progress": 0,
            "message": "已启动，准备删除区间内旧 trace…",
            "purged_rows": 0,
            "precompute_hits": 0,
            "precomputed_days": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "error": None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        _TRACE_REFRESH_STATUS[cid] = st
        return dict(st), False


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def resolve_csb_trade_date(db) -> str:
    from backend_api.models import HistoricalQuotes

    latest = db.query(func.max(HistoricalQuotes.date)).scalar()
    if latest:
        return latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)[:10]
    return datetime.now().strftime("%Y-%m-%d")


def list_precompute_config_ids(db) -> List[int]:
    from backend_api.models import CSBStrategyConfig

    rows = (
        db.query(CSBStrategyConfig.id)
        .filter(
            CSBStrategyConfig.is_active.is_(True),
            (
                (CSBStrategyConfig.is_default.is_(True))
                | (CSBStrategyConfig.precompute_enabled.is_(True))
            ),
        )
        .order_by(CSBStrategyConfig.id.asc())
        .all()
    )
    return [int(r[0]) for r in rows]


def run_csb_precompute_for_config(
    config_id: int,
    *,
    trade_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine
    from backend_core.strategies.csb.trace_store import mark_date_scanned, upsert_trace_rows

    db = SessionLocal()
    started = datetime.now()
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(config_id, db=db)
        storage_floor = resolve_csb_precompute_storage_min_score(cfg)
        scan_cfg = cfg_with_precompute_storage_floor(cfg)
        loader = CSBDataLoader(db)
        date_s = trade_date or resolve_csb_trade_date(db)
        date_s = loader.resolve_effective_trade_date(date_s)
        stocks = loader.list_a_share_candidates(limit=limit)
        engine = CSBStrategyEngine(loader, scan_cfg)
        hits = engine.screen(
            stocks, as_of_end_date=date_s, require_entry=True, max_results=0
        )
        written = upsert_trace_rows(db, config_id=config_id, rows=hits)
        mark_date_scanned(
            db,
            config_id=config_id,
            trade_date=date_s,
            extra={
                "hits": len(hits),
                "candidates": len(stocks),
                "scope": "full_market",
                "written": written,
                "storage_min_score": storage_floor,
                "selection_min_score": cfg.get("min_score"),
            },
        )
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "CSB 预计算完成 config_id=%s date=%s hits=%s written=%s floor=%.1f elapsed=%.1fs",
            config_id, date_s, len(hits), written, storage_floor, elapsed,
        )
        return {
            "success": True,
            "config_id": config_id,
            "trade_date": date_s,
            "candidates": len(stocks),
            "hits": len(hits),
            "written": written,
            "storage_min_score": storage_floor,
            "selection_min_score": cfg.get("min_score"),
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        logger.exception("CSB 预计算失败 config_id=%s: %s", config_id, e)
        return {"success": False, "config_id": config_id, "error": str(e)}
    finally:
        db.close()


def run_csb_trace_refresh_range(
    config_id: int,
    *,
    start_date: str,
    end_date: str,
    purge_first: bool = True,
    stock_pool: Optional[List[str]] = None,
) -> dict:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.backtest_runner import _ensure_trace_for_backtest_range, _trading_dates
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.strategy_engine import CSBStrategyEngine
    from backend_core.strategies.csb.trace_store import delete_trace_for_config_in_range

    started = datetime.now()
    cid = int(config_id)
    _set_csb_trace_refresh_status(
        cid,
        phase="running",
        start_date=str(start_date)[:10],
        end_date=str(end_date)[:10],
        purge_first=bool(purge_first),
        progress=1,
        message="删除区间内旧 trace…",
        error=None,
        finished_at=None,
    )
    db = SessionLocal()
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(cid, db=db)
        storage_floor = resolve_csb_precompute_storage_min_score(cfg)
        scan_cfg = cfg_with_precompute_storage_floor(cfg)
        # 仅删区间内数据；整版清空请用「清空该版本 trace」
        purged = (
            delete_trace_for_config_in_range(
                db,
                config_id=cid,
                start_date=str(start_date)[:10],
                end_date=str(end_date)[:10],
            )
            if purge_first
            else 0
        )
        _set_csb_trace_refresh_status(
            cid,
            purged_rows=purged,
            progress=5,
            message=f"已删除区间内 {purged} 行，开始全市场扫描…",
        )
        dates = _trading_dates(db, start_date, end_date)
        if not dates:
            err = "区间内无交易日"
            _set_csb_trace_refresh_status(
                cid,
                phase="failed",
                progress=100,
                message=err,
                error=err,
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
            return {"success": False, "error": err, "purged_rows": purged}

        def _progress(pct: int, msg: str) -> None:
            # 删除阶段占 0～5，扫描占 5～99
            mapped = 5 + int(max(0, min(100, pct)) * 0.94)
            _set_csb_trace_refresh_status(cid, progress=mapped, message=msg)

        loader = CSBDataLoader(db)
        # 区间补算按入库地板分落库；选股/回测读侧仍用版本 min_score
        engine = CSBStrategyEngine(loader, scan_cfg)
        meta = _ensure_trace_for_backtest_range(
            db,
            dates=dates,
            config_id=cid,
            cfg=cfg,
            loader=loader,
            engine=engine,
            stock_pool=stock_pool,
            progress_cb=_progress,
            progress_start=0,
            progress_end=100,
        )
        elapsed = (datetime.now() - started).total_seconds()
        result = {
            "success": True,
            "config_id": cid,
            "start_date": str(start_date)[:10],
            "end_date": str(end_date)[:10],
            "purged_rows": purged,
            "elapsed_sec": elapsed,
            **meta,
        }
        _set_csb_trace_refresh_status(
            cid,
            phase="completed",
            progress=100,
            message=(
                f"完成：删除 {purged} 行，补算 {int(meta.get('precomputed_days') or 0)} 日，"
                f"买点 {int(meta.get('precompute_hits') or 0)} 条，耗时 {elapsed:.0f}s"
            ),
            purged_rows=purged,
            precompute_hits=int(meta.get("precompute_hits") or 0),
            precomputed_days=int(meta.get("precomputed_days") or 0),
            finished_at=datetime.now().isoformat(timespec="seconds"),
            error=None,
        )
        return result
    except Exception as e:
        logger.exception("CSB 区间 trace 刷新失败: %s", e)
        _set_csb_trace_refresh_status(
            cid,
            phase="failed",
            progress=100,
            message=f"失败：{e}",
            error=str(e),
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def scheduled_csb_signals_cn() -> None:
    if datetime.now().weekday() >= 5:
        return
    if not _env_bool("ENABLE_CSB_PRECOMPUTE", True):
        return
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        ids = list_precompute_config_ids(db)
    finally:
        db.close()
    for cid in ids:
        run_csb_precompute_for_config(cid)
