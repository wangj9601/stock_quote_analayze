#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁程序：全量计算 A 股与港股全部股票的成交量指标（mavol_indicators）。
- 数据来源：A 股 historical_quotes，港股 historical_quotes_hk
- 已存在记录跳过，不重复计算
- 可指定市场、日期范围、单只股票或测试条数
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import argparse
import logging

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
import pandas as pd

from backend_api.database import SessionLocal
from backend_core.utils.mavol_calculator import MAVOLCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(project_root / "logs" / "mavol_backfill.log", encoding="utf-8")
        if (project_root / "logs").exists()
        else logging.NullHandler(),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _date_to_str(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d).strip()[:10]


class MAVOLBackfill:
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

    def get_volumes(self, code: str, market_type: str) -> List[tuple]:
        table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
        q = text(
            f"SELECT date, volume FROM {table} WHERE code = :code AND volume IS NOT NULL ORDER BY date ASC"
        )
        rows = self.session.execute(q, {"code": code}).fetchall()
        return [(row[0], row[1]) for row in rows]

    def exists(self, code: str, market_type: str, date_str: str) -> bool:
        r = self.session.execute(
            text(
                "SELECT 1 FROM mavol_indicators WHERE code = :code AND market_type = :mt AND date = :dt LIMIT 1"
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
            rows = self.get_volumes(code, market_type)
            if not rows or len(rows) < 5:
                self.skipped_stocks += 1
                return True

            data = []
            for date_val, vol in rows:
                dt_str = _date_to_str(date_val)
                if start_date and dt_str < start_date:
                    continue
                if end_date and dt_str > end_date:
                    continue
                try:
                    v = float(vol) if vol is not None else None
                except (TypeError, ValueError):
                    v = None
                if v is None:
                    continue
                data.append({"date": dt_str, "volume": v})

            if len(data) < 5:
                self.skipped_stocks += 1
                return True

            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

            mavol_df = MAVOLCalculator.calculate_mavol_for_dataframe(df)
            saved = 0
            skipped = 0

            for _, row in mavol_df.iterrows():
                dt_str = row["date"].strftime("%Y-%m-%d")
                if skip_existing and self.exists(code, market_type, dt_str):
                    skipped += 1
                    continue

                m5 = self._v(row.get("mavol5"))
                m10 = self._v(row.get("mavol10"))
                m20 = self._v(row.get("mavol20"))
                m30 = self._v(row.get("mavol30"))
                m60 = self._v(row.get("mavol60"))
                m120 = self._v(row.get("mavol120"))
                m200 = self._v(row.get("mavol200"))

                self.session.execute(
                    text("""
                        INSERT INTO mavol_indicators
                        (code, date, market_type, mavol5, mavol10, mavol20, mavol30, mavol60, mavol120, mavol200, created_at)
                        VALUES (:code, :date, :market_type, :mavol5, :mavol10, :mavol20, :mavol30, :mavol60, :mavol120, :mavol200, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            mavol5 = EXCLUDED.mavol5,
                            mavol10 = EXCLUDED.mavol10,
                            mavol20 = EXCLUDED.mavol20,
                            mavol30 = EXCLUDED.mavol30,
                            mavol60 = EXCLUDED.mavol60,
                            mavol120 = EXCLUDED.mavol120,
                            mavol200 = EXCLUDED.mavol200,
                            created_at = EXCLUDED.created_at
                    """),
                    {
                        "code": code,
                        "date": dt_str,
                        "market_type": market_type,
                        "mavol5": m5,
                        "mavol10": m10,
                        "mavol20": m20,
                        "mavol30": m30,
                        "mavol60": m60,
                        "mavol120": m120,
                        "mavol200": m200,
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
            return round(float(x), 2)
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
                logger.error(f"未找到股票代码 {code}，请检查市场或代码")
                return

        if test_limit is not None and test_limit > 0:
            stocks = stocks[: test_limit]
            logger.info(f"测试模式：仅处理前 {test_limit} 只")

        total = len(stocks)
        logger.info(f"开始全量补算 mavol_indicators：共 {total} 只股票，跳过已存在={skip_existing}")

        for i, (c, mt) in enumerate(stocks):
            if (i + 1) % 100 == 0 or i == 0:
                logger.info(f"进度 {i+1}/{total} - {mt} {c}")
            self.process_stock(c, mt, start_date, end_date, skip_existing)

        logger.info(
            f"结束：新增/更新 {self.processed_rows} 条，跳过股票 {self.skipped_stocks} 只，跳过已存在 {self.skipped_existing} 条，失败 {self.failed_count} 只"
        )
        if self.failed_list:
            for s in self.failed_list[:20]:
                logger.warning(f"失败: {s}")
            if len(self.failed_list) > 20:
                logger.warning(f"… 共 {len(self.failed_list)} 条失败")


def main():
    parser = argparse.ArgumentParser(
        description="全量计算 A 股+港股 mavol_indicators，已计算记录跳过"
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
    parser.add_argument("--no-skip", action="store_true", help="不跳过已存在，强制重算并覆盖")
    parser.add_argument("--test", type=int, metavar="N", help="测试模式：仅处理前 N 只股票")
    args = parser.parse_args()

    backfill = MAVOLBackfill()
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
