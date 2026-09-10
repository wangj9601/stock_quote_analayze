# -*- coding: utf-8 -*-
"""CSB 回测任务持久化（csb_backtest_tasks）。"""

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
from backend_api.models import CSBBacktestTask

logger = logging.getLogger(__name__)

_CSB_DETAIL_FIELDS: List[str] = [
    "code", "name", "signal_date", "signal_type", "score",
    "entry_date", "entry_price", "max_high", "max_gain_pct",
    "hit_target", "hit_date", "exit_date", "exit_price", "exit_reason",
    "pnl_pct", "bars_held", "horizon_days",
    "squeeze_days", "squeeze_pct", "touch_count", "vol_expand_mult",
    "channel_upper", "channel_lower", "entry_low",
    "f_squeeze_days", "f_squeeze_pct", "f_touch_count", "f_vol_expand",
    "horizon_pnl_pct", "horizon_exit_price",
]

_CSB_DETAIL_HEADER_ZH: Dict[str, str] = {
    "code": "股票代码",
    "name": "股票名称",
    "signal_date": "信号日期",
    "signal_type": "信号类型",
    "score": "得分",
    "entry_date": "入场日期",
    "entry_price": "入场价",
    "max_high": "观察期最高价",
    "max_gain_pct": "观察期最大涨幅(%)",
    "hit_target": "是否命中目标",
    "hit_date": "命中日期",
    "exit_date": "出场日期",
    "exit_price": "出场价",
    "exit_reason": "出场原因",
    "pnl_pct": "盈亏比例(%)",
    "bars_held": "持有天数",
    "horizon_days": "观察期天数",
    "squeeze_days": "粘合天数",
    "squeeze_pct": "粘合带宽",
    "touch_count": "回踩次数",
    "vol_expand_mult": "放量倍数",
    "channel_upper": "通道上轨",
    "channel_lower": "通道下轨",
    "entry_low": "基准低点",
    "f_squeeze_days": "粘合天数分",
    "f_squeeze_pct": "粘合带宽分",
    "f_touch_count": "回踩分",
    "f_vol_expand": "放量分",
    "horizon_pnl_pct": "满观察期盈亏(%)",
    "horizon_exit_price": "满观察期收盘",
}

_CSB_EXIT_REASON_ZH: Dict[str, str] = {
    "horizon_end": "到期平仓",
    "false_break": "假突破",
    "baseline_stop": "基准止损",
    "ma_trail": "MA跟踪止损",
    "price_stop": "价格止损",
}

_EXCEL_TEXT_PREFIX = "\u2060"


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


def _row_to_dict(row: CSBBacktestTask) -> Dict[str, Any]:
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
        CSBBacktestTask.__table__.create(bind=db.get_bind(), checkfirst=True)
    finally:
        if owns:
            db.close()


