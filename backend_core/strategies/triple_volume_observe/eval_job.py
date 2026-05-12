"""日终：对 triple_volume_observe_stocks 中 待观察/观察中 记录跑 VSB evaluate_stock 并更新状态。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.models import TripleVolumeObserveStock
from backend_core.strategies.triple_volume_observe.env_config import load_scan_env
from backend_core.strategies.volume_shrink_breakout.config import VolumeShrinkBreakoutConfigManager
from backend_core.strategies.volume_shrink_breakout.data_loader import VolumeShrinkBreakoutDataLoader
from backend_core.strategies.volume_shrink_breakout.strategy_engine import evaluate_stock

logger = logging.getLogger(__name__)


def _fetch_hk_hist_desc(db: Session, code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT code, name, date::text, open, close, high, low,
                   change_percent, volume, amount
            FROM historical_quotes_hk
            WHERE code = :code
              AND date::date >= :sd::date
              AND date::date <= :ed::date
            ORDER BY date::date DESC
            """
        ),
        {"code": str(code), "sd": start_date, "ed": end_date},
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        date_str = str(row[2])[:10]
        out.append(
            {
                "code": row[0],
                "name": row[1],
                "date": date_str,
                "open": float(row[3]) if row[3] is not None else 0.0,
                "close": float(row[4]) if row[4] is not None else 0.0,
                "high": float(row[5]) if row[5] is not None else 0.0,
                "low": float(row[6]) if row[6] is not None else 0.0,
                "change_percent": float(row[7]) if row[7] is not None else 0.0,
                "volume": float(row[8]) if row[8] is not None else 0.0,
                "amount": float(row[9]) if row[9] is not None else 0.0,
            }
        )
    return out


def _summarize_vsb(detail: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "boom_date",
        "boom_close",
        "boom_volume",
        "breakout_date",
        "breakout_close",
        "breakout_volume",
        "evaluation_mode",
    )
    return {k: detail.get(k) for k in keys if k in detail}


def run_triple_volume_eval(db: Session) -> Dict[str, Any]:
    cfg_env = load_scan_env()
    if not cfg_env.enabled:
        return {"skipped": True, "reason": "TRIPLE_VOLUME_OBSERVE_ENABLED=false"}

    vsb_cfg = VolumeShrinkBreakoutConfigManager().load_config()
    cal_days = int(vsb_cfg.get("history_calendar_days", 180))
    vr = float(vsb_cfg.get("volume_ratio", 3.0))
    kmin = int(vsb_cfg.get("boom_lookback_min", 5))
    kmax = int(vsb_cfg.get("boom_lookback_max", 60))

    rows = (
        db.query(TripleVolumeObserveStock)
        .filter(TripleVolumeObserveStock.status.in_(("待观察", "观察中")))
        .order_by(TripleVolumeObserveStock.id)
        .all()
    )

    loader = VolumeShrinkBreakoutDataLoader(db)
    start_d, end_d = VolumeShrinkBreakoutDataLoader.default_date_window(cal_days, end_anchor=None)

    updated_trigger = 0
    updated_watch = 0
    errors = 0

    for ob in rows:
        try:
            if ob.market == "HK":
                hist = _fetch_hk_hist_desc(db, ob.code, start_d, end_d)
            else:
                hist = loader.fetch_historical_desc(ob.code, start_date=start_d, end_date=end_d)
            detail = evaluate_stock(
                hist,
                volume_ratio=vr,
                boom_lookback_min=kmin,
                boom_lookback_max=kmax,
                config=vsb_cfg,
            )
            now = datetime.now()
            if detail:
                ob.status = "交易触发"
                ob.vsb_evaluated_at = now
                ob.vsb_detail_json = _summarize_vsb(detail)
                updated_trigger += 1
            else:
                ob.status = "观察中"
                ob.vsb_evaluated_at = now
                ob.vsb_detail_json = None
                updated_watch += 1
            ob.updated_at = now
        except Exception as e:
            errors += 1
            logger.warning("VSB 复核失败 %s %s: %s", ob.market, ob.code, e)

    db.commit()
    out = {
        "skipped": False,
        "candidates": len(rows),
        "updated_trigger": updated_trigger,
        "updated_watch": updated_watch,
        "errors": errors,
    }
    logger.info("triple_volume eval 完成: %s", out)
    return out
