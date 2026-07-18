# -*- coding: utf-8 -*-
"""URT 回测任务持久化（urt_backtest_tasks）。"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend_api.database import SessionLocal
from backend_api.models import URTBacktestTask

logger = logging.getLogger(__name__)


def _session() -> Session:
    return SessionLocal()


def normalize_task_id(task_id: Optional[str]) -> str:
    return str(task_id or "").strip()


def clamp_progress(progress: Any) -> int:
    try:
        v = int(round(float(progress)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, v))


def _dt_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def _row_to_dict(row: URTBacktestTask) -> Dict[str, Any]:
    return {
        "task_id": row.task_id,
        "name": row.name,
        "config": row.config if isinstance(row.config, dict) else {},
        "status": row.status,
        "progress": clamp_progress(row.progress),
        "message": row.message or "",
        "logs": row.logs if isinstance(row.logs, list) else [],
        "created_at": _dt_iso(row.created_at),
        "started_at": _dt_iso(row.started_at),
        "completed_at": _dt_iso(row.completed_at),
        "summary": row.summary,
        "details_path": row.details_path,
        "error": row.error,
        "has_details_csv": bool(row.details_csv_bytes),
    }


def ensure_table(db: Optional[Session] = None) -> None:
    owns = db is None
    if owns:
        db = _session()
    try:
        URTBacktestTask.__table__.create(bind=db.get_bind(), checkfirst=True)
    finally:
        if owns:
            db.close()


def create_task(config: Dict[str, Any], name: Optional[str] = None) -> str:
    ensure_table()
    task_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db = _session()
    try:
        t = URTBacktestTask(
            task_id=task_id,
            name=name or config.get("task_name") or f"URT回测_{task_id[:8]}",
            config=config,
            status="pending",
            progress=0,
            message="",
            logs=[],
            summary=None,
            error=None,
            details_path=None,
            details_csv_bytes=None,
            created_at=now,
            started_at=None,
            completed_at=None,
        )
        db.add(t)
        db.commit()
        return task_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    tid = normalize_task_id(task_id)
    if not tid:
        return None
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        return _row_to_dict(row) if row else None
    finally:
        db.close()


def list_tasks(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _session()
    try:
        q = db.query(URTBacktestTask).order_by(desc(URTBacktestTask.created_at))
        if status:
            q = q.filter(URTBacktestTask.status == status)
        return [_row_to_dict(r) for r in q.limit(int(limit)).all()]
    finally:
        db.close()


def update_task_progress(task_id: str, progress: int, message: str = "", log_line: Optional[str] = None) -> None:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row:
            return
        if row.status == "pending":
            row.status = "running"
            row.started_at = datetime.utcnow()
        row.progress = clamp_progress(progress)
        row.message = message or row.message
        if log_line:
            logs = list(row.logs or [])
            logs.append({"ts": datetime.utcnow().isoformat() + "Z", "message": log_line})
            row.logs = logs[-200:]
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def complete_task(
    task_id: str,
    summary: Dict[str, Any],
    details_rows: Optional[List[Dict[str, Any]]] = None,
) -> None:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row:
            return
        row.status = "completed"
        row.progress = 100
        row.message = "完成"
        row.summary = summary
        row.completed_at = datetime.utcnow()
        row.error = None
        if details_rows:
            buf = io.StringIO()
            fields = list(details_rows[0].keys())
            w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in details_rows:
                w.writerow(r)
            row.details_csv_bytes = buf.getvalue().encode("utf-8-sig")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fail_task(task_id: str, error: str) -> None:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row:
            return
        row.status = "failed"
        row.error = error
        row.message = error
        row.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel_task(task_id: str) -> bool:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row or row.status in ("completed", "failed", "cancelled"):
            return False
        row.status = "cancelled"
        row.message = "已取消"
        row.completed_at = datetime.utcnow()
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_task(task_id: str) -> bool:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_details_csv(task_id: str) -> Optional[bytes]:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        return bytes(row.details_csv_bytes) if row and row.details_csv_bytes else None
    finally:
        db.close()


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """已完成任务投影为报告列表。"""
    db = _session()
    try:
        rows = (
            db.query(URTBacktestTask)
            .filter(URTBacktestTask.status == "completed")
            .order_by(desc(URTBacktestTask.completed_at), desc(URTBacktestTask.created_at))
            .offset(int(offset))
            .limit(int(limit))
            .all()
        )
        out = []
        for r in rows:
            d = _row_to_dict(r)
            out.append(
                {
                    "report_id": d["task_id"],
                    "task_id": d["task_id"],
                    "name": d["name"],
                    "created_at": d.get("completed_at") or d.get("created_at"),
                    "summary": d.get("summary"),
                    "details_path": d.get("details_path"),
                    "has_details_csv": d.get("has_details_csv"),
                    "config": d.get("config"),
                }
            )
        return out
    finally:
        db.close()


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    row = get_task(report_id)
    if not row or row.get("status") != "completed":
        return None
    return {
        "report_id": row["task_id"],
        "task_id": row["task_id"],
        "name": row["name"],
        "created_at": row.get("completed_at") or row.get("created_at"),
        "summary": row.get("summary"),
        "details_path": row.get("details_path"),
        "has_details_csv": row.get("has_details_csv"),
        "config": row.get("config"),
    }


def get_task_logs(task_id: str) -> List[Dict[str, Any]]:
    row = get_task(task_id)
    if not row:
        return []
    logs = row.get("logs") or []
    # 统一为 {text, ts} 便于前端
    out = []
    for item in logs:
        if isinstance(item, dict):
            text = item.get("message") or item.get("text") or str(item)
            out.append({"text": text, "ts": item.get("ts")})
        else:
            out.append({"text": str(item)})
    return out


def reset_task_for_rerun(task_id: str) -> bool:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(URTBacktestTask).filter(URTBacktestTask.task_id == tid).first()
        if not row:
            return False
        row.status = "pending"
        row.progress = 0
        row.message = "重新排队"
        row.error = None
        row.summary = None
        row.details_csv_bytes = None
        row.started_at = None
        row.completed_at = None
        logs = list(row.logs or [])
        logs.append({"ts": datetime.utcnow().isoformat() + "Z", "message": "任务重新执行"})
        row.logs = logs[-200:]
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def batch_delete_tasks(task_ids: List[str]) -> int:
    n = 0
    for tid in task_ids or []:
        if delete_task(tid):
            n += 1
    return n
