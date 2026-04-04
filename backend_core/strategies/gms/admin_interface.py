"""
GMS 回测管理端接口
提供：创建任务、列表/详情、日志、取消/删除、报告列表/详情/下载。
"""

import logging
from typing import Dict, List, Any, Optional

from backend_api.database import SessionLocal

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
    """删除任务及报告、明细文件。"""
    backtest_worker.request_cancel(task_id)
    return backtest_storage.delete_task(task_id)


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """报告列表。"""
    return backtest_storage.list_reports(limit=limit, offset=offset)


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """报告详情。"""
    return backtest_storage.get_report(report_id)


def download_report(report_id: str, variant: Optional[str] = None) -> Optional[str]:
    """
    返回报告明细文件的本地绝对路径，供 API 层 send_file。
    variant: None 使用报告记录的主明细文件（一般为 xlsx）；csv / xlsx 则强制对应扩展名。
    """
    v = (variant or "").strip().lower()
    if v == "csv":
        return backtest_storage.get_detail_path_by_ext(report_id, ".csv")
    if v in ("xlsx", "excel"):
        return backtest_storage.get_detail_path_by_ext(report_id, ".xlsx")
    return backtest_storage.get_details_path(report_id)
