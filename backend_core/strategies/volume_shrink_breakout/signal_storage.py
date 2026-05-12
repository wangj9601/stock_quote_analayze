"""
3倍量缩量突破 — 选股命中写入 volume_shrink_breakout_signals
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _is_vsb_observe_table_missing(exc: BaseException) -> bool:
    """PostgreSQL 42P01 undefined_table 或文案中含表名且「不存在」。"""
    if isinstance(exc, ProgrammingError):
        orig = getattr(exc, "orig", None)
        if getattr(orig, "pgcode", None) == "42P01":
            return "vsb_observe_stocks" in str(exc)
    msg = str(exc).lower()
    return "vsb_observe_stocks" in msg and ("does not exist" in msg or "不存在" in str(exc))


def parse_vsb_signal_date(breakout_date: Any) -> Optional[date]:
    """从 breakout_date（YYYY-MM-DD 或 date）解析 signal_date。"""
    if breakout_date is None:
        return None
    if isinstance(breakout_date, datetime):
        return breakout_date.date()
    if isinstance(breakout_date, date):
        return breakout_date
    s = str(breakout_date).strip()[:10]
    if len(s) < 10:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def screen_row_to_signal_fields(
    row: Dict[str, Any],
    *,
    parameters: Dict[str, Any],
    search_date: str,
) -> Optional[Dict[str, Any]]:
    """
    将 screen_universe 单条 dict 转为 ORM 可赋值的字段包；无法解析 signal_date 时返回 None。
    """
    code = str(row.get("code") or "").strip()
    if len(code) == 5 and code.isdigit():
        code = code.zfill(6)
    if not code:
        return None
    sd = parse_vsb_signal_date(row.get("breakout_date"))
    if sd is None:
        return None
    boards = parameters.get("boards")
    if boards is not None and not isinstance(boards, (list, tuple)):
        boards = None
    boards_json = json.dumps(list(boards) if boards else [], ensure_ascii=False)
    reminders = row.get("signal_reminders")
    if isinstance(reminders, (list, tuple)):
        reminders_json = json.dumps(list(reminders), ensure_ascii=False)
    else:
        reminders_json = None
    phase_state = row.get("phase_state")
    if isinstance(phase_state, dict):
        phase_state_json = json.dumps(phase_state, ensure_ascii=False)
    else:
        raw_ps = row.get("phase_state_json")
        phase_state_json = str(raw_ps) if raw_ps else None

    return {
        "code": code,
        "name": str(row.get("name") or "")[:100],
        "signal_date": sd,
        "boom_date": (str(row.get("boom_date") or "")[:20] or None),
        "boom_close": _f(row.get("boom_close")),
        "boom_volume": _f(row.get("boom_volume")),
        "boom_volume_ratio_vs_prev": _f(row.get("boom_volume_ratio_vs_prev")),
        "ma5_at_boom": _f(row.get("ma5_at_boom")),
        "ma10_at_boom": _f(row.get("ma10_at_boom")),
        "ma20_at_boom": _f(row.get("ma20_at_boom")),
        "breakout_close": _f(row.get("breakout_close")),
        "breakout_volume": _f(row.get("breakout_volume")),
        "current_change_percent": _f(row.get("current_change_percent")),
        "volume_ratio_param": _f(parameters.get("volume_ratio")),
        "boom_lookback_min": _i(parameters.get("boom_lookback_min")),
        "boom_lookback_max": _i(parameters.get("boom_lookback_max")),
        "boards_json": boards_json,
        "run_search_date": (str(search_date)[:20] if search_date else None),
        "signal_strength": _i(row.get("signal_strength")),
        "signal_strength_level": (str(row.get("signal_strength_level") or "")[:10] or None),
        "buy_signal_text": (str(row.get("buy_signal") or "")[:220] or None),
        "signal_reminders_json": reminders_json,
        "phase_state_json": phase_state_json,
    }


def _vsb_screening_observe_enabled() -> bool:
    """为 false 时仅写 volume_shrink_breakout_signals，不写 vsb_observe_stocks。"""
    raw = (os.getenv("VSB_SCREENING_OBSERVE_ENABLED") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on", "y")


def _save_vsb_observe_from_screen_rows(
    db: Session,
    rows: List[Dict[str, Any]],
    *,
    parameters: Dict[str, Any],
    search_date: str,
) -> int:
    """将选股命中同步写入 vsb_observe_stocks；(market, code, signal_date) 幂等更新。"""
    if not rows:
        return 0
    try:
        from backend_api.models import VsbObserveStock
    except ImportError:
        return 0
    if VsbObserveStock is None:
        return 0
    rs = (search_date or "").strip()[:20]
    n = 0
    for row in rows:
        code = str(row.get("code") or "").strip()
        if len(code) == 5 and code.isdigit():
            code = code.zfill(6)
        if not code:
            continue
        sd = parse_vsb_signal_date(row.get("breakout_date"))
        if sd is None:
            continue
        snap: Dict[str, Any] = {
            "volume_ratio": parameters.get("volume_ratio"),
            "boom_lookback_min": parameters.get("boom_lookback_min"),
            "boom_lookback_max": parameters.get("boom_lookback_max"),
            "evaluation_mode": parameters.get("evaluation_mode"),
            "screening_date_effective": parameters.get("screening_date_effective"),
            "screening_date_requested": parameters.get("screening_date_requested"),
        }
        ps = row.get("phase_state")
        if isinstance(ps, dict):
            snap["strategy_phase"] = ps.get("strategy_phase")
        name = (str(row.get("name") or "").strip()[:200] or None)
        boom_d = str(row.get("boom_date") or "").strip()[:20] or None
        bst = str(row.get("buy_signal") or "").strip()[:220] or None
        lvl = str(row.get("signal_strength_level") or "").strip()[:20] or None
        existing = (
            db.query(VsbObserveStock)
            .filter(
                VsbObserveStock.market == "CN",
                VsbObserveStock.code == code,
                VsbObserveStock.signal_date == sd,
            )
            .first()
        )
        if existing:
            if name:
                existing.name = name
            existing.boom_date = boom_d
            existing.run_search_date = rs or None
            existing.signal_strength = _i(row.get("signal_strength"))
            existing.signal_strength_level = lvl
            existing.buy_signal_text = bst
            existing.screen_snapshot_json = snap
            existing.updated_at = datetime.now()
        else:
            db.add(
                VsbObserveStock(
                    market="CN",
                    code=code,
                    name=name,
                    signal_date=sd,
                    boom_date=boom_d,
                    run_search_date=rs or None,
                    signal_strength=_i(row.get("signal_strength")),
                    signal_strength_level=lvl,
                    buy_signal_text=bst,
                    screen_snapshot_json=snap,
                )
            )
        n += 1
    return n


def save_screen_hits(
    db: Session,
    rows: List[Dict[str, Any]],
    *,
    parameters: Dict[str, Any],
    search_date: str,
) -> int:
    """
    将选股命中列表写入 volume_shrink_breakout_signals；同一 (code, signal_date) 则更新。
    在信号表提交成功后，默认再写入 vsb_observe_stocks（可用环境变量 VSB_SCREENING_OBSERVE_ENABLED=false 关闭）。
    返回成功写入/更新的信号条数；信号异常时 rollback 并返回 0。
    """
    if not rows:
        return 0
    from backend_api.models import VolumeShrinkBreakoutSignal

    n = 0
    try:
        for row in rows:
            fields = screen_row_to_signal_fields(row, parameters=parameters, search_date=search_date)
            if not fields:
                logger.debug("VSB 信号跳过（无有效 code/signal_date）: %s", row.get("code"))
                continue
            code = fields["code"]
            signal_date = fields["signal_date"]
            existing = (
                db.query(VolumeShrinkBreakoutSignal)
                .filter(
                    VolumeShrinkBreakoutSignal.code == code,
                    VolumeShrinkBreakoutSignal.signal_date == signal_date,
                )
                .first()
            )
            if existing:
                for k, v in fields.items():
                    if k in ("code", "signal_date"):
                        continue
                    setattr(existing, k, v)
                existing.updated_at = datetime.now()
            else:
                rec = VolumeShrinkBreakoutSignal(**fields)
                db.add(rec)
            n += 1
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("VSB 信号批量保存失败: %s", e, exc_info=True)
        return 0

    if _vsb_screening_observe_enabled():
        try:
            no = _save_vsb_observe_from_screen_rows(db, rows, parameters=parameters, search_date=search_date)
            if no > 0:
                db.commit()
                logger.info("VSB 观察股表 vsb_observe_stocks 已写入/更新 %s 条", no)
        except Exception as e:
            db.rollback()
            if _is_vsb_observe_table_missing(e):
                logger.warning(
                    "VSB 观察股表 vsb_observe_stocks 不存在，请在项目根执行: "
                    "python migrations/add_vsb_observe_stocks_table.py（信号表已提交，不影响选股）"
                )
            else:
                logger.warning(
                    "VSB 观察股表写入失败（信号表已提交，不影响选股结果）: %s", e, exc_info=True
                )
    return n
