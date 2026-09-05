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
            summary = dict(row.summary or {})
            stock_lists = self._derive_stock_lists(summary)
            summary.setdefault("entry_stocks", stock_lists["entry_stocks"])
            summary.setdefault("hit_stocks", stock_lists["hit_stocks"])
            return {
                "task_id": row.task_id,
                "name": row.name,
                "config": row.config or {},
                "status": row.status,
                "progress": row.progress,
                "message": row.message,
                "summary": summary,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
        finally:
            db.close()

    @staticmethod
    def _derive_stock_lists(summary: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """从 summary / details_preview 推导入场与命中列表（兼容旧任务）。"""
        s = summary or {}
        if s.get("entry_stocks") is not None:
            entry_stocks = list(s.get("entry_stocks") or [])
            if s.get("hit_stocks") is not None:
                hit_stocks = list(s.get("hit_stocks") or [])
            else:
                hit_stocks = [e for e in entry_stocks if e.get("ok")]
            return {
                "entry_stocks": entry_stocks[:100],
                "hit_stocks": hit_stocks[:100],
            }

        entry_stocks: List[Dict[str, Any]] = []
        for d in list(s.get("details_preview") or []):
            code = d.get("code")
            if not code:
                continue
            date = d.get("date") or d.get("signal_date")
            ok = d.get("ok")
            if ok is None:
                if "return" in d:
                    ok = float(d.get("return") or 0) > 0
                else:
                    ok = bool(d.get("hit_target")) and not bool(d.get("defense_breached"))
            entry_stocks.append(
                {
                    "code": code,
                    "name": d.get("name"),
                    "date": date,
                    "ok": bool(ok),
                }
            )
        hit_stocks = [e for e in entry_stocks if e.get("ok")]
        return {
            "entry_stocks": entry_stocks[:100],
            "hit_stocks": hit_stocks[:100],
        }

    @staticmethod
    def _format_stock_labels(rows: List[Dict[str, Any]], limit: int = 8) -> str:
        labels: List[str] = []
        for r in rows[:limit]:
            code = str(r.get("code") or "")
            name = str(r.get("name") or "").strip()
            date = str(r.get("date") or "")[:10]
            base = f"{code}{(' ' + name) if name else ''}".strip()
            labels.append(f"{base}@{date}" if date else base)
        extra = len(rows) - limit
        text = "、".join(labels)
        if extra > 0:
            text = f"{text} 等{len(rows)}只" if text else f"{len(rows)}只"
        return text

    @staticmethod
    def _summary_list_fields(summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """列表用精简 summary；兼容旧任务仅有 total_samples。"""
        s = summary or {}
        entry_count = s.get("entry_count")
        if entry_count is None:
            entry_count = s.get("total_samples")
        stock_lists = SBBRBacktestStorage._derive_stock_lists(s)
        entry_stocks = stock_lists["entry_stocks"]
        hit_stocks = stock_lists["hit_stocks"]
        out: Dict[str, Any] = {
            "entry_count": entry_count,
            "hit_count": s.get("hit_count"),
            "hit_rate": s.get("hit_rate"),
            "total_samples": s.get("total_samples"),
            "total_trades": s.get("total_trades"),
            "win_rate": s.get("win_rate"),
            "total_return": s.get("total_return"),
            "max_drawdown": s.get("max_drawdown"),
            "entry_stocks": entry_stocks,
            "hit_stocks": hit_stocks,
            "entry_stock_labels": SBBRBacktestStorage._format_stock_labels(entry_stocks),
            "hit_stock_labels": SBBRBacktestStorage._format_stock_labels(hit_stocks),
        }
        return out

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
            items = []
            for r in rows:
                cfg = r.config or {}
                scope_meta = cfg.get("scope_meta") or {}
                if not scope_meta and (r.summary or {}).get("scope_meta"):
                    scope_meta = (r.summary or {}).get("scope_meta") or {}
                mode = (
                    scope_meta.get("stock_pool_mode")
                    or cfg.get("stock_pool_mode")
                    or ((r.summary or {}).get("stock_pool_mode") if r.summary else None)
                )
                items.append(
                    {
                        "task_id": r.task_id,
                        "name": r.name,
                        "status": r.status,
                        "progress": r.progress,
                        "message": r.message,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                        "backtest_type": cfg.get("backtest_type"),
                        "stock_pool_mode": mode,
                        "scope_meta": scope_meta or None,
                        "summary": self._summary_list_fields(r.summary),
                    }
                )
            return items
        finally:
            db.close()
