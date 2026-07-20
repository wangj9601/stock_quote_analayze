"""RPE 日终预计算。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def run_rpe_precompute(
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    max_boards: Optional[int] = None,
    max_results: Optional[int] = None,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal

    from .config import RPEConfigManager
    from .signal_storage import upsert_signal_traces
    from .strategy_engine import RPEStrategyEngine

    cm = RPEConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    if max_boards is not None:
        cfg = {**cfg, "scan": {**(cfg.get("scan") or {}), "max_boards": max_boards}}

    engine = RPEStrategyEngine(config=cfg)
    date_s = trade_date or engine.loader.resolve_trade_date()
    logger.info("RPE precompute start config_id=%s date=%s", cid, date_s)

    rows = engine.screen(
        date=date_s,
        config=cfg,
        entry_only=False,
        max_results=max_results or int((cfg.get("scan") or {}).get("max_results", 200)),
    )
    db = SessionLocal()
    try:
        saved = upsert_signal_traces(db, rows, config_id=cid, trade_date=date_s)
        # precompute run record
        try:
            from backend_api.models import RPEPrecomputeRun
            from datetime import datetime

            db.add(
                RPEPrecomputeRun(
                    config_id=cid,
                    trade_date=datetime.strptime(date_s[:10], "%Y-%m-%d").date(),
                    market="CN",
                    status="completed",
                    stock_count=len(rows),
                    message=f"saved={saved}",
                    created_at=datetime.now(),
                )
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("RPE precompute run log skipped: %s", e)

        summary = {
            "ok": True,
            "config_id": cid,
            "trade_date": date_s,
            "screened": len(rows),
            "saved": saved,
            "entry_count": sum(1 for r in rows if r.get("entry_signal")),
        }
        logger.info("RPE precompute done: %s", summary)
        return summary
    except Exception as e:
        db.rollback()
        logger.exception("RPE precompute failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def scheduled_rpe_signals_cn():
    try:
        return run_rpe_precompute()
    except Exception as e:
        logger.exception("scheduled_rpe_signals_cn failed: %s", e)
        return {"ok": False, "error": str(e)}
