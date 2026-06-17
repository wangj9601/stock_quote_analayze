"""
GMS 回测管理端接口
提供：创建任务、列表/详情、日志、取消/删除、报告列表/详情/下载。
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from . import backtest_storage
from . import backtest_worker

logger = logging.getLogger(__name__)


def create_backtest(config: Dict[str, Any], name: Optional[str] = None) -> str:
    """
    创建回测任务并异步执行。
    config 应包含: task_name?, market, start_date, end_date, target_pct, horizon_days?, min_score?, stock_pool_mode? 等。
    返回 task_id。
    """
    task_id = backtest_storage.create_task(config, name=name or config.get("task_name"))
    backtest_worker.start_backtest(task_id)
    return task_id


def rerun_backtest(task_id: str) -> str:
    """
    按已有任务的 config 再创建并启动一个新任务（管理端「重新执行」）。
    进行中（pending/running）的任务不可重跑。
    """
    task = get_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    if task.get("status") in ("pending", "running"):
        raise ValueError("任务进行中，无法重新执行")
    cfg = deepcopy(task.get("config") or {})
    if not cfg:
        raise ValueError("任务参数缺失")
    name = (task.get("name") or cfg.get("task_name") or "").strip()
    new_name = f"{name}（重跑）" if name else None
    cfg.pop("task_name", None)
    return create_backtest(cfg, name=new_name)


def list_backtest_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """回测任务列表。"""
    return backtest_storage.list_tasks(status=status, limit=limit, offset=offset)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """任务详情（含参数与汇总）。"""
    return backtest_storage.get_task(task_id)


def get_logs(task_id: str) -> List[Dict[str, Any]]:
    """任务日志。"""
    return backtest_storage.get_task_logs(task_id)


def cancel_task(task_id: str) -> bool:
    """取消任务。"""
    backtest_worker.request_cancel(task_id)
    return backtest_storage.cancel_task(task_id)


def delete_task(task_id: str) -> bool:
    """删除任务及库内报告明细。"""
    backtest_worker.request_cancel(task_id)
    return backtest_storage.delete_task(task_id)


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """报告列表。"""
    return backtest_storage.list_reports(limit=limit, offset=offset)


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """报告详情。"""
    return backtest_storage.get_report(report_id)


def delete_report(report_id: str) -> bool:
    """删除历史报告（已完成任务记录）。"""
    return backtest_storage.delete_report(report_id)


def download_report(
    report_id: str, variant: Optional[str] = None
) -> Optional[Tuple[bytes, str, str]]:
    """
    返回报告明细字节与下载文件名、Content-Type（数据库存储）。
    variant: None 优先 xlsx；csv / xlsx 强制对应格式。
    """
    return backtest_storage.get_report_file_bytes(report_id, variant=variant)
