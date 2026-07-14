# -*- coding: utf-8 -*-
"""URT 前台：信号历史 / 计算明细 API。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.strategies.urt.config import URTConfigManager
from backend_core.strategies.urt.data_loader import URTDataLoader
from backend_core.strategies.urt.signal_detector import evaluate_buy_signal
from backend_core.strategies.urt.trace_store import query_trace_by_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["URT Signal"])


@router.get("/urt-signal-trace")
async def get_urt_signal_trace(
    code: str = Query(..., description="股票代码"),
    config_id: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    try:
        cm = URTConfigManager()
        cm.ensure_default_row(db)
        configs = cm.list_configs(db, active_only=True)
        resolved = config_id
        if resolved is None:
            for c in configs:
                if c.get("is_default"):
                    resolved = c["id"]
                    break
            if resolved is None and configs:
                resolved = configs[0]["id"]
        rows = query_trace_by_code(db, code=code, config_id=resolved, limit=limit)
        return {
            "success": True,
            "code": code,
            "config_id": resolved,
            "configs": configs,
            "data": rows,
            "total": len(rows),
        }
    except Exception as e:
        logger.exception("urt-signal-trace 失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/urt-score-detail")
async def get_urt_score_detail(
    code: str = Query(...),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD"),
    config_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """URT 信号计算明细：优先 trace.score_detail，否则实时重算。"""
    try:
        cm = URTConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(config_id, db=db)
        code_n = str(code).strip()
        if code_n.isdigit() and len(code_n) <= 6:
            code_n = code_n.zfill(6)

        # 优先读缓存
        if date:
            from backend_api.models import URTSignalTrace

            resolved = config_id
            if resolved is None:
                from backend_api.models import URTStrategyConfig

                row0 = (
                    db.query(URTStrategyConfig)
                    .filter(URTStrategyConfig.is_default.is_(True))
                    .order_by(URTStrategyConfig.id.asc())
                    .first()
                )
                resolved = int(row0.id) if row0 else None
            if resolved is not None:
                cached = (
                    db.query(URTSignalTrace)
                    .filter(
                        URTSignalTrace.code == code_n,
                        URTSignalTrace.date == str(date)[:10],
                        URTSignalTrace.config_id == int(resolved),
                    )
                    .first()
                )
                if cached and cached.score_detail:
                    return {
                        "success": True,
                        "source": "urt_signal_trace",
                        "code": code_n,
                        "name": cached.name,
                        "date": cached.date,
                        "config_id": resolved,
                        "buy_signal": cached.buy_signal,
                        "score": cached.score,
                        "score_detail": cached.score_detail,
                        "fields": {
                            "close": cached.close,
                            "open": cached.open,
                            "ma20": cached.ma20,
                            "yang_count_4": cached.yang_count_4,
                            "yang_count_5": cached.yang_count_5,
                            "volume_multiple": cached.volume_multiple,
                            "volume_ratio": cached.volume_ratio,
                            "turnover_rate": cached.turnover_rate,
                            "filter_reason": None,
                        },
                    }

        loader = URTDataLoader(db)
        effective = URTDataLoader.resolve_effective_history_end_date(db, date)
        start_s, end_s = URTDataLoader.default_date_window(
            int(cfg.get("history_calendar_days") or 120), effective
        )
        hist = loader.fetch_historical_desc(code_n, start_date=start_s, end_date=end_s)
        hist = [b for b in hist if str(b.get("date") or "")[:10] <= effective]
        detail = evaluate_buy_signal(hist, cfg, require_pass=False)
        if not detail:
            raise HTTPException(status_code=404, detail="数据不足，无法计算明细")
        return {
            "success": True,
            "source": "realtime",
            "code": code_n,
            "name": (hist[0].get("name") if hist else None),
            "date": detail.get("signal_date"),
            "config_id": config_id,
            "buy_signal": detail.get("buy_signal"),
            "score": detail.get("score"),
            "score_detail": detail.get("score_detail"),
            "fields": {
                "close": detail.get("close"),
                "open": detail.get("open"),
                "ma20": detail.get("ma20"),
                "yang_count_4": detail.get("yang_count_4"),
                "yang_count_5": detail.get("yang_count_5"),
                "volume_multiple": detail.get("volume_multiple"),
                "volume_ratio": detail.get("volume_ratio"),
                "turnover_rate": detail.get("turnover_rate"),
                "filter_ok": detail.get("filter_ok"),
                "filter_reason": detail.get("filter_reason"),
                "score_ok": detail.get("score_ok"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("urt-score-detail 失败")
        raise HTTPException(status_code=500, detail=str(e))
