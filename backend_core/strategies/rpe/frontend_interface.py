"""RPE 前端选股接口：优先读 trace；前复权现算不写 trace。"""

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
        include_no_signal: bool = False,
        adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
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
            adjust_n = str(adjust or "none").strip().lower() or "none"
            if adjust_n not in ("none", "qfq"):
                adjust_n = "none"
            # 前复权必须整簇现算，禁止走预计算 trace
            use_trace = bool(trace_only) and adjust_n == "none"

            resolved_boards: Optional[List[str]] = None
            if board_codes:
                resolved_boards = [str(c).strip() for c in board_codes if str(c).strip()]
            elif board_code:
                resolved_boards = [str(board_code).strip()]

            if use_trace and scope == "cn" and not resolved_boards and not codes:
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
                    "price_adjust": "none",
                    "total": len(rows),
                }

            # 单股/自选：预先检查是否有板块归属，便于返回可读提示
            message = None
            if codes and not resolved_boards:
                board_jobs = engine._resolve_boards_for_codes(list(codes), kind)
                if not board_jobs:
                    message = "未找到所选股票的行业/概念板块归属，无法计算比价效应"
                    return {
                        "data": [],
                        "search_date": trade_date,
                        "config_id": cid,
                        "source": "live_qfq" if adjust_n == "qfq" else "live",
                        "price_adjust": adjust_n,
                        "total": 0,
                        "message": message,
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
                include_no_signal=include_no_signal,
                price_adjust=adjust_n,
                factor_source=factor_source or "auto",
                refresh_factor=bool(refresh_factor),
            )

            # 前复权现算仅供对照，禁止回写 rpe_signal_trace（避免污染不复权预计算）
            if adjust_n != "qfq":
                try:
                    upsert_signal_traces(session, rows, config_id=cid, trade_date=trade_date)
                except Exception as e:
                    logger.warning("RPE save traces skipped: %s", e)

            out: Dict[str, Any] = {
                "data": rows,
                "search_date": trade_date,
                "config_id": cid,
                "source": "live_qfq" if adjust_n == "qfq" else "live",
                "price_adjust": adjust_n,
                "total": len(rows),
            }
            if not rows and resolved_boards:
                min_members = int((cfg.get("scan") or {}).get("min_sector_members", 5))
                reasons = []
                for bc in resolved_boards:
                    members = engine.loader.load_board_members(bc, board_kind=kind)
                    if len(members) < min_members:
                        reasons.append(
                            f"板块 {bc} 有效成分 {len(members)} 只（需≥{min_members}；可能选中了无成分的重复编码）"
                        )
                if reasons:
                    out["message"] = "；".join(reasons)
                else:
                    out["message"] = (
                        "已定位板块但未能计算出有效 Z-Score（可能日线不足、成分过少或前复权因子缺失）"
                        if adjust_n == "qfq"
                        else "已定位板块但未能计算出有效 Z-Score（可能日线不足或成分股过少）"
                    )
            elif not rows and codes and include_no_signal:
                out["message"] = (
                    "已定位板块但未能计算出有效 Z-Score（可能日线不足、成分股过少或前复权因子缺失）"
                    if adjust_n == "qfq"
                    else "已定位板块但未能计算出有效 Z-Score（可能日线不足或成分股过少）"
                )
            return out
        finally:
            if own:
                session.close()
