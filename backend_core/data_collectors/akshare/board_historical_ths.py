# -*- coding: utf-8 -*-
"""同花顺行业/概念板块指数历史 OHLC 采集（仅 board_code_source=tonghuashun）。

优先按 board_code 直连同花顺 K 线接口（绕过 akshare 名称码表），
名称不匹配导致的 KeyError（如「机器人」「电池化学 品」）可避免。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import akshare as ak
import pandas as pd
import py_mini_racer
import requests
from sqlalchemy import text

from akshare.datasets import get_ths_js
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

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
)


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


def normalize_board_name(name: str) -> str:
    """去掉首尾及内部空白，便于与 THS 码表比对。"""
    return re.sub(r"\s+", "", str(name or "").strip())


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


@lru_cache(maxsize=1)
def _ths_js_content() -> str:
    path = get_ths_js("ths.js")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _ths_cookie_v() -> str:
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(_ths_js_content())
    return str(js_code.call("v"))


def _parse_ths_line_payload(text: str) -> pd.DataFrame:
    """解析 d.10jqka.com.cn/v4/line/bk_xxx/01/{year}.js 响应。"""
    if not text or "data" not in text:
        return pd.DataFrame()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return pd.DataFrame()
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return pd.DataFrame()
    raw = obj.get("data") or ""
    if not raw:
        return pd.DataFrame()
    rows = []
    for part in str(raw).split(";"):
        part = part.strip()
        if not part:
            continue
        cols = part.split(",")
        if len(cols) < 7:
            continue
        rows.append(
            {
                "日期": cols[0],
                "开盘价": _safe_float(cols[1]),
                "最高价": _safe_float(cols[2]),
                "最低价": _safe_float(cols[3]),
                "收盘价": _safe_float(cols[4]),
                "成交量": _safe_float(cols[5]),
                "成交额": _safe_float(cols[6]),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def fetch_ths_board_index_by_code(
    board_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """按同花顺板块代码直拉日 K（绕过名称码表）。"""
    code = str(board_code or "").strip()
    if not code:
        return pd.DataFrame()
    try:
        begin_year = int(str(start_date)[:4])
        end_year = int(str(end_date)[:4])
    except (TypeError, ValueError):
        begin_year = datetime.now().year
        end_year = begin_year
    if end_year < begin_year:
        begin_year, end_year = end_year, begin_year

    v_code = _ths_cookie_v()
    headers = {
        "User-Agent": _UA,
        "Referer": "http://q.10jqka.com.cn",
        "Host": "d.10jqka.com.cn",
        "Cookie": f"v={v_code}",
    }
    frames: List[pd.DataFrame] = []
    for year in range(begin_year, end_year + 1):
        url = f"https://d.10jqka.com.cn/v4/line/bk_{code}/01/{year}.js"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            logger.warning("THS 板块指数按代码请求失败 code=%s year=%s: %s", code, year, exc)
            continue
        if resp.status_code != 200 or not resp.text:
            continue
        year_df = _parse_ths_line_payload(resp.text)
        if not year_df.empty:
            frames.append(year_df)

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = normalize_ths_index_df(df)
    if df.empty:
        return df
    start = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
    end = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
    if start is not None and not pd.isna(start):
        df = df[df["_trade_date"] >= start]
    if end is not None and not pd.isna(end):
        df = df[df["_trade_date"] <= end]
    return df.reset_index(drop=True)


def _resolve_symbol_from_name_map(board_kind: str, board_name: str) -> Optional[str]:
    """用规范化名称在 akshare 码表中解析 symbol（仅作兜底）。"""
    target = normalize_board_name(board_name)
    if not target:
        return None
    try:
        if board_kind == "industry":
            from akshare.stock_feature.stock_board_industry_ths import (
                _get_stock_board_industry_name_ths,
            )

            code_map = _get_stock_board_industry_name_ths() or {}
            if board_name in code_map:
                return board_name
            for name in code_map:
                if normalize_board_name(name) == target:
                    return name
        else:
            name_df = ak.stock_board_concept_name_ths()
            if name_df is None or name_df.empty:
                return None
            name_col = "name" if "name" in name_df.columns else name_df.columns[0]
            for name in name_df[name_col].astype(str).tolist():
                if name == board_name or normalize_board_name(name) == target:
                    return name
    except Exception as exc:
        logger.debug("THS 名称码表解析失败 kind=%s name=%s: %s", board_kind, board_name, exc)
    return None


def fetch_ths_board_index(
    board_kind: str,
    board_name: str,
    start_date: str,
    end_date: str,
    *,
    board_code: Optional[str] = None,
) -> pd.DataFrame:
    """拉取同花顺板块指数日线：优先 board_code，失败再按名称。"""
    code = str(board_code or "").strip()
    if code:
        df = fetch_ths_board_index_by_code(code, start_date, end_date)
        if not df.empty:
            return df
        logger.info(
            "THS 按代码无数据，尝试名称兜底 kind=%s code=%s name=%s",
            board_kind,
            code,
            board_name,
        )

    symbol = _resolve_symbol_from_name_map(board_kind, board_name) or normalize_board_name(
        board_name
    )
    if not symbol:
        return pd.DataFrame()
    if board_kind == "industry":
        df = ak.stock_board_industry_index_ths(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        df = ak.stock_board_concept_index_ths(
            symbol=symbol,
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
            df = fetch_ths_board_index(
                board_kind,
                board_name,
                start_date,
                end_date,
                board_code=board_code,
            )
            rows = self.upsert_rows(
                board_kind,
                board_code,
                board_name,
                df,
                collected_source=collected_source,
            )
            if rows <= 0:
                return {
                    "board_code": board_code,
                    "ok": False,
                    "rows": 0,
                    "error": "empty_dataframe",
                }
            return {"board_code": board_code, "ok": True, "rows": rows}
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
