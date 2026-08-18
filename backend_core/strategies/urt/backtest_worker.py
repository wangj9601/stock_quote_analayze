# -*- coding: utf-8 -*-
"""URT 回测后台 worker。"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Set

from backend_api.database import SessionLocal

from . import backtest_storage
from .backtest_runner import run_urt_backtest

logger = logging.getLogger(__name__)

_cancelled: Set[str] = set()
_lock = threading.Lock()


def request_cancel(task_id: str) -> None:
    with _lock:
        _cancelled.add(task_id)


def _run_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = backtest_storage.get_task(task_id)
        if not task or task.get("status") != "pending":
            return
        cfg = task.get("config") or {}
        start_date = cfg.get("start_date")
        end_date = cfg.get("end_date")
        if not start_date or not end_date:
            backtest_storage.fail_task(task_id, "缺少 start_date 或 end_date")
            return

        def progress_cb(percent: int, message: str) -> None:
            backtest_storage.update_task_progress(task_id, percent, message, log_line=message)

        def cancel_check() -> bool:
            with _lock:
                if task_id in _cancelled:
                    return True
            t = backtest_storage.get_task(task_id)
            return bool(t and t.get("status") == "cancelled")

        backtest_storage.update_task_progress(task_id, 0, "开始回测", log_line="开始回测")
        stock_pool = cfg.get("stock_pool")
        if stock_pool is None and cfg.get("stock_code"):
            stock_pool = [cfg.get("stock_code")]

        result = run_urt_backtest(
            db,
            start_date=str(start_date)[:10],
            end_date=str(end_date)[:10],
            strategy_config_id=cfg.get("strategy_config_id") or cfg.get("config_id"),
            target_pct=float(cfg.get("target_pct", 0.10)),
            horizon_days=int(cfg.get("horizon_days", 20)),
            min_score=cfg.get("min_score"),
            use_trace=bool(cfg.get("use_trace", True)),
            stock_pool=stock_pool if isinstance(stock_pool, list) else None,
            exit_mode=str(cfg.get("exit_mode") or "hit_rate"),
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )
        if cancel_check():
            backtest_storage.cancel_task(task_id)
            return
        backtest_storage.complete_task(
            task_id,
            summary=result.get("summary") or {},
            details_rows=result.get("details") or [],
        )
        if cfg.get("is_hit_rate_compare") and cfg.get("paired_from_task_id"):
            sm = result.get("summary") or {}
            backtest_storage.patch_task_summary(
                str(cfg.get("paired_from_task_id")),
                {
                    "paired_hit_rate_task_id": task_id,
                    "paired_hit_rate_summary": {
                        "task_id": task_id,
                        "total_signals": sm.get("total_signals"),
                        "hit_rate": sm.get("hit_rate"),
                        "win_rate": sm.get("win_rate"),
                        "avg_pnl_pct": sm.get("avg_pnl_pct"),
                        "avg_max_gain_pct": sm.get("avg_max_gain_pct"),
                        "avg_bars_held": sm.get("avg_bars_held"),
                    },
                },
            )
        _maybe_start_hit_rate_compare(task_id)
    except Exception as e:
        logger.exception("URT 回测任务失败 %s", task_id)
        backtest_storage.fail_task(task_id, str(e))
    finally:
        with _lock:
            _cancelled.discard(task_id)
        db.close()


def _maybe_start_hit_rate_compare(parent_id: str) -> Optional[str]:
    """结构/纪律出场完成后，同配置自动排队一条 hit_rate 对照任务。"""
    parent = backtest_storage.get_task(parent_id)
    if not parent:
        return None
    cfg = parent.get("config") if isinstance(parent.get("config"), dict) else {}
    mode = str(cfg.get("exit_mode") or "hit_rate").strip().lower()
    if mode not in ("structure_exit", "risk_exit"):
        return None
    if cfg.get("is_hit_rate_compare"):
        return None
    if cfg.get("compare_hit_rate") is False:
        return None
    existing = str(cfg.get("paired_hit_rate_task_id") or "").strip()
    if existing:
        child = backtest_storage.get_task(existing)
        if child and child.get("status") == "pending":
            start_backtest_task(existing)
            return existing
        return existing

    child_cfg = dict(cfg)
    child_cfg["exit_mode"] = "hit_rate"
    child_cfg["compare_hit_rate"] = False
    child_cfg["is_hit_rate_compare"] = True
    child_cfg["paired_from_task_id"] = parent_id
    parent_name = str(parent.get("name") or "URT回测")
    child_name = f"{parent_name}_命中率对照"
    child_id = backtest_storage.create_task(child_cfg, name=child_name)
    backtest_storage.patch_task_config(parent_id, {"paired_hit_rate_task_id": child_id})
    backtest_storage.patch_task_summary(
        parent_id,
        {
            "paired_hit_rate_task_id": child_id,
            "paired_hit_rate_name": child_name,
        },
    )
    start_backtest_task(child_id)
    logger.info("URT 已自动创建 hit_rate 对照任务 parent=%s child=%s", parent_id[:8], child_id[:8])
    return child_id


def start_backtest_task(task_id: str) -> None:
    t = threading.Thread(target=_run_task, args=(task_id,), daemon=True, name=f"urt-bt-{task_id[:8]}")
    t.start()
