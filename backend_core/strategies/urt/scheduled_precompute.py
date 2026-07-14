# -*- coding: utf-8 -*-
"""
URT 信号定时预计算（暂仅 A 股）：写入 urt_signal_trace。
由 backend_core/data_collectors/main.py 注册。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: bool = True) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def resolve_urt_trade_date(db) -> str:
    from backend_api.models import HistoricalQuotes

    latest = db.query(func.max(HistoricalQuotes.date)).scalar()
    if latest:
        if hasattr(latest, "strftime"):
            return latest.strftime("%Y-%m-%d")
        return str(latest).strip()[:10]
    return datetime.now().strftime("%Y-%m-%d")


def list_precompute_config_ids(db) -> List[int]:
    from backend_api.models import URTStrategyConfig

    rows = (
        db.query(URTStrategyConfig.id)
        .filter(
            URTStrategyConfig.is_active.is_(True),
            (
                (URTStrategyConfig.is_default.is_(True))
                | (URTStrategyConfig.precompute_enabled.is_(True))
            ),
        )
        .order_by(URTStrategyConfig.id.asc())
        .all()
    )
    ids = [int(r[0]) for r in rows]
    env_raw = (os.getenv("URT_PRECOMPUTE_CONFIG_IDS") or "").strip()
    if env_raw:
        for p in env_raw.split(","):
            p = p.strip()
            if p.isdigit():
                ids.append(int(p))
    return list(dict.fromkeys(ids))


def run_urt_precompute_for_config(
    config_id: int,
    *,
    trade_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """对单个参数版本做全市场 A 股硬筛+得分并落库（含未过硬筛的失败样本不写，只写 buy_signal=True）。"""
    from backend_api.database import SessionLocal
    from backend_core.strategies.urt.config import URTConfigManager
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.strategy_engine import URTStrategyEngine
    from backend_core.strategies.urt.trace_store import upsert_trace_rows

    db = SessionLocal()
    started = datetime.now()
    try:
        try:
            from backend_api.models import URTSignalTrace, URTStrategyConfig

            URTSignalTrace.__table__.create(bind=db.get_bind(), checkfirst=True)
        except Exception:
            pass

        cm = URTConfigManager()
        cm.ensure_default_row(db)
        cfg = cm.get_config(config_id, db=db)
        loader = URTDataLoader(db)
        date_s = trade_date or resolve_urt_trade_date(db)
        date_s = URTDataLoader.resolve_effective_history_end_date(db, date_s)

        stocks = loader.list_a_share_candidates(limit=limit)
        engine = URTStrategyEngine(loader, cfg)
        # 全量扫描：写出所有 buy 信号
        hits = engine.screen_universe(stocks, as_of_end_date=date_s)
        written = upsert_trace_rows(db, config_id=config_id, rows=hits)
        elapsed = (datetime.now() - started).total_seconds()
        logger.info(
            "URT 预计算完成 config_id=%s date=%s candidates=%s hits=%s written=%s elapsed=%.1fs",
            config_id,
            date_s,
            len(stocks),
            len(hits),
            written,
            elapsed,
        )
        return {
            "success": True,
            "config_id": config_id,
            "trade_date": date_s,
            "candidates": len(stocks),
            "hits": len(hits),
            "written": written,
            "elapsed_sec": elapsed,
        }
    except Exception as e:
        logger.exception("URT 预计算失败 config_id=%s: %s", config_id, e)
        return {"success": False, "config_id": config_id, "error": str(e)}
    finally:
        db.close()


def run_urt_precompute_ashare(*, trade_date: Optional[str] = None, limit: Optional[int] = None) -> dict:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        ids = list_precompute_config_ids(db)
    finally:
        db.close()
    if not ids:
        logger.warning("URT 预计算：无 is_default/precompute_enabled 版本，跳过")
        return {"success": True, "skipped": True, "message": "no config"}
    results = [run_urt_precompute_for_config(cid, trade_date=trade_date, limit=limit) for cid in ids]
    ok = all(r.get("success") for r in results)
    return {"success": ok, "results": results}


def scheduled_urt_signals_cn() -> None:
    """定时入口：工作日 A 股全量预计算。"""
    if datetime.now().weekday() >= 5:
        logger.info("URT 预计算跳过周末")
        return
    if not _env_bool("ENABLE_URT_PRECOMPUTE", True):
        logger.info("URT 预计算已禁用 ENABLE_URT_PRECOMPUTE=false")
        return
    run_urt_precompute_ashare()
