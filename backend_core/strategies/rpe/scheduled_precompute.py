"""RPE 日终预计算。以同花顺概念板块为处理单位。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _signal_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """只保留补涨/领涨。区间内无信号成分不落库。"""
    return [r for r in rows if r.get("signal_type") or r.get("entry_signal")]


def _preload_concept_slopes(
    db,
    board_codes: List[str],
    *,
    trade_date: str,
    window: int,
) -> Optional[Dict[str, Optional[float]]]:
    """一次读出概念板斜率；缺失的板合并现算。失败返回 None，调用方改逐板解析。"""
    try:
        from backend_core.board_metrics.sector_slope_store import (
            load_board_sector_slopes,
            refresh_board_sector_slopes,
        )

        stored = load_board_sector_slopes(
            db,
            board_codes,
            board_kind="concept",
            asof_date=trade_date,
            window=window,
        )
        missing = [
            c
            for c in board_codes
            if (stored.get(c) or {}).get("sector_slope") is None
        ]
        if missing:
            refresh_board_sector_slopes(
                db,
                board_kind="concept",
                board_codes=missing,
                end_date=trade_date,
                window=window,
                commit=True,
            )
            stored = load_board_sector_slopes(
                db,
                board_codes,
                board_kind="concept",
                asof_date=trade_date,
                window=window,
            )
        return {c: (stored.get(c) or {}).get("sector_slope") for c in board_codes}
    except Exception as e:
        logger.warning("RPE slope preload skipped: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def run_rpe_precompute(
    *,
    config_id: Optional[int] = None,
    trade_date: Optional[str] = None,
    max_boards: Optional[int] = None,
    max_results: Optional[int] = None,
) -> Dict[str, Any]:
    """按概念板块逐板量权比价并落库。

    同一股票在不同概念上各写一行（sector_id 区分），不做跨板去重，
    也不使用选股页的 scan.max_results 截断。
    max_boards 有值时只重写这些概念；未限制时先清掉该日该配置的全部 trace 再全量写入。
    max_results 保留参数以兼容旧调用，日终概念预计算不使用。
    """
    del max_results  # 概念板块是处理单位，禁止再按全局条数截断
    from backend_api.database import SessionLocal

    from backend_core.strategies.precompute_progress import maybe_log_precompute_progress

    from .config import RPEConfigManager
    from .signal_storage import delete_traces_for_date, upsert_signal_traces
    from .strategy_engine import RPEStrategyEngine

    cm = RPEConfigManager()
    cid = int(config_id) if config_id is not None else cm.get_default_config_id()
    cfg = cm.get_config(cid)
    scan = cfg.get("scan") or {}
    limit = max_boards if max_boards is not None else scan.get("max_boards")
    partial = limit is not None

    db = SessionLocal()
    try:
        engine = RPEStrategyEngine(db_session=db, config=cfg)
        date_s = trade_date or engine.loader.resolve_trade_date()
        boards = engine.loader.list_boards("concept", limit=limit)
        logger.info(
            "RPE concept precompute start config_id=%s date=%s boards=%s partial=%s "
            "(lateral bars + last-window Z + cross-board KDE cache)",
            cid,
            date_s,
            len(boards),
            partial,
        )
        if not boards:
            return {
                "ok": False,
                "config_id": cid,
                "trade_date": date_s,
                "error": "未找到同花顺概念板块",
                "board_kind": "concept",
            }

        sector_ids = [str(b.get("board_code") or "").strip() for b in boards]
        sector_ids = [s for s in sector_ids if s]

        members_by_board = None
        load_members = getattr(engine.loader, "load_concept_members_grouped", None)
        if callable(load_members):
            grouped = load_members()
            if grouped:
                members_by_board = grouped
        slope_window = int(cfg.get("sector_slope_window", 60))
        slope_by_board = _preload_concept_slopes(
            db, sector_ids, trade_date=date_s, window=slope_window
        )
        lookback = int(cfg.get("lookback_days", 250))
        if members_by_board and hasattr(engine.loader, "load_bars_batch"):
            uniq: List[str] = []
            seen: set = set()
            for members in members_by_board.values():
                for m in members:
                    code = str(m.get("code") or "").strip()
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    uniq.append(code)
            t0 = time.perf_counter()
            engine.loader.load_bars_batch(uniq, end_date=date_s, limit=lookback)
            logger.info(
                "RPE preloaded bars codes=%s boards_with_members=%s sec=%.2f",
                len(uniq),
                len(members_by_board),
                time.perf_counter() - t0,
            )

        removed = delete_traces_for_date(
            db,
            config_id=cid,
            trade_date=date_s,
            sector_ids=sector_ids if partial else None,
        )

        saved = 0
        screened = 0
        entry_count = 0
        failed_boards = 0
        progress_state: Dict[str, Any] = {"last": 0}
        total_boards = len(boards)
        for idx, board in enumerate(boards, start=1):
            board_code = str(board.get("board_code") or "").strip()
            if not board_code:
                continue
            board_name = str(board.get("board_name") or board_code)
            try:
                screen_kw: Dict[str, Any] = {}
                if members_by_board is not None:
                    screen_kw["members"] = members_by_board.get(board_code, [])
                if slope_by_board is not None:
                    screen_kw["sector_slope"] = slope_by_board.get(board_code)
                rows = engine.screen_board(
                    board_code,
                    board_name,
                    date=date_s,
                    config=cfg,
                    entry_only=False,
                    board_kind="concept",
                    include_no_signal=False,
                    **screen_kw,
                )
                rows = _signal_rows(rows)
                if rows:
                    saved += upsert_signal_traces(
                        db, rows, config_id=cid, trade_date=date_s
                    )
            except Exception as e:
                failed_boards += 1
                logger.exception("RPE concept board %s failed: %s", board_code, e)
                try:
                    db.rollback()
                except Exception:
                    pass
                continue
            screened += len(rows)
            entry_count += sum(1 for r in rows if r.get("entry_signal"))
            maybe_log_precompute_progress(
                logger,
                "RPE",
                idx,
                total_boards,
                state=progress_state,
                every=10,
                extra="概念板块",
            )

        try:
            from datetime import datetime

            from backend_api.models import RPEPrecomputeRun

            db.add(
                RPEPrecomputeRun(
                    config_id=cid,
                    trade_date=datetime.strptime(date_s[:10], "%Y-%m-%d").date(),
                    market="CN",
                    status="completed",
                    stock_count=screened,
                    message=(
                        f"board_kind=concept saved={saved} boards={total_boards} "
                        f"removed={removed} failed_boards={failed_boards} partial={partial}"
                    ),
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
            "board_kind": "concept",
            "boards": total_boards,
            "partial": partial,
            "removed": removed,
            "failed_boards": failed_boards,
            "screened": screened,
            "saved": saved,
            "entry_count": entry_count,
        }
        logger.info("RPE precompute done: %s", summary)
        return summary
    except Exception as e:
        db.rollback()
        logger.exception("RPE precompute failed: %s", e)
        return {"ok": False, "error": str(e), "board_kind": "concept"}
    finally:
        db.close()


def scheduled_rpe_signals_cn():
    try:
        return run_rpe_precompute()
    except Exception as e:
        logger.exception("scheduled_rpe_signals_cn failed: %s", e)
        return {"ok": False, "error": str(e)}
