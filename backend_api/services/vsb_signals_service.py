"""
3倍量缩量突破 — 信号历史查询逻辑（供 /api/stock 与 /api/screening 复用）
"""

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from backend_api.models import VolumeShrinkBreakoutSignal

_VSB_TABLE_NAME = "volume_shrink_breakout_signals"
_TABLE_MISSING_HINT = (
    f"数据库表 {_VSB_TABLE_NAME} 尚未创建。请在项目根目录执行："
    f"python backend_api/create_volume_shrink_breakout_signal_table.py"
    "（PostgreSQL 需有建表权限）；若表已改名请同步 ORM。"
)


def _is_vsb_table_missing_error(exc: BaseException) -> bool:
    """UndefinedTable / 42P01 等：关系 volume_shrink_breakout_signals 不存在。"""
    cur = exc
    for _ in range(5):
        if cur is None:
            break
        msg = str(cur).lower()
        if _VSB_TABLE_NAME in msg and (
            "does not exist" in msg
            or "undefinedtable" in msg.replace(" ", "")
            or "不存在" in str(cur)
            or "42p01" in msg
        ):
            return True
        cur = getattr(cur, "__cause__", None) or getattr(cur, "orig", None)
    return False


def _reminders_from_row(r: VolumeShrinkBreakoutSignal) -> List[str]:
    raw = getattr(r, "signal_reminders_json", None)
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        out = json.loads(str(raw))
        return out if isinstance(out, list) else []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _phase_state_from_row(r: VolumeShrinkBreakoutSignal) -> Optional[Dict[str, Any]]:
    raw = getattr(r, "phase_state_json", None)
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(str(raw))
        return out if isinstance(out, dict) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def signal_to_dict(r: VolumeShrinkBreakoutSignal) -> Dict[str, Any]:
    phase_state = _phase_state_from_row(r)
    return {
        "code": r.code,
        "name": r.name,
        "signal_date": r.signal_date.isoformat() if r.signal_date else None,
        "boom_date": r.boom_date,
        "boom_close": r.boom_close,
        "boom_volume": r.boom_volume,
        "boom_volume_ratio_vs_prev": r.boom_volume_ratio_vs_prev,
        "ma5_at_boom": r.ma5_at_boom,
        "ma10_at_boom": r.ma10_at_boom,
        "ma20_at_boom": r.ma20_at_boom,
        "breakout_close": r.breakout_close,
        "breakout_volume": r.breakout_volume,
        "current_change_percent": r.current_change_percent,
        "volume_ratio_param": r.volume_ratio_param,
        "boom_lookback_min": r.boom_lookback_min,
        "boom_lookback_max": r.boom_lookback_max,
        "boards_json": r.boards_json,
        "run_search_date": r.run_search_date,
        "signal_strength": getattr(r, "signal_strength", None),
        "signal_strength_level": getattr(r, "signal_strength_level", None),
        "buy_signal": getattr(r, "buy_signal_text", None),
        "signal_reminders": _reminders_from_row(r),
        "signal_reminders_json": getattr(r, "signal_reminders_json", None),
        "strategy_phase": (phase_state or {}).get("strategy_phase") if phase_state else None,
        "phase_state": phase_state,
        "phase_state_json": getattr(r, "phase_state_json", None),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def normalize_vsb_code(code: str) -> str:
    s = str(code).strip()
    if len(s) == 5 and s.isdigit():
        s = s.zfill(6)
    return s


def parse_yyyy_mm_dd(s: Optional[str], field_name: str) -> Optional[date]:
    if not s:
        return None
    raw = str(s).strip()[:10]
    if len(raw) < 10:
        raise ValueError(f"{field_name} 须为 YYYY-MM-DD")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"{field_name} 格式错误") from e


def query_vsb_signals_by_code(
    db: Session,
    *,
    code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    返回 (payload_dict, error_key)。
    error_key: 'model_unavailable' | 'bad_code' | 'table_missing' | None
    """
    if VolumeShrinkBreakoutSignal is None:
        return {}, "model_unavailable"
    code_n = normalize_vsb_code(code)
    if not code_n:
        return {}, "bad_code"

    d0 = parse_yyyy_mm_dd(start_date, "start_date") if start_date else None
    d1 = parse_yyyy_mm_dd(end_date, "end_date") if end_date else None

    q = db.query(VolumeShrinkBreakoutSignal).filter(VolumeShrinkBreakoutSignal.code == code_n)
    if d0 is not None:
        q = q.filter(VolumeShrinkBreakoutSignal.signal_date >= d0)
    if d1 is not None:
        q = q.filter(VolumeShrinkBreakoutSignal.signal_date <= d1)
    try:
        rows = q.order_by(VolumeShrinkBreakoutSignal.signal_date.desc()).limit(limit).all()
    except ProgrammingError as e:
        if _is_vsb_table_missing_error(e):
            return (
                {
                    "success": False,
                    "message": _TABLE_MISSING_HINT,
                    "data": [],
                    "total": 0,
                    "code": code_n,
                },
                "table_missing",
            )
        raise
    data = [signal_to_dict(r) for r in rows]
    return (
        {
            "success": True,
            "data": data,
            "total": len(data),
            "code": code_n,
        },
        None,
    )


def query_vsb_signals_by_signal_date(
    db: Session,
    *,
    signal_date: str,
    limit: int,
) -> Tuple[Dict[str, Any], Optional[str]]:
    if VolumeShrinkBreakoutSignal is None:
        return {}, "model_unavailable"
    sd = parse_yyyy_mm_dd(signal_date, "signal_date")

    try:
        rows = (
            db.query(VolumeShrinkBreakoutSignal)
            .filter(VolumeShrinkBreakoutSignal.signal_date == sd)
            .order_by(VolumeShrinkBreakoutSignal.code.asc())
            .limit(limit)
            .all()
        )
    except ProgrammingError as e:
        if _is_vsb_table_missing_error(e):
            return (
                {
                    "success": False,
                    "message": _TABLE_MISSING_HINT,
                    "data": [],
                    "total": 0,
                    "signal_date": sd.isoformat(),
                },
                "table_missing",
            )
        raise
    data = [signal_to_dict(r) for r in rows]
    return (
        {
            "success": True,
            "data": data,
            "total": len(data),
            "signal_date": sd.isoformat(),
        },
        None,
    )
