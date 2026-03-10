"""
GMS 回测任务与报告持久化（文件存储）
任务元数据、进度、日志与报告产物存放在 backend_core/strategies/gms/backtest_data/ 下。
"""

import json
import logging
import os
import threading
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 存储根目录（与本文件同级的 backtest_data）
_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_data")
_TASKS_DIR = os.path.join(_BASE_DIR, "tasks")
_REPORTS_DIR = os.path.join(_BASE_DIR, "reports")
_DETAILS_DIR = os.path.join(_BASE_DIR, "details")
_INDEX_FILE = os.path.join(_BASE_DIR, "task_index.json")
_INDEX_LOCK = threading.Lock()


def _ensure_dirs():
    for d in (_BASE_DIR, _TASKS_DIR, _REPORTS_DIR, _DETAILS_DIR):
        os.makedirs(d, exist_ok=True)


def _load_index() -> Dict[str, Dict[str, Any]]:
    _ensure_dirs()
    if not os.path.isfile(_INDEX_FILE):
        return {}
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        # 容错：若出现 “Extra data”，通常是多段 JSON 被拼接在一起
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(content)
        return obj if isinstance(obj, dict) else {}
    except Exception as e:
        logger.warning("读取 task_index 失败: %s", e)
        return {}


def _save_index(index: Dict[str, Dict[str, Any]]) -> None:
    _ensure_dirs()
    tmp = _INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _INDEX_FILE)


def _set_index_entry(task_id: str, created_at: Optional[str] = None, status: Optional[str] = None) -> None:
    """进程内锁保护下更新 task_index（原子写入）。"""
    with _INDEX_LOCK:
        index = _load_index()
        entry = index.get(task_id) or {}
        if created_at is not None:
            entry["created_at"] = created_at
        if status is not None:
            entry["status"] = status
        index[task_id] = entry
        _save_index(index)


def create_task(config: Dict[str, Any], name: Optional[str] = None) -> str:
    """创建任务记录，返回 task_id。"""
    _ensure_dirs()
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    task = {
        "task_id": task_id,
        "name": name or config.get("task_name") or f"GMS回测_{task_id[:8]}",
        "config": config,
        "status": "pending",
        "progress": 0,
        "message": "",
        "logs": [],
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "summary": None,
        "details_path": None,
        "error": None,
    }
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    _set_index_entry(task_id, created_at=now, status="pending")
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务详情。"""
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("读取任务 %s 失败: %s", task_id, e)
        return None


def update_task_progress(task_id: str, progress: int, message: str = "", log_line: Optional[str] = None) -> bool:
    """更新任务进度与可选日志。"""
    task = get_task(task_id)
    if not task:
        return False
    task["progress"] = progress
    task["message"] = message
    if log_line is not None:
        task.setdefault("logs", []).append({"ts": datetime.utcnow().isoformat(), "text": log_line})
    if task.get("status") == "pending" and progress > 0:
        task["status"] = "running"
        if not task.get("started_at"):
            task["started_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        _set_index_entry(task_id, status=task["status"])
        return True
    except Exception as e:
        logger.warning("更新任务进度失败 %s: %s", task_id, e)
        return False


def append_task_log(task_id: str, log_line: str) -> bool:
    """仅追加一条日志。"""
    task = get_task(task_id)
    if not task:
        return False
    task.setdefault("logs", []).append({"ts": datetime.utcnow().isoformat(), "text": log_line})
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning("追加任务日志失败 %s: %s", task_id, e)
        return False


def complete_task(task_id: str, summary: Dict[str, Any], details_path: Optional[str] = None) -> bool:
    """标记任务完成并写入汇总与明细路径。"""
    task = get_task(task_id)
    if not task:
        return False
    task["status"] = "completed"
    task["progress"] = 100
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    task["summary"] = summary
    task["details_path"] = details_path
    task["error"] = None
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        _set_index_entry(task_id, status="completed")
        # 报告与任务一一对应，report_id = task_id
        report_path = os.path.join(_REPORTS_DIR, f"{task_id}.json")
        report = {
            "report_id": task_id,
            "task_id": task_id,
            "name": task.get("name"),
            "created_at": task.get("completed_at"),
            "summary": summary,
            "details_path": details_path,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning("完成任务写入失败 %s: %s", task_id, e)
        return False


def fail_task(task_id: str, error: str) -> bool:
    """标记任务失败。"""
    task = get_task(task_id)
    if not task:
        return False
    task["status"] = "failed"
    task["error"] = error
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        _set_index_entry(task_id, status="failed")
        return True
    except Exception as e:
        logger.warning("失败任务写入失败 %s: %s", task_id, e)
        return False


def cancel_task(task_id: str) -> bool:
    """标记任务已取消。"""
    task = get_task(task_id)
    if not task:
        return False
    if task.get("status") in ("completed", "failed"):
        return False
    task["status"] = "cancelled"
    task["completed_at"] = datetime.utcnow().isoformat() + "Z"
    path = os.path.join(_TASKS_DIR, f"{task_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        _set_index_entry(task_id, status="cancelled")
        return True
    except Exception as e:
        logger.warning("取消任务写入失败 %s: %s", task_id, e)
        return False


def delete_task(task_id: str) -> bool:
    """删除任务及对应报告与明细文件。"""
    for subdir, ext in ((_TASKS_DIR, ".json"), (_REPORTS_DIR, ".json"), (_DETAILS_DIR, ".csv")):
        p = os.path.join(subdir, f"{task_id}{ext}")
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception as e:
                logger.warning("删除文件 %s 失败: %s", p, e)
    with _INDEX_LOCK:
        index = _load_index()
        if task_id in index:
            del index[task_id]
            _save_index(index)
    return True


def list_tasks(status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """任务列表，按创建时间倒序。"""
    index = _load_index()
    items = []
    for tid, meta in index.items():
        if status and meta.get("status") != status:
            continue
        task = get_task(tid)
        if task:
            items.append(task)
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[offset : offset + limit]


def get_task_logs(task_id: str) -> List[Dict[str, Any]]:
    """返回任务日志列表。"""
    task = get_task(task_id)
    if not task:
        return []
    return task.get("logs") or []


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """报告列表（仅已完成任务对应的报告），按完成时间倒序。"""
    index = _load_index()
    report_ids = [tid for tid, meta in index.items() if meta.get("status") == "completed"]
    items = []
    for rid in report_ids:
        path = os.path.join(_REPORTS_DIR, f"{rid}.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                items.append(json.load(f))
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[offset : offset + limit]


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """报告详情。"""
    path = os.path.join(_REPORTS_DIR, f"{report_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("读取报告 %s 失败: %s", report_id, e)
        return None


def get_details_path(report_id: str) -> Optional[str]:
    """返回明细文件绝对路径（CSV），供下载。"""
    report = get_report(report_id)
    if not report:
        return None
    rel = report.get("details_path")
    if not rel:
        return None
    if os.path.isabs(rel):
        return rel if os.path.isfile(rel) else None
    return os.path.join(_DETAILS_DIR, os.path.basename(rel))


def save_details_csv(task_id: str, details: List[Dict[str, Any]]) -> str:
    """将明细写入 CSV，返回相对路径（文件名）。"""
    import csv
    _ensure_dirs()
    fname = f"{task_id}.csv"
    path = os.path.join(_DETAILS_DIR, fname)
    if not details:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("code,date,market,buy_type,score_total,entry_close,max_high_20d,max_gain_20d,hit\n")
        return fname
    keys = list(details[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(details)
    return fname
