"""AkShare 指数日线 → index_historical_quotes（CAN SLIM M 兜底）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_core.config.config import DATA_COLLECTORS
from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.data_collectors.tushare.index_daily import DEFAULT_INDEXES
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

# ts_code -> AkShare stock_zh_index_daily symbol（新浪）
_AK_SYMBOL: Dict[str, str] = {
    "000300.SH": "sh000300",
    "000001.SH": "sh000001",
    "399001.SZ": "sz399001",
    "399006.SZ": "sz399006",
}

UPSERT_SQL = text(
    """
    INSERT INTO index_historical_quotes (
        ts_code, trade_date, code, name,
        open, high, low, close, pre_close, change, pct_chg, vol, amount,
        collected_source, update_time
    ) VALUES (
        :ts_code, CAST(:trade_date AS DATE), :code, :name,
        :open, :high, :low, :close, :pre_close, :change, :pct_chg, :vol, :amount,
        'akshare', CURRENT_TIMESTAMP
    )
    ON CONFLICT (ts_code, trade_date) DO UPDATE SET
        code = EXCLUDED.code,
        name = EXCLUDED.name,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        pre_close = EXCLUDED.pre_close,
        change = EXCLUDED.change,
        pct_chg = EXCLUDED.pct_chg,
        vol = EXCLUDED.vol,
        amount = EXCLUDED.amount,
        collected_source = EXCLUDED.collected_source,
        update_time = CURRENT_TIMESTAMP
    """
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
    for n in names:
        if n in row.index:
            return row.get(n)
        # case-insensitive
        for col in row.index:
            if str(col).lower() == n.lower():
                return row.get(col)
    return None


class AkshareIndexDailyCollector(AKShareCollector):
    def ensure_table(self) -> None:
        session = SessionLocal()
        try:
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS index_historical_quotes (
                        ts_code VARCHAR(16) NOT NULL,
                        trade_date DATE NOT NULL,
                        code VARCHAR(16),
                        name VARCHAR(64),
                        open DOUBLE PRECISION,
                        high DOUBLE PRECISION,
                        low DOUBLE PRECISION,
                        close DOUBLE PRECISION,
                        pre_close DOUBLE PRECISION,
                        change DOUBLE PRECISION,
                        pct_chg DOUBLE PRECISION,
                        vol DOUBLE PRECISION,
                        amount DOUBLE PRECISION,
                        collected_source VARCHAR(32) DEFAULT 'tushare',
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (ts_code, trade_date)
                    )
                    """
                )
            )
            session.commit()
        finally:
            session.close()

    def collect_one(
        self,
        ts_code: str,
        code: str,
        name: str,
        start_date: str,
        end_date: str,
    ) -> int:
        symbol = _AK_SYMBOL.get(ts_code)
        if not symbol:
            self.logger.warning("无 AkShare 指数映射: %s", ts_code)
            return 0
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            return 0
        # 过滤日期
        date_col = "date" if "date" in df.columns else ("日期" if "日期" in df.columns else None)
        if date_col is None:
            return 0
        df = df.copy()
        df["_d"] = pd.to_datetime(df[date_col], errors="coerce")
        start = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        if start is not None:
            df = df[df["_d"] >= start]
        if end is not None:
            df = df[df["_d"] <= end]
        session = SessionLocal()
        n = 0
        try:
            for _, row in df.iterrows():
                d = row.get("_d")
                if d is None or pd.isna(d):
                    continue
                trade_date = pd.Timestamp(d).strftime("%Y-%m-%d")
                session.execute(
                    UPSERT_SQL,
                    {
                        "ts_code": ts_code,
                        "trade_date": trade_date,
                        "code": code,
                        "name": name,
                        "open": _safe_float(_pick(row, "open", "开盘")),
                        "high": _safe_float(_pick(row, "high", "最高")),
                        "low": _safe_float(_pick(row, "low", "最低")),
                        "close": _safe_float(_pick(row, "close", "收盘")),
                        "pre_close": _safe_float(_pick(row, "pre_close", "昨收")),
                        "change": _safe_float(_pick(row, "change", "涨跌额")),
                        "pct_chg": _safe_float(_pick(row, "pct_chg", "涨跌幅")),
                        "vol": _safe_float(_pick(row, "volume", "vol", "成交量")),
                        "amount": _safe_float(_pick(row, "amount", "成交额")),
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

    def collect(
        self,
        *,
        years_back: int = 3,
        indexes: Optional[Sequence[Tuple[str, str, str]]] = None,
    ) -> Dict[str, Any]:
        self.ensure_table()
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=int(years_back) * 365)).strftime("%Y%m%d")
        items: List[Tuple[str, str, str]] = list(indexes or DEFAULT_INDEXES)
        total = 0
        details = []
        for ts_code, code, name in items:
            try:
                n = self.collect_one(ts_code, code, name, start_date, end_date)
                total += n
                details.append({"ts_code": ts_code, "rows": n, "ok": n > 0})
                self.logger.info("AkShare index_daily %s rows=%d", ts_code, n)
            except Exception as e:
                self.logger.warning("AkShare index_daily 失败 %s: %s", ts_code, e)
                details.append({"ts_code": ts_code, "rows": 0, "ok": False, "error": str(e)})
        result = {
            "success": any(d.get("ok") for d in details),
            "source": "akshare",
            "rows": total,
            "start_date": start_date,
            "end_date": end_date,
            "details": details,
        }
        self.logger.info("AkShare index_daily 完成: rows=%s", total)
        return result


def run_akshare_index_daily_collect(**kwargs: Any) -> Dict[str, Any]:
    cfg = dict(DATA_COLLECTORS.get("akshare", {}) or {})
    return AkshareIndexDailyCollector(cfg).collect(**kwargs)
