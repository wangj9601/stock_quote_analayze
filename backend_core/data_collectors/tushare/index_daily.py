"""Tushare 指数日线 → index_historical_quotes（CAN SLIM M）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import tushare as ts
from sqlalchemy import text

from backend_core.config.config import DATA_COLLECTORS, TUSHARE_CONFIG
from backend_core.data_collectors.tushare.base import TushareCollector
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

# (ts_code, short_code, name)
DEFAULT_INDEXES: Tuple[Tuple[str, str, str], ...] = (
    ("000300.SH", "000300", "沪深300"),
    ("000001.SH", "000001", "上证指数"),
    ("399001.SZ", "399001", "深证成指"),
    ("399006.SZ", "399006", "创业板指"),
)

UPSERT_SQL = text(
    """
    INSERT INTO index_historical_quotes (
        ts_code, trade_date, code, name,
        open, high, low, close, pre_close, change, pct_chg, vol, amount,
        collected_source, update_time
    ) VALUES (
        :ts_code, CAST(:trade_date AS DATE), :code, :name,
        :open, :high, :low, :close, :pre_close, :change, :pct_chg, :vol, :amount,
        'tushare', CURRENT_TIMESTAMP
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


class IndexDailyCollector(TushareCollector):
    """采集主要 A 股指数日线。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        token = (self.config or {}).get("token") or TUSHARE_CONFIG.get("token") or ""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()

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
        df = self.pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return 0
        session = SessionLocal()
        n = 0
        try:
            for _, row in df.iterrows():
                td = str(row.get("trade_date") or "").strip()
                if not td:
                    continue
                trade_date = f"{td[:4]}-{td[4:6]}-{td[6:8]}" if len(td) == 8 else td
                session.execute(
                    UPSERT_SQL,
                    {
                        "ts_code": ts_code,
                        "trade_date": trade_date,
                        "code": code,
                        "name": name,
                        "open": _safe_float(row.get("open")),
                        "high": _safe_float(row.get("high")),
                        "low": _safe_float(row.get("low")),
                        "close": _safe_float(row.get("close")),
                        "pre_close": _safe_float(row.get("pre_close")),
                        "change": _safe_float(row.get("change")),
                        "pct_chg": _safe_float(row.get("pct_chg")),
                        "vol": _safe_float(row.get("vol")),
                        "amount": _safe_float(row.get("amount")),
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
                details.append({"ts_code": ts_code, "rows": n, "ok": True})
                self.logger.info("index_daily %s rows=%d", ts_code, n)
            except Exception as e:
                self.logger.warning("index_daily 失败 %s: %s", ts_code, e)
                details.append({"ts_code": ts_code, "rows": 0, "ok": False, "error": str(e)})
        result = {
            "success": any(d.get("ok") for d in details),
            "rows": total,
            "start_date": start_date,
            "end_date": end_date,
            "details": details,
        }
        self.logger.info("index_daily 采集完成: rows=%s", total)
        return result


def run_index_daily_collect(**kwargs: Any) -> Dict[str, Any]:
    cfg = dict(DATA_COLLECTORS.get("tushare", {}) or {})
    if TUSHARE_CONFIG.get("token"):
        cfg.setdefault("token", TUSHARE_CONFIG["token"])
    result = IndexDailyCollector(cfg).collect(**kwargs)
    if isinstance(result, dict):
        result.setdefault("source", "tushare")
    return result


def _tushare_token_available() -> bool:
    import os

    token = (
        (TUSHARE_CONFIG.get("token") or "").strip()
        or (os.getenv("TUSHARE_TOKEN") or "").strip()
        or str((DATA_COLLECTORS.get("tushare") or {}).get("token") or "").strip()
    )
    return bool(token)


def run_index_daily_collect_auto(**kwargs: Any) -> Dict[str, Any]:
    """CANSLIM_INDEX_SOURCE=auto|tushare|akshare。

    默认 auto：**优先 AkShare**，失败再回退 Tushare（需 token）。
    """
    import os

    source = (os.getenv("CANSLIM_INDEX_SOURCE") or "auto").strip().lower()
    if source == "tushare":
        return run_index_daily_collect(**kwargs)

    if source == "akshare":
        from backend_core.data_collectors.akshare.index_daily import (
            run_akshare_index_daily_collect,
        )

        return run_akshare_index_daily_collect(**kwargs)

    # auto：AkShare 优先
    from backend_core.data_collectors.akshare.index_daily import (
        run_akshare_index_daily_collect,
    )

    try:
        result = run_akshare_index_daily_collect(**kwargs)
        if isinstance(result, dict) and result.get("success"):
            return result
        logger.warning("AkShare index_daily 未成功，回退 Tushare: %s", result)
    except Exception as e:
        logger.warning("AkShare index_daily 异常，回退 Tushare: %s", e)

    if not _tushare_token_available():
        logger.error("AkShare 指数日线失败且未配置 TUSHARE_TOKEN，无法回退")
        return {
            "success": False,
            "source": "akshare",
            "error": "AkShare failed and TUSHARE_TOKEN missing",
            "rows": 0,
        }

    return run_index_daily_collect(**kwargs)
