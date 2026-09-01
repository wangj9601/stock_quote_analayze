# -*- coding: utf-8 -*-
"""同花顺行业/概念板块指数历史 OHLC 采集（仅 board_code_source=tonghuashun）。"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

TABLE_BY_KIND = {
    "industry": "industry_board_historical_quotes",
    "concept": "concept_board_historical_quotes",
}

BASIC_INFO_BY_KIND = {
    "industry": "industry_board_basic_info",
    "concept": "concept_board_basic_info",
}


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pick(row: pd.Series, *names: str) -> Any:
    for name in names:
        if name in row.index:
            return row.get(name)
        for col in row.index:
            if str(col).strip().lower() == name.lower():
                return row.get(col)
    return None


def normalize_ths_index_df(df: pd.DataFrame) -> pd.DataFrame:
    """将 THS 指数 DataFrame 列名归一化。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    date_col = None
    for c in out.columns:
        if str(c) in ("日期", "date"):
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame()
    out["_trade_date"] = pd.to_datetime(out[date_col], errors="coerce")
    out = out[out["_trade_date"].notna()]
    return out


def fetch_ths_board_index(
    board_kind: str,
    board_name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """拉取同花顺板块指数日线。"""
    if board_kind == "industry":
        df = ak.stock_board_industry_index_ths(
            symbol=board_name,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        df = ak.stock_board_concept_index_ths(
            symbol=board_name,
            start_date=start_date,
            end_date=end_date,
        )
    return normalize_ths_index_df(df)


class BoardHistoricalThsCollector:
    """同花顺板块指数历史采集。"""

    def __init__(
        self,
        *,
        request_interval: float = 0.35,
        board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
    ) -> None:
        self.request_interval = request_interval
        self.board_code_source = board_code_source
        self.logger = logger

    def ensure_tables(self) -> None:
        session = SessionLocal()
        try:
            for table in TABLE_BY_KIND.values():
                session.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            board_code VARCHAR(20) NOT NULL,
                            trade_date DATE NOT NULL,
                            board_name VARCHAR(100),
                            open DOUBLE PRECISION,
                            high DOUBLE PRECISION,
                            low DOUBLE PRECISION,
                            close DOUBLE PRECISION,
                            volume DOUBLE PRECISION,
                            amount DOUBLE PRECISION,
                            collected_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
                            update_time TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                            PRIMARY KEY (board_code, trade_date)
                        )
                        """
                    )
                )
            session.commit()
        finally:
            session.close()

    def load_boards(
        self,
        board_kind: str,
        board_codes: Optional[Sequence[str]] = None,
    ) -> List[Tuple[str, str]]:
        """返回 [(board_code, board_name), ...]。"""
        table = BASIC_INFO_BY_KIND.get(board_kind, "industry_board_basic_info")
        session = SessionLocal()
        try:
            sql = f"""
                SELECT board_code, board_name
                FROM {table}
                WHERE board_code_source = :src
            """
            params: Dict[str, Any] = {"src": self.board_code_source}
            if board_codes:
                codes = [str(c).strip() for c in board_codes if str(c).strip()]
                if codes:
                    placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
                    sql += f" AND board_code IN ({placeholders})"
                    for i, code in enumerate(codes):
                        params[f"c{i}"] = code
            rows = session.execute(text(sql), params).fetchall()
            return [(r.board_code, r.board_name) for r in rows if r.board_name]
        finally:
            session.close()

    def upsert_rows(
        self,
        board_kind: str,
        board_code: str,
        board_name: str,
        df: pd.DataFrame,
        *,
        collected_source: str = "tonghuashun",
    ) -> int:
        if df is None or df.empty:
            return 0
        table = TABLE_BY_KIND[board_kind]
        insert_sql = text(
            f"""
            INSERT INTO {table} (
                board_code, trade_date, board_name,
                open, high, low, close, volume, amount,
                collected_source, update_time
            ) VALUES (
                :board_code, CAST(:trade_date AS DATE), :board_name,
                :open, :high, :low, :close, :volume, :amount,
                :collected_source, CURRENT_TIMESTAMP
            )
            ON CONFLICT (board_code, trade_date) DO UPDATE SET
                board_name = EXCLUDED.board_name,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount,
                collected_source = EXCLUDED.collected_source,
                update_time = CURRENT_TIMESTAMP
            """
        )
        session = SessionLocal()
        n = 0
        try:
            for _, row in df.iterrows():
                trade_date = pd.Timestamp(row["_trade_date"]).strftime("%Y-%m-%d")
                session.execute(
                    insert_sql,
                    {
                        "board_code": board_code,
                        "trade_date": trade_date,
                        "board_name": board_name,
                        "open": _safe_float(_pick(row, "开盘价", "open")),
                        "high": _safe_float(_pick(row, "最高价", "high")),
                        "low": _safe_float(_pick(row, "最低价", "low")),
                        "close": _safe_float(_pick(row, "收盘价", "close")),
                        "volume": _safe_float(_pick(row, "成交量", "volume")),
                        "amount": _safe_float(_pick(row, "成交额", "amount")),
                        "collected_source": collected_source,
                    },
                )
                n += 1
            session.commit()
            return n
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect_board(
        self,
        board_kind: str,
        board_code: str,
        board_name: str,
        start_date: str,
        end_date: str,
        *,
        collected_source: str = "tonghuashun",
    ) -> Dict[str, Any]:
        try:
            df = fetch_ths_board_index(board_kind, board_name, start_date, end_date)
            rows = self.upsert_rows(
                board_kind,
                board_code,
                board_name,
                df,
                collected_source=collected_source,
            )
            return {"board_code": board_code, "ok": rows > 0, "rows": rows}
        except Exception as exc:
            self.logger.warning(
                "THS 板块指数采集失败 kind=%s code=%s name=%s: %s",
                board_kind,
                board_code,
                board_name,
                exc,
            )
            return {"board_code": board_code, "ok": False, "rows": 0, "error": str(exc)}

    def collect(
        self,
        *,
        mode: str = "backfill",
        years_back: int = 3,
        trade_date: Optional[str] = None,
        board_kinds: Optional[Sequence[str]] = None,
        board_codes: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """
        mode=backfill: 按 years_back 回补历史
        mode=daily: 仅拉取 trade_date 附近最近 3 个交易日窗口
        """
        self.ensure_tables()
        end_dt = datetime.now()
        if trade_date:
            end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        end_date = end_dt.strftime("%Y%m%d")

        if mode == "daily":
            start_dt = end_dt - timedelta(days=5)
            start_date = start_dt.strftime("%Y%m%d")
        else:
            start_dt = end_dt - timedelta(days=int(years_back) * 365)
            start_date = start_dt.strftime("%Y%m%d")

        kinds = list(board_kinds or ("industry", "concept"))
        details: List[Dict[str, Any]] = []
        total_rows = 0
        ok_count = 0
        fail_count = 0

        for kind in kinds:
            boards = self.load_boards(kind, board_codes)
            self.logger.info("THS 板块历史 kind=%s boards=%d mode=%s", kind, len(boards), mode)
            for board_code, board_name in boards:
                result = self.collect_board(
                    kind,
                    board_code,
                    board_name,
                    start_date,
                    end_date,
                )
                details.append({**result, "kind": kind, "board_name": board_name})
                total_rows += int(result.get("rows") or 0)
                if result.get("ok"):
                    ok_count += 1
                else:
                    fail_count += 1
                if self.request_interval > 0:
                    time.sleep(self.request_interval)

        return {
            "success": ok_count > 0,
            "mode": mode,
            "start_date": start_date,
            "end_date": end_date,
            "boards_ok": ok_count,
            "boards_failed": fail_count,
            "rows": total_rows,
            "details": details,
        }


def run_board_historical_ths_collect(**kwargs: Any) -> Dict[str, Any]:
    return BoardHistoricalThsCollector().collect(**kwargs)
