"""SBBR 日终预计算。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def run_sbbr_precompute(
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    max_results: Optional[int] = None,
) -> Dict[str, Any]:
    from backend_api.database import SessionLocal
    from backend_api.models import SBBRFormalTrade

    from .alert_hooks import notify_sbbr_events
    from .config import SBBRConfigManager
    from .signal_storage import upsert_signal_traces
    from .strategy_engine import SBBRStrategyEngine

    cm = SBBRConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    engine = SBBRStrategyEngine(config=cfg)
    date_s = engine.loader.resolve_effective_trade_date(trade_date)

    logger.info("SBBR precompute start config_id=%s date=%s", cid, date_s)
    rows = engine.screen(
        codes=None,
        date=date_s,
        config=cfg,
        require_entry=False,
        require_size=True,
        require_bottom=True,
        max_results=max_results or int((cfg.get("scan") or {}).get("max_results", 200)),
    )

    db = SessionLocal()
    try:
        saved = upsert_signal_traces(db, rows, config_id=cid, trade_date=date_s)

        # 持仓评估
        open_trades = (
            db.query(SBBRFormalTrade)
            .filter(SBBRFormalTrade.status == "open")
            .all()
        )
        position_events: List[Dict[str, Any]] = []
        open_count = len(open_trades)
        for t in open_trades:
            ev = engine.evaluate_position(
                t.code,
                entry_price=float(t.entry_price),
                entry_date=t.signal_date.isoformat() if t.signal_date else None,
                defense_anchor_low=t.defense_anchor_low,
                defense_buffer_pct=t.defense_buffer_pct,
                stage=t.stage,
                allocated_pct=float(t.allocated_pct or 0),
                open_positions=open_count,
                date=date_s,
                config=cfg,
            )
            if not ev.get("ok"):
                continue
            # 回写快照
            t.last_eval_json = ev
            t.updated_at = __import__("datetime").datetime.now()
            breach = (ev.get("defense_breach") or {}).get("breached")
            exit_flags = ev.get("exit_flags") or {}
            if breach:
                position_events.append(
                    {
                        "code": t.code,
                        "name": t.name,
                        "event_type": "defense_breach",
                        "close": ev.get("close"),
                        "message": "尾盘跌破弹性防守下沿",
                    }
                )
            if exit_flags.get("all_ok"):
                position_events.append(
                    {
                        "code": t.code,
                        "name": t.name,
                        "event_type": "exit_full",
                        "close": ev.get("close"),
                        "message": "三要素同时满足，建议全额退出",
                    }
                )
            elif exit_flags.get("any_ok"):
                position_events.append(
                    {
                        "code": t.code,
                        "name": t.name,
                        "event_type": "exit_partial",
                        "close": ev.get("close"),
                        "message": f"退出线索: {','.join(exit_flags.get('flags') or [])}",
                    }
                )
        db.commit()

        entry_rows = [r for r in rows if r.get("entry_signal")]
        notify_sbbr_events(
            entry_rows=entry_rows,
            position_events=position_events,
            trade_date=date_s,
            config=cfg,
        )

        def _stock_brief(r: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "code": r.get("code"),
                "name": r.get("name"),
                "close": r.get("close"),
                "bottom_mode": r.get("bottom_mode"),
                "bottom_matched": bool(r.get("bottom_matched")),
                "entry_signal": bool(r.get("entry_signal")),
                "size_ok": r.get("size_ok"),
                "ma20": r.get("ma20"),
                "volume_ratio": r.get("volume_ratio"),
            }

        bottom_stocks = [_stock_brief(r) for r in rows[:100]]
        entry_stocks = [_stock_brief(r) for r in entry_rows[:100]]
        cfg_name = None
        try:
            for c in cm.list_configs(active_only=False):
                if int(c.get("id") or 0) == int(cid):
                    cfg_name = c.get("name")
                    break
        except Exception:
            cfg_name = None

        summary = {
            "ok": True,
            "config_id": cid,
            "config_name": cfg_name,
            "trade_date": date_s,
            "screened": len(rows),
            "saved": saved,
            "bottom_count": len(rows),
            "entry_count": len(entry_rows),
            "position_events": len(position_events),
            "bottom_stocks": bottom_stocks,
            "entry_stocks": entry_stocks,
        }
        logger.info(
            "SBBR precompute done: config_id=%s date=%s screened=%s entry=%s",
            cid,
            date_s,
            len(rows),
            len(entry_rows),
        )
        return summary
    except Exception as e:
        db.rollback()
        logger.exception("SBBR precompute failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def scheduled_sbbr_signals_cn():
    """定时任务入口。"""
    try:
        return run_sbbr_precompute()
    except Exception as e:
        logger.exception("scheduled_sbbr_signals_cn failed: %s", e)
        return {"ok": False, "error": str(e)}
