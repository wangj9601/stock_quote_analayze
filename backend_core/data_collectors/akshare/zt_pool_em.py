# -*- coding: utf-8 -*-
"""东方财富涨停股池日采：ak.stock_zt_pool_em → stock_zt_pool_daily。

失败/空表不抛崩调用方，返回 success=False，供复盘计算回退 hist_proxy。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

SOURCE = "em_zt_pool"
_TIME_DIGITS = re.compile(r"^\d{5,6}$")


def _norm_trade_date(trade_date: Optional[str]) -> str:
    if not trade_date:
        return datetime.now().strftime("%Y-%m-%d")
    s = str(trade_date).strip().replace("/", "-")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10:
        return s[:10]
    return datetime.now().strftime("%Y-%m-%d")


def _to_ymd(trade_date: str) -> str:
    return trade_date.replace("-", "")[:8]


def _norm_code(val: Any) -> Optional[str]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    if s.isdigit():
        return s.zfill(6)
    return s


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


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    if f is None:
        return None
    try:
        return int(f)
    except (TypeError, ValueError):
        return None


def _norm_seal_time(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("-", "--", "None", "nan"):
        return None
    if _TIME_DIGITS.match(s):
        s = s.zfill(6)
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    return s


class ZtPoolEmCollector:
    """采集东方财富涨停股池并 UPSERT。"""

    def __init__(self, trade_date: Optional[str] = None) -> None:
        self.trade_date = _norm_trade_date(trade_date)
        self.logger = logger

    def fetch_dataframe(self) -> pd.DataFrame:
        ymd = _to_ymd(self.trade_date)
        self.logger.info("调用 ak.stock_zt_pool_em(date=%s)", ymd)
        df = ak.stock_zt_pool_em(date=ymd)
        if df is None or df.empty:
            raise RuntimeError(f"涨停股池返回空数据 date={ymd}")
        return df

    def dataframe_to_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        col_map = {str(c).strip(): c for c in df.columns}

        def col(*names: str):
            for n in names:
                if n in col_map:
                    return col_map[n]
            return None

        c_code = col("代码", "股票代码")
        if c_code is None:
            raise RuntimeError(f"涨停股池缺少代码列: {list(df.columns)}")

        now = datetime.now()
        by_code: Dict[str, Dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = _norm_code(row.get(c_code))
            if not code:
                continue
            if code in by_code:
                continue
            name_col = col("名称", "股票简称")
            by_code[code] = {
                "code": code,
                "trade_date": self.trade_date,
                "name": (
                    str(row.get(name_col)).strip()
                    if name_col and row.get(name_col) is not None
                    else None
                ),
                "change_percent": _safe_float(row.get(col("涨跌幅"))),
                "price": _safe_float(row.get(col("最新价"))),
                "amount": _safe_float(row.get(col("成交额"))),
                "float_mv": _safe_float(row.get(col("流通市值"))),
                "total_mv": _safe_float(row.get(col("总市值"))),
                "turnover_rate": _safe_float(row.get(col("换手率"))),
                "seal_fund": _safe_float(row.get(col("封板资金"))),
                "first_seal_time": _norm_seal_time(row.get(col("首次封板时间"))),
                "last_seal_time": _norm_seal_time(row.get(col("最后封板时间"))),
                "break_count": _safe_int(row.get(col("炸板次数"))),
                "limit_stats": (
                    str(row.get(col("涨停统计"))).strip()
                    if col("涨停统计") and row.get(col("涨停统计")) is not None
                    else None
                ),
                "board_count": _safe_int(row.get(col("连板数"))),
                "industry": (
                    str(row.get(col("所属行业"))).strip()
                    if col("所属行业") and row.get(col("所属行业")) is not None
                    else None
                ),
                "source": SOURCE,
                "collected_at": now,
            }
        return list(by_code.values())

    def upsert_rows(self, rows: List[Dict[str, Any]], batch_size: int = 500) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_zt_pool_daily (
                code, trade_date, name, change_percent, price, amount,
                float_mv, total_mv, turnover_rate, seal_fund,
                first_seal_time, last_seal_time, break_count, limit_stats,
                board_count, industry, source, collected_at
            ) VALUES (
                :code, :trade_date, :name, :change_percent, :price, :amount,
                :float_mv, :total_mv, :turnover_rate, :seal_fund,
                :first_seal_time, :last_seal_time, :break_count, :limit_stats,
                :board_count, :industry, :source, :collected_at
            )
            ON CONFLICT (code, trade_date) DO UPDATE SET
                name = EXCLUDED.name,
                change_percent = EXCLUDED.change_percent,
                price = EXCLUDED.price,
                amount = EXCLUDED.amount,
                float_mv = EXCLUDED.float_mv,
                total_mv = EXCLUDED.total_mv,
                turnover_rate = EXCLUDED.turnover_rate,
                seal_fund = EXCLUDED.seal_fund,
                first_seal_time = EXCLUDED.first_seal_time,
                last_seal_time = EXCLUDED.last_seal_time,
                break_count = EXCLUDED.break_count,
                limit_stats = EXCLUDED.limit_stats,
                board_count = EXCLUDED.board_count,
                industry = EXCLUDED.industry,
                source = EXCLUDED.source,
                collected_at = EXCLUDED.collected_at
            """
        )
        session = SessionLocal()
        written = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                session.execute(sql, chunk)
                session.commit()
                written += len(chunk)
            return written
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect(self) -> Dict[str, Any]:
        try:
            df = self.fetch_dataframe()
            rows = self.dataframe_to_rows(df)
            written = self.upsert_rows(rows)
            result = {
                "success": True,
                "trade_date": self.trade_date,
                "fetched": len(df),
                "unique": len(rows),
                "written": written,
                "source": SOURCE,
            }
            self.logger.info(
                "涨停股池日采完成 trade_date=%s fetched=%s unique=%s written=%s",
                self.trade_date,
                result["fetched"],
                result["unique"],
                written,
            )
            return result
        except Exception as e:
            self.logger.warning(
                "涨停股池日采失败 trade_date=%s err=%s", self.trade_date, e
            )
            return {
                "success": False,
                "trade_date": self.trade_date,
                "fetched": 0,
                "unique": 0,
                "written": 0,
                "source": SOURCE,
                "error": str(e),
            }


def collect_zt_pool_em(trade_date: Optional[str] = None) -> Dict[str, Any]:
    return ZtPoolEmCollector(trade_date=trade_date).collect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(collect_zt_pool_em())
