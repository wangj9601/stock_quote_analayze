# -*- coding: utf-8 -*-
"""URT 信号写入 urt_signal_trace。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _normalize_a_share_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def delete_trace_for_code_config(db: Session, *, code: str, config_id: int) -> int:
    """删除某股某参数版本的全部 URT 信号历史。"""
    from backend_api.models import URTSignalTrace

    code_n = _normalize_a_share_code(code)
    n = (
        db.query(URTSignalTrace)
        .filter(
            URTSignalTrace.code == code_n,
            URTSignalTrace.config_id == int(config_id),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


def recompute_trace_for_stock(
    db: Session,
    *,
    code: str,
    config_id: int,
    config: Dict[str, Any],
    lookback_calendar_days: Optional[int] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    对单股按交易日滚动重算 URT 信号并写入 urt_signal_trace（require_pass=False，写入可评日）。
    返回写入条数。
    """
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.signal_detector import evaluate_buy_signal

    code_n = _normalize_a_share_code(code)
    if lookback_calendar_days is None:
        env_raw = (os.getenv("URT_TRACE_RECOMPUTE_LOOKBACK_DAYS") or "").strip()
        if env_raw.isdigit():
            lookback_calendar_days = int(env_raw)
        else:
            lookback_calendar_days = max(400, int(config.get("history_calendar_days") or 120) + 280)

    delete_trace_for_code_config(db, code=code_n, config_id=config_id)

    loader = URTDataLoader(db)
    end_s = URTDataLoader.resolve_effective_history_end_date(db, None)
    try:
        end_d = datetime.strptime(end_s, "%Y-%m-%d").date()
    except ValueError:
        end_d = datetime.now().date()
        end_s = end_d.strftime("%Y-%m-%d")
    start_s = (end_d - timedelta(days=int(lookback_calendar_days))).strftime("%Y-%m-%d")
    hist = loader.fetch_historical_desc(code_n, start_date=start_s, end_date=end_s)
    if not hist:
        return 0

    name = str(hist[0].get("name") or "")
    total = len(hist)
    rows: List[Dict[str, Any]] = []
    for i in range(total):
        if progress_cb:
            date_i = str(hist[i].get("date") or "")[:10]
            progress_cb(i + 1, total, f"正在计算 {date_i}（{i + 1}/{total}）")
        try:
            detail = evaluate_buy_signal(hist[i:], config, require_pass=False)
            if not detail:
                continue
            rows.append({"code": code_n, "name": name, **detail})
        except Exception as e:
            logger.debug("URT 单股重算跳过 %s day=%s: %s", code_n, hist[i].get("date"), e)
            continue

    return upsert_trace_rows(db, config_id=config_id, rows=rows)


def upsert_trace_rows(
    db: Session,
    *,
    config_id: int,
    rows: List[Dict[str, Any]],
) -> int:
    """批量 upsert；每行需含 code、signal_date（或 date）。返回写入条数。"""
    from backend_api.models import URTSignalTrace

    n = 0
    now = datetime.now()
    for r in rows:
        code = str(r.get("code") or "").strip()
        date_s = str(r.get("signal_date") or r.get("date") or "")[:10]
        if not code or not date_s:
            continue
        existing = (
            db.query(URTSignalTrace)
            .filter(
                URTSignalTrace.code == code,
                URTSignalTrace.date == date_s,
                URTSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        fields = dict(
            name=r.get("name"),
            buy_signal=bool(r.get("buy_signal")),
            score=r.get("score"),
            signal_strength=r.get("signal_strength", r.get("score")),
            close=r.get("close"),
            open=r.get("open"),
            ma20=r.get("ma20"),
            above_ma20=r.get("above_ma20"),
            yang_count_4=r.get("yang_count_4"),
            yang_count_5=r.get("yang_count_5"),
            yang_rule=r.get("yang_rule"),
            volume=r.get("volume"),
            avg_volume_20=r.get("avg_volume_20"),
            volume_multiple=r.get("volume_multiple"),
            volume_ratio=r.get("volume_ratio"),
            turnover_rate=r.get("turnover_rate"),
            score_detail=r.get("score_detail"),
            created_at=now,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(
                URTSignalTrace(
                    code=code,
                    date=date_s,
                    config_id=int(config_id),
                    **fields,
                )
            )
        n += 1
        if n % 200 == 0:
            db.commit()
    db.commit()
    return n


def query_buy_signals_for_date(
    db: Session,
    *,
    trade_date: str,
    config_id: int,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = (
        db.query(URTSignalTrace)
        .filter(
            URTSignalTrace.date == str(trade_date)[:10],
            URTSignalTrace.config_id == int(config_id),
            URTSignalTrace.buy_signal.is_(True),
        )
        .order_by(URTSignalTrace.score.desc())
    )
    if min_score is not None:
        q = q.filter(URTSignalTrace.score >= float(min_score))
    if limit:
        q = q.limit(int(limit))
    out: List[Dict[str, Any]] = []
    for row in q.all():
        out.append(
            {
                "code": row.code,
                "name": row.name or "",
                "signal_date": row.date,
                "close": row.close,
                "open": row.open,
                "ma20": row.ma20,
                "above_ma20": row.above_ma20,
                "yang_count_4": row.yang_count_4,
                "yang_count_5": row.yang_count_5,
                "yang_rule": row.yang_rule,
                "avg_volume_20": row.avg_volume_20,
                "volume": row.volume,
                "volume_multiple": row.volume_multiple,
                "volume_ratio": row.volume_ratio,
                "turnover_rate": row.turnover_rate,
                "score": row.score,
                "signal_strength": row.signal_strength,
                "score_detail": row.score_detail,
                "buy_signal": True,
                "from_cache": True,
            }
        )
    return out


def query_trace_by_code(
    db: Session,
    *,
    code: str,
    config_id: Optional[int] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = db.query(URTSignalTrace).filter(URTSignalTrace.code == str(code).strip())
    if config_id is not None:
        q = q.filter(URTSignalTrace.config_id == int(config_id))
    rows = q.order_by(URTSignalTrace.date.desc()).limit(int(limit)).all()
    return [
        {
            "code": r.code,
            "name": r.name,
            "date": r.date,
            "config_id": r.config_id,
            "buy_signal": r.buy_signal,
            "score": r.score,
            "close": r.close,
            "open": r.open,
            "ma20": r.ma20,
            "above_ma20": r.above_ma20,
            "yang_count_4": r.yang_count_4,
            "yang_count_5": r.yang_count_5,
            "yang_rule": r.yang_rule,
            "volume": r.volume,
            "avg_volume_20": r.avg_volume_20,
            "volume_multiple": r.volume_multiple,
            "volume_ratio": r.volume_ratio,
            "turnover_rate": r.turnover_rate,
            "score_detail": r.score_detail,
        }
        for r in rows
    ]
