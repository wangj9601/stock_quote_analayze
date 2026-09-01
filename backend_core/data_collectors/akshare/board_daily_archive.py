# -*- coding: utf-8 -*-
"""同花顺板块每日历史归档：THS 指数 API 优先，行业实时快照兜底。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.data_collectors.akshare.board_historical_ths import (
    BoardHistoricalThsCollector,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)


class BoardDailyArchiveCollector:
    """收盘后将同花顺板块行情写入历史 OHLC 表。"""

    def __init__(self) -> None:
        self.ths_collector = BoardHistoricalThsCollector()
        self.logger = logger

    def _existing_boards_for_date(self, trade_date: str) -> Set[str]:
        """已写入历史表的 board_code（行业+概念）。"""
        session = SessionLocal()
        codes: Set[str] = set()
        try:
            for table in (
                "industry_board_historical_quotes",
                "concept_board_historical_quotes",
            ):
                rows = session.execute(
                    text(
                        f"""
                        SELECT board_code FROM {table}
                        WHERE trade_date = CAST(:d AS DATE)
                        """
                    ),
                    {"d": trade_date},
                ).fetchall()
                codes.update(r.board_code for r in rows)
        finally:
            session.close()
        return codes

    def _archive_industry_from_realtime(self, trade_date: str) -> Dict[str, Any]:
        """行业板：从 realtime 表取当日最后快照作为 close 兜底。"""
        session = SessionLocal()
        success = 0
        failed = 0
        try:
            rows = session.execute(
                text(
                    """
                    SELECT DISTINCT ON (q.board_code)
                        q.board_code,
                        q.board_name,
                        q.latest_price,
                        q.change_amount,
                        q.change_percent,
                        q.volume,
                        q.amount
                    FROM industry_board_realtime_quotes q
                    INNER JOIN industry_board_basic_info b
                        ON b.board_code = q.board_code
                    WHERE b.board_code_source = :src
                      AND LEFT(CAST(q.update_time AS TEXT), 10) = :trade_date
                    ORDER BY q.board_code, q.update_time DESC
                    """
                ),
                {"src": DEFAULT_BOARD_CODE_SOURCE, "trade_date": trade_date},
            ).fetchall()

            insert_sql = text(
                """
                INSERT INTO industry_board_historical_quotes (
                    board_code, trade_date, board_name,
                    open, high, low, close, volume, amount,
                    collected_source, update_time
                ) VALUES (
                    :board_code, CAST(:trade_date AS DATE), :board_name,
                    NULL, NULL, NULL, :close, :volume, :amount,
                    'realtime_archive', CURRENT_TIMESTAMP
                )
                ON CONFLICT (board_code, trade_date) DO NOTHING
                """
            )

            for row in rows:
                try:
                    session.execute(
                        insert_sql,
                        {
                            "board_code": row.board_code,
                            "trade_date": trade_date,
                            "board_name": row.board_name,
                            "close": row.latest_price,
                            "volume": row.volume,
                            "amount": row.amount,
                        },
                    )
                    success += 1
                except Exception as exc:
                    self.logger.warning(
                        "行业板实时兜底失败 code=%s: %s", row.board_code, exc
                    )
                    failed += 1
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return {"success": success, "failed": failed}

    def run(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        self.logger.info("开始同花顺板块日归档 trade_date=%s", trade_date)

        ths_result = self.ths_collector.collect(
            mode="daily",
            trade_date=trade_date,
            board_kinds=("industry", "concept"),
        )

        existing = self._existing_boards_for_date(trade_date)
        ths_ok_codes = {
            d["board_code"]
            for d in ths_result.get("details") or []
            if d.get("ok") and d.get("rows", 0) > 0
        }

        fallback_result: Dict[str, Any] = {"success": 0, "failed": 0, "skipped": True}
        industry_boards = self.ths_collector.load_boards("industry")
        missing_industry = [
            code
            for code, _ in industry_boards
            if code not in existing and code not in ths_ok_codes
        ]
        if missing_industry:
            fallback_result = self._archive_industry_from_realtime(trade_date)
            fallback_result["skipped"] = False
            fallback_result["missing_count"] = len(missing_industry)

        return {
            "success": ths_result.get("success") or fallback_result.get("success", 0) > 0,
            "trade_date": trade_date,
            "ths": ths_result,
            "realtime_fallback": fallback_result,
        }


def run_board_daily_archive(trade_date: Optional[str] = None) -> Dict[str, Any]:
    return BoardDailyArchiveCollector().run(trade_date=trade_date)
