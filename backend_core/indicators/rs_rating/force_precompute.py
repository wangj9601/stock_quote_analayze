"""RS Rating 全市场强制预计算任务（异步，内存态）。

语义：按交易日重算**全市场**截面排名，不是单票局部假评级。
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

MAX_FORCE_DAYS = 10

_lock = threading.Lock()
_tasks: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        t = _tasks.get(task_id)
        return dict(t) if t else None


def find_running(trade_date: Optional[str] = None) -> Optional[str]:
    with _lock:
        for tid, t in _tasks.items():
            if t.get("status") in ("pending", "running"):
                if trade_date and t.get("trade_date") and t.get("trade_date") != trade_date[:10]:
                    continue
                return tid
    return None


def create_task(trade_dates: List[str]) -> str:
    task_id = uuid.uuid4().hex
    with _lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "trade_dates": list(trade_dates),
            "trade_date": trade_dates[0] if len(trade_dates) == 1 else None,
            "progress": 0,
            "current": 0,
            "total": len(trade_dates),
            "message": "排队中…",
            "error": None,
            "summaries": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
    return task_id


def _update(task_id: str, **fields: Any) -> None:
    with _lock:
        t = _tasks.get(task_id)
        if not t:
            return
        t.update(fields)
        t["updated_at"] = _now()


def resolve_force_trade_dates(
    *,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_days: int = MAX_FORCE_DAYS,
    market: str = "CN",
) -> List[str]:
    """解析待强制重算的交易日列表（升序）。"""
    from backend_api.database import SessionLocal
    from backend_core.indicators.rs_rating.scheduled_precompute import (
        _normalize_date_str,
        resolve_trade_date,
    )
    from backend_core.indicators.rs_rating.scheduled_precompute_hk import (
        resolve_trade_date_hk,
    )

    mt = (market or "CN").strip().upper()
    quotes_table = "historical_quotes_hk" if mt == "HK" else "historical_quotes"
    td = (trade_date or "").strip()[:10] or None
    sd = (start_date or "").strip()[:10] or None
    ed = (end_date or "").strip()[:10] or None
    cap = max(1, min(int(max_days or MAX_FORCE_DAYS), MAX_FORCE_DAYS))

    db = SessionLocal()
    try:
        if sd or ed:
            if not sd or not ed:
                raise ValueError("区间强制计算需同时提供 start_date 与 end_date")
            if sd > ed:
                raise ValueError("start_date 不能晚于 end_date")
            rows = db.execute(
                text(
                    f"""
                    SELECT DISTINCT date::text AS d
                    FROM {quotes_table}
                    WHERE date >= :sd AND date <= :ed
                    ORDER BY d ASC
                    """
                ),
                {"sd": sd, "ed": ed},
            ).fetchall()
            dates = [_normalize_date_str(r[0]) for r in rows if r and r[0]]
            if not dates:
                raise ValueError(f"区间 {sd}~{ed} 在 {quotes_table} 中无交易日")
            if len(dates) > cap:
                raise ValueError(
                    f"区间内共 {len(dates)} 个交易日，强制重算上限为 {cap} 天；请缩小区间"
                )
            return dates

        if mt == "HK":
            date_s = resolve_trade_date_hk(db, td)
        else:
            date_s = resolve_trade_date(db, td)
        return [date_s]
    finally:
        db.close()


def _run(task_id: str, trade_dates: List[str], market: str = "CN") -> None:
    from backend_core.indicators.rs_rating.scheduled_precompute import run_rs_rating_precompute
    from backend_core.indicators.rs_rating.scheduled_precompute_hk import (
        run_rs_rating_precompute_hk,
    )

    mt = (market or "CN").strip().upper()
    runner = run_rs_rating_precompute_hk if mt == "HK" else run_rs_rating_precompute
    label = "港股" if mt == "HK" else "A股"

    try:
        _update(
            task_id,
            status="running",
            market=mt,
            message=f"开始{label}全市场前复权截面预计算…",
            progress=0,
        )
        summaries: List[Dict[str, Any]] = []
        total = len(trade_dates)
        for i, d in enumerate(trade_dates):
            _update(
                task_id,
                current=i,
                progress=int(round(i * 100 / total)) if total else 0,
                message=f"正在计算 {d}（{label}全市场）…",
                trade_date=d,
            )
            summary = runner(trade_date=d)
            summaries.append(summary)
            if not summary.get("ok"):
                raise RuntimeError(summary.get("error") or f"{d} 预计算失败")
        _update(
            task_id,
            status="completed",
            progress=100,
            current=total,
            total=total,
            summaries=summaries,
            message=f"已完成 {total} 个交易日{label}全市场预计算",
            trade_date=trade_dates[-1] if trade_dates else None,
        )
        logger.info(
            "RS force precompute done task_id=%s market=%s days=%s",
            task_id,
            mt,
            trade_dates,
        )
    except Exception as e:
        logger.exception("RS force precompute failed task_id=%s market=%s", task_id, mt)
        _update(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )


def start_precompute(trade_dates: List[str], *, market: str = "CN") -> str:
    dates = [str(d).strip()[:10] for d in trade_dates if str(d).strip()]
    if not dates:
        raise ValueError("请至少指定一个交易日")
    mt = (market or "CN").strip().upper()
    if mt not in ("CN", "HK"):
        raise ValueError("market 仅支持 CN 或 HK")
    seen = set()
    uniq: List[str] = []
    for d in dates:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    if len(uniq) > MAX_FORCE_DAYS:
        raise ValueError(f"单次最多强制重算 {MAX_FORCE_DAYS} 个交易日")
    running = find_running()
    if running:
        raise RuntimeError(f"已有预计算任务进行中: {running}")
    task_id = create_task(uniq)
    with _lock:
        t = _tasks.get(task_id)
        if t is not None:
            t["market"] = mt
    th = threading.Thread(target=_run, args=(task_id, uniq, mt), daemon=True)
    th.start()
    return task_id
