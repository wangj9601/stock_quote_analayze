"""
GMS 回测后台执行 worker
在后台线程中执行 backtest_runner，更新进度与日志，完成后写入 storage 并生成报告。
"""

import logging
import threading
from typing import Set

from backend_api.database import SessionLocal

from . import backtest_storage
from .backtest_runner import run_gms_backtest

logger = logging.getLogger(__name__)

_cancelled_tasks: Set[str] = set()
_lock = threading.Lock()


def request_cancel(task_id: str) -> None:
    """请求取消任务（正在运行的任务会在下一次检查时退出）。"""
    with _lock:
        _cancelled_tasks.add(task_id)


def _run_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = backtest_storage.get_task(task_id)
        if not task or task.get("status") != "pending":
            return
        config = task.get("config") or {}
        market = config.get("market", "all")
        start_date = config.get("start_date")
        end_date = config.get("end_date")
        target_pct = float(config.get("target_pct", 0.05))
        horizon_days = int(config.get("horizon_days", 20))
        min_score = float(config.get("min_score", 0))
        # 股票池：单股(stock_code) -> [code]；自定义(stock_pool) -> 列表；全市场 -> None
        stock_pool = config.get("stock_pool")
        if stock_pool is None and config.get("stock_code"):
            code = str(config.get("stock_code")).strip()
            if code:
                stock_pool = [code]
        if stock_pool is not None:
            if not isinstance(stock_pool, list):
                stock_pool = [stock_pool]
            stock_pool = [str(c).strip() for c in stock_pool if str(c).strip()]
            if not stock_pool:
                stock_pool = None

        if not start_date or not end_date:
            backtest_storage.fail_task(task_id, "缺少 start_date 或 end_date")
            return

        def progress_cb(percent: int, message: str) -> None:
            backtest_storage.update_task_progress(task_id, percent, message, log_line=message)

        def cancel_check() -> bool:
            with _lock:
                if task_id in _cancelled_tasks:
                    return True
            t = backtest_storage.get_task(task_id)
            return t and t.get("status") == "cancelled"

        backtest_storage.update_task_progress(task_id, 0, "开始回测", log_line="开始回测")
        result = run_gms_backtest(
            db=db,
            start_date=start_date,
            end_date=end_date,
            market=market,
            target_pct=target_pct,
            horizon_days=horizon_days,
            min_score=min_score,
            stock_pool=stock_pool,
            progress_callback=progress_cb,
            cancel_check=cancel_check,
        )
        summary = result.get("summary") or {}
        details = result.get("details") or []
        backtest_storage.save_details_csv(task_id, details)
        details_path = backtest_storage.save_details_xlsx(task_id, details)
        backtest_storage.complete_task(task_id, summary, details_path=details_path)
        backtest_storage.update_task_progress(task_id, 100, "回测完成", log_line="回测完成")
    except Exception as e:
        logger.exception("GMS 回测执行异常 %s", task_id)
        backtest_storage.fail_task(task_id, str(e))
    finally:
        with _lock:
            _cancelled_tasks.discard(task_id)
        db.close()


def start_backtest(task_id: str) -> None:
    """在后台线程中启动回测。"""
    th = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
    th.start()
    logger.info("GMS 回测任务已启动: %s", task_id)
