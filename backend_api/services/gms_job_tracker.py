"""GMS 任务运行记录、选股指标统计与预计算运行记录。"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SCREENING_STATS: Dict[str, Any] = {
    "request_count": 0,
    "timeout_count": 0,
    "trace_hit_rates": [],
    "last_reset": datetime.now().isoformat(),
}


def record_job_run(
    db: Session,
    job_type: str,
    status: str,
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO gms_job_runs (job_type, status, config_id, trade_date, message, meta_json)
                VALUES (:job_type, :status, :config_id, :trade_date, :message, CAST(:meta AS JSONB))
                """
            ),
            {
                "job_type": job_type,
                "status": status,
                "config_id": config_id,
                "trade_date": trade_date,
                "message": message,
                "meta": json.dumps(meta or {}, ensure_ascii=False),
            },
        )
        db.commit()
    except Exception as e:
        logger.warning("记录 gms_job_runs 失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


def record_precompute_run(
    db: Session,
    config_id: int,
    market: str,
    trade_date: str,
    status: str,
    stock_count: int = 0,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO gms_precompute_runs
                (config_id, market, trade_date, status, stock_count, duration_ms, error_message, finished_at)
                VALUES (:config_id, :market, :trade_date, :status, :stock_count, :duration_ms, :error, NOW())
                """
            ),
            {
                "config_id": config_id,
                "market": market,
                "trade_date": trade_date,
                "status": status,
                "stock_count": stock_count,
                "duration_ms": duration_ms,
                "error": error_message,
            },
        )
        db.commit()
    except Exception as e:
        logger.warning("记录 gms_precompute_runs 失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


def note_screening_request(trace_meta: Optional[Dict[str, Any]] = None, timed_out: bool = False) -> None:
    _SCREENING_STATS["request_count"] = int(_SCREENING_STATS.get("request_count") or 0) + 1
    if timed_out:
        _SCREENING_STATS["timeout_count"] = int(_SCREENING_STATS.get("timeout_count") or 0) + 1
    if trace_meta:
        req = int(trace_meta.get("requested_count") or 0)
        hit = int(trace_meta.get("from_trace_count") or 0)
        if req > 0:
            rates = _SCREENING_STATS.setdefault("trace_hit_rates", [])
            rates.append(hit / req)
            if len(rates) > 200:
                _SCREENING_STATS["trace_hit_rates"] = rates[-200:]


def screening_stats_summary() -> Dict[str, Any]:
    rates = _SCREENING_STATS.get("trace_hit_rates") or []
    avg_rate = sum(rates) / len(rates) if rates else None
    return {
        "request_count": int(_SCREENING_STATS.get("request_count") or 0),
        "timeout_count": int(_SCREENING_STATS.get("timeout_count") or 0),
        "avg_trace_hit_rate": round(avg_rate, 4) if avg_rate is not None else None,
        "since": _SCREENING_STATS.get("last_reset"),
    }


def get_latest_precompute_runs(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                SELECT config_id, market, trade_date, status, stock_count, duration_ms,
                       error_message, started_at, finished_at
                FROM gms_precompute_runs
                ORDER BY started_at DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("查询 gms_precompute_runs 失败: %s", e)
        return []


def get_recent_job_runs(db: Session, job_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        if job_type:
            rows = db.execute(
                text(
                    """
                    SELECT job_type, status, config_id, trade_date, message, meta_json, created_at
                    FROM gms_job_runs WHERE job_type = :jt
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"jt": job_type, "lim": limit},
            ).mappings().all()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT job_type, status, config_id, trade_date, message, meta_json, created_at
                    FROM gms_job_runs ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"lim": limit},
            ).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out
    except Exception as e:
        logger.warning("查询 gms_job_runs 失败: %s", e)
        return []


def check_precompute_alert(db: Session) -> Optional[str]:
    """连续两日 CN 预计算未成功时返回告警文案。"""
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT trade_date, status
                FROM gms_precompute_runs
                WHERE market = 'cn' AND trade_date >= :since
                ORDER BY trade_date DESC
                """
            ),
            {"since": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")},
        ).mappings().all()
        if not rows:
            return "近 3 日无 A 股 GMS 预计算记录，请检查定时任务"
        failed_dates = [r["trade_date"] for r in rows if r.get("status") != "success"]
        if len(failed_dates) >= 2:
            return f"GMS A 股预计算连续异常：{', '.join(failed_dates[:3])}"
    except Exception:
        pass
    return None


def maybe_send_gms_alert(db: Session, alert_message: str) -> None:
    if not alert_message:
        return
    if os.getenv("GMS_ALERT_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logger.warning("GMS 告警（未启用邮件）: %s", alert_message)
        return
    logger.warning("GMS 告警: %s", alert_message)
