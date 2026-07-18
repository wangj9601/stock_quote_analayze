"""SBBR 回测任务存储。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SBBRBacktestStorage:
    def _session(self):
        from backend_api.database import SessionLocal

        return SessionLocal()

    def create_task(self, config: Dict[str, Any], name: Optional[str] = None) -> str:
        from backend_api.models import SBBRBacktestTask

        task_id = str(uuid.uuid4())
        db = self._session()
        try:
            row = SBBRBacktestTask(
                task_id=task_id,
                name=name or config.get("task_name") or f"sbbr-{task_id[:8]}",
                config=config,
                status="pending",
                progress=0,
                message="queued",
                created_at=datetime.now(),
            )
            db.add(row)
            db.commit()
            return task_id
        finally:
            db.close()

    def update_task(self, task_id: str, **fields) -> None:
        from backend_api.models import SBBRBacktestTask

        db = self._session()
        try:
            row = db.query(SBBRBacktestTask).filter(SBBRBacktestTask.task_id == task_id).first()
            if not row:
                return
            for k, v in fields.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            row.updated_at = datetime.now()
            db.commit()
        finally:
            db.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        from backend_api.models import SBBRBacktestTask

        db = self._session()
        try:
            row = db.query(SBBRBacktestTask).filter(SBBRBacktestTask.task_id == task_id).first()
            if not row:
                return None
            return {
                "task_id": row.task_id,
                "name": row.name,
                "config": row.config or {},
                "status": row.status,
                "progress": row.progress,
                "message": row.message,
                "summary": row.summary,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
        finally:
            db.close()

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        from backend_api.models import SBBRBacktestTask

        db = self._session()
        try:
            rows = (
                db.query(SBBRBacktestTask)
                .order_by(SBBRBacktestTask.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "task_id": r.task_id,
                    "name": r.name,
                    "status": r.status,
                    "progress": r.progress,
                    "message": r.message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "backtest_type": (r.config or {}).get("backtest_type"),
                }
                for r in rows
            ]
        finally:
            db.close()