def create_task(config: Dict[str, Any], name: Optional[str] = None) -> str:
    ensure_table()
    task_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db = _session()
    try:
        t = CSBBacktestTask(
            task_id=task_id,
            name=name or config.get("task_name") or f"CSB回测_{task_id[:8]}",
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
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
        return _row_to_dict(row) if row else None
    finally:
        db.close()


def list_tasks(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _session()
    try:
        q = db.query(CSBBacktestTask).order_by(desc(CSBBacktestTask.created_at))
        if status:
            q = q.filter(CSBBacktestTask.status == status)
        return [_row_to_dict(r) for r in q.limit(int(limit)).all()]
    finally:
        db.close()


def update_task_progress(task_id: str, progress: int, message: str = "", log_line: Optional[str] = None) -> None:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
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


def _format_cell(key: str, value: Any) -> Any:
    if key == "hit_target":
        if value is True:
            return "是"
        if value is False:
            return "否"
    if key == "exit_reason":
        return _CSB_EXIT_REASON_ZH.get(str(value or ""), value)
    if key == "code" and value is not None:
        s = str(value).replace(_EXCEL_TEXT_PREFIX, "").strip()
        if s.isdigit() and len(s) != 5 and len(s) <= 6:
            s = s.zfill(6)
        return _EXCEL_TEXT_PREFIX + s
    return value


def _build_csv_bytes(details_rows: List[Dict[str, Any]]) -> bytes:
    fields = list(_CSB_DETAIL_FIELDS)
    if details_rows:
        for k in details_rows[0]:
            if k not in fields:
                fields.append(k)
    headers = [_CSB_DETAIL_HEADER_ZH.get(k, k) for k in fields]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    for r in details_rows:
        w.writerow({_CSB_DETAIL_HEADER_ZH.get(k, k): _format_cell(k, r.get(k)) for k in fields})
    return buf.getvalue().encode("utf-8-sig")


def complete_task(task_id: str, summary: Dict[str, Any], details_rows: Optional[List[Dict[str, Any]]] = None) -> None:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
        if not row:
            return
        row.status = "completed"
        row.progress = 100
        row.message = "完成"
        row.summary = summary
        row.completed_at = datetime.utcnow()
        row.error = None
        if details_rows:
            row.details_csv_bytes = _build_csv_bytes(details_rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def patch_task_config(task_id: str, extra: Dict[str, Any]) -> None:
    tid = normalize_task_id(task_id)
    if not tid or not extra:
        return
    db = _session()
    try:
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
        if not row:
            return
        cfg = dict(row.config) if isinstance(row.config, dict) else {}
        cfg.update(extra)
        row.config = cfg
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def patch_task_summary(task_id: str, extra: Dict[str, Any]) -> None:
    tid = normalize_task_id(task_id)
    if not tid or not extra:
        return
    db = _session()
    try:
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
        if not row:
            return
        summary = dict(row.summary) if isinstance(row.summary, dict) else {}
        summary.update(extra)
        row.summary = summary
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
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
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
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
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
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
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
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
        return bytes(row.details_csv_bytes) if row and row.details_csv_bytes else None
    finally:
        db.close()


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    db = _session()
    try:
        rows = (
            db.query(CSBBacktestTask)
            .filter(CSBBacktestTask.status == "completed")
            .order_by(desc(CSBBacktestTask.completed_at))
            .offset(int(offset))
            .limit(int(limit))
            .all()
        )
        return [
            {
                "report_id": r.task_id,
                "task_id": r.task_id,
                "name": r.name,
                "created_at": _dt_iso(r.completed_at or r.created_at),
                "summary": r.summary,
                "has_details_csv": bool(r.details_csv_bytes),
                "config": r.config,
            }
            for r in rows
        ]
    finally:
        db.close()


def reset_task_for_rerun(task_id: str) -> bool:
    tid = normalize_task_id(task_id)
    db = _session()
    try:
        row = db.query(CSBBacktestTask).filter(CSBBacktestTask.task_id == tid).first()
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


def _csv_bytes_to_xlsx(raw: bytes) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return b""
    wb = Workbook()
    ws = wb.active
    ws.title = "CSB回测明细"
    headers = rows[0]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    code_col = None
    for i, h in enumerate(headers, start=1):
        if h == "股票代码":
            code_col = i
            break
    for row in rows[1:]:
        if code_col and len(row) >= code_col:
            idx = code_col - 1
            row = list(row)
            s = str(row[idx] or "").replace(_EXCEL_TEXT_PREFIX, "").strip()
            if s.isdigit() and len(s) != 5 and len(s) <= 6:
                s = s.zfill(6)
            row[idx] = _EXCEL_TEXT_PREFIX + s
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def get_details_xlsx(task_id: str) -> Optional[bytes]:
    raw = get_details_csv(task_id)
    if not raw:
        return None
    return _csv_bytes_to_xlsx(raw)


def count_completed_reports() -> int:
    db = _session()
    try:
        return db.query(CSBBacktestTask).filter(CSBBacktestTask.status == "completed").count()
    finally:
        db.close()


def count_running_tasks() -> int:
    db = _session()
    try:
        return (
            db.query(CSBBacktestTask)
            .filter(CSBBacktestTask.status.in_(("pending", "running")))
            .count()
        )
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
    out: List[Dict[str, Any]] = []
    for item in logs:
        if isinstance(item, dict):
            text = item.get("message") or item.get("text") or str(item)
            out.append({"text": text, "ts": item.get("ts")})
        else:
            out.append({"text": str(item)})
    return out


def batch_delete_tasks(task_ids: List[str]) -> int:
    n = 0
    for tid in task_ids or []:
        if delete_task(tid):
            n += 1
    return n
