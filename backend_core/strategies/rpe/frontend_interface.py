"""RPE 前端选股接口：优先读 trace。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RPEFrontendInterface:
    @staticmethod
    def get_selection_results(
        *,
        date: Optional[str] = None,
        config_id: Optional[int] = None,
        scope: str = "cn",
        codes: Optional[List[str]] = None,
        board_code: Optional[str] = None,
        board_codes: Optional[List[str]] = None,
        board_kind: str = "industry",
        entry_only: bool = False,
        signal_type: Optional[str] = None,
        trace_only: bool = False,
        max_results: int = 200,
        db=None,
    ) -> Dict[str, Any]:
        from backend_api.database import SessionLocal

        from .config import RPEConfigManager
        from .signal_storage import load_traces, upsert_signal_traces
        from .strategy_engine import RPEStrategyEngine

        own = db is None
        session = db or SessionLocal()
        try:
            cm = RPEConfigManager()
            cid = int(config_id) if config_id is not None else cm.get_default_config_id()
            cfg = cm.get_config(cid)
            engine = RPEStrategyEngine(db_session=session, config=cfg)
            trade_date = date or engine.loader.resolve_trade_date()
            kind = "concept" if board_kind == "concept" else "industry"

            resolved_boards: Optional[List[str]] = None
            if board_codes:
                resolved_boards = [str(c).strip() for c in board_codes if str(c).strip()]
            elif board_code:
                resolved_boards = [str(board_code).strip()]

            if trace_only and scope == "cn" and not resolved_boards and not codes:
                rows = load_traces(
                    session,
                    trade_date=trade_date,
                    config_id=cid,
                    entry_only=entry_only,
                    signal_type=signal_type,
                    limit=max_results,
                )
                return {
                    "data": rows,
                    "search_date": trade_date,
                    "config_id": cid,
                    "source": "trace",
                    "total": len(rows),
                }

            rows = engine.screen(
                date=trade_date,
                config=cfg,
                board_codes=resolved_boards,
                codes=codes,
                entry_only=entry_only,
                signal_type=signal_type,
                max_results=max_results,
                board_kind=kind,
            )

            try:
                upsert_signal_traces(session, rows, config_id=cid, trade_date=trade_date)
            except Exception as e:
                logger.warning("RPE save traces skipped: %s", e)

            return {
                "data": rows,
                "search_date": trade_date,
                "config_id": cid,
                "source": "live",
                "total": len(rows),
            }
        finally:
            if own:
                session.close()
