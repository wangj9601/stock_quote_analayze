#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁程序：全量计算 A 股与港股全部股票的 MA 指标（ma_indicators）。
- 数据来源：A 股 historical_quotes，港股 historical_quotes_hk（close）
- 已计算的记录跳过，不重复计算
- 可指定市场、日期范围、单只股票或测试条数
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
import argparse
import logging

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
import pandas as pd

from backend_api.database import SessionLocal
from backend_core.utils.ma_calculator import MACalculator

PERIODS = [5, 10, 20, 30, 60, 120, 200]

log_dir = project_root / "logs"
if not log_dir.exists():
    log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "ma_indicators_backfill.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _date_to_str(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


class MAIndicatorsBackfill:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self.processed_rows = 0
        self.skipped_stocks = 0
        self.skipped_existing = 0
        self.failed_count = 0
        self.failed_list: List[str] = []

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

    def get_stock_list(self, market_type: str) -> List[str]:
        if market_type == "CN":
            r = self.session.execute(
                text("SELECT DISTINCT code FROM historical_quotes ORDER BY code")
            )
        else:
            r = self.session.execute(
                text("SELECT DISTINCT code FROM historical_quotes_hk ORDER BY code")
            )
        return [row[0] for row in r.fetchall()]

    def get_closes(self, code: str, market_type: str) -> List[Tuple[str, float]]:
        """返回 [(date_yyyy_mm_dd, close), ...] 按日期升序"""
        table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
        q = text(
            f"SELECT date, close FROM {table} WHERE code = :code "
            "AND close IS NOT NULL ORDER BY date ASC"
        )
        rows = self.session.execute(q, {"code": code}).fetchall()
        out = []
        for r in rows:
            dt_str = _date_to_str(r[0])
            try:
                close_val = float(r[1])
            except (TypeError, ValueError):
                continue
            out.append((dt_str, close_val))
        return out

    def exists(self, code: str, market_type: str, date_str: str) -> bool:
        r = self.session.execute(
            text(
                "SELECT 1 FROM ma_indicators "
                "WHERE code = :code AND market_type = :mt AND date = :dt LIMIT 1"
            ),
            {"code": code, "mt": market_type, "dt": date_str},
        )
        return r.fetchone() is not None

    def process_stock(
        self,
        code: str,
        market_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip_existing: bool = True,
    ) -> bool:
        try:
            rows = self.get_closes(code, market_type)
            if len(rows) < min(PERIODS):
                self.skipped_stocks += 1
                return True

            data = []
            for dt_str, close in rows:
                if start_date and dt_str < start_date:
                    continue
                if end_date and dt_str > end_date:
                    continue
                data.append({"date": dt_str, "close": close})

            if len(data) < min(PERIODS):
                self.skipped_stocks += 1
                return True

            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

            ma_df = MACalculator.calculate_ma_for_dataframe(df, periods=PERIODS)
            saved = 0
            skipped = 0

            for _, row in ma_df.iterrows():
                dt_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])[:10]
                if skip_existing and self.exists(code, market_type, dt_str):
                    skipped += 1
                    continue

                self.session.execute(
                    text("""
                        INSERT INTO ma_indicators
                        (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200, created_at)
                        VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200, :created_at)
                        ON CONFLICT (code, date, market_type) DO NOTHING
                    """),
                    {
                        "code": code,
                        "date": dt_str,
                        "market_type": market_type,
                        "ma5": self._v(row.get("ma5")),
                        "ma10": self._v(row.get("ma10")),
                        "ma20": self._v(row.get("ma20")),
                        "ma30": self._v(row.get("ma30")),
                        "ma60": self._v(row.get("ma60")),
                        "ma120": self._v(row.get("ma120")),
                        "ma200": self._v(row.get("ma200")),
                        "created_at": datetime.now(),
                    },
                )
                saved += 1

            if saved > 0:
                self.session.commit()
                self.processed_rows += saved
                self.skipped_existing += skipped
                logger.info(
                    f"{market_type} {code}: 新增 {saved} 条，跳过已存在 {skipped} 条"
                )
            else:
                self.skipped_stocks += 1
            return True
        except Exception as e:
            logger.exception(f"处理 {market_type} {code} 失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_list.append(f"{market_type}:{code} -> {e}")
            return False

    @staticmethod
    def _v(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        try:
            return round(float(x), 4)
        except (TypeError, ValueError):
            return None

    def run(
        self,
        market: str = "ALL",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        code: Optional[str] = None,
        skip_existing: bool = True,
        test_limit: Optional[int] = None,
    ):
        if market.upper() == "ALL":
            codes_cn = self.get_stock_list("CN")
            codes_hk = self.get_stock_list("HK")
            stocks = [(c, "CN") for c in codes_cn] + [(c, "HK") for c in codes_hk]
        elif market.upper() in ("CN", "A"):
            stocks = [(c, "CN") for c in self.get_stock_list("CN")]
        elif market.upper() in ("HK", "H"):
            stocks = [(c, "HK") for c in self.get_stock_list("HK")]
        else:
            logger.error("market 须为 ALL / CN / HK")
            return

        if code:
            codes_cn = self.get_stock_list("CN")
            codes_hk = self.get_stock_list("HK")
            if code in codes_cn:
                stocks = [(code, "CN")]
            elif code in codes_hk:
                stocks = [(code, "HK")]
            else:
                logger.error(f"未找到股票代码 {code}")
                return

        if test_limit is not None and test_limit > 0:
            stocks = stocks[:test_limit]
            logger.info(f"测试模式：仅处理前 {test_limit} 只")

        total = len(stocks)
        logger.info(
            f"开始全量补算 ma_indicators：共 {total} 只股票，跳过已存在={skip_existing}"
        )

        for i, (c, mt) in enumerate(stocks):
            if (i + 1) % 100 == 0 or i == 0:
                logger.info(f"进度 {i+1}/{total} - {mt} {c}")
            self.process_stock(c, mt, start_date, end_date, skip_existing)

        logger.info(
            f"结束：新增 {self.processed_rows} 条，跳过股票 {self.skipped_stocks} 只，"
            f"跳过已存在 {self.skipped_existing} 条，失败 {self.failed_count} 只"
        )
        if self.failed_list:
            for s in self.failed_list[:20]:
                logger.warning(f"失败: {s}")
            if len(self.failed_list) > 20:
                logger.warning(f"… 共 {len(self.failed_list)} 条失败")


def main():
    parser = argparse.ArgumentParser(
        description="全量计算 A 股+港股 MA 指标，已计算记录跳过"
    )
    parser.add_argument(
        "--market",
        choices=["ALL", "CN", "HK"],
        default="ALL",
        help="市场：ALL=全部，CN=A股，HK=港股",
    )
    parser.add_argument("--start-date", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--code", help="仅处理指定股票代码")
    parser.add_argument("--no-skip", action="store_true", help="不逐条检查是否已存在，直接插入（重复由 ON CONFLICT DO NOTHING 忽略）")
    parser.add_argument("--test", type=int, metavar="N", help="测试模式：仅处理前 N 只股票")
    args = parser.parse_args()

    backfill = MAIndicatorsBackfill()
    try:
        backfill.run(
            market=args.market,
            start_date=args.start_date,
            end_date=args.end_date,
            code=args.code,
            skip_existing=not args.no_skip,
            test_limit=args.test,
        )
    finally:
        backfill.close()


if __name__ == "__main__":
    main()
