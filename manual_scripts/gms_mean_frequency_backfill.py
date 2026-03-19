#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁程序：全量计算 A 股与港股全部股票的 GMS 均值频率共振指标（mean_frequency_resonance_indicators）。
- 数据来源：A 股 historical_quotes，港股 historical_quotes_hk（close、volume）
- 已存在记录跳过，不重复计算
- 可指定市场、日期范围、单只股票或测试条数
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import argparse
import logging

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend_api.database import SessionLocal
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator

log_dir = project_root / "logs"
if not log_dir.exists():
    log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "gms_mean_frequency_backfill.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

WINDOW = 20


def _date_to_str(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d).strip()[:10]


class GMSMeanFrequencyBackfill:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self.calc = MeanFrequencyResonanceCalculator()
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

    def get_history(
        self,
        code: str,
        market_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Tuple[str, float, float]]:
        """返回 [(date_yyyy_mm_dd, close, volume), ...] 按日期升序。
        当指定 start_date 时，从 start_date 前 300 天开始取数，确保有足够回看窗口计算 GMS 指标。
        """
        table = "historical_quotes" if market_type == "CN" else "historical_quotes_hk"
        params: dict = {"code": code}
        extra = ""
        if start_date:
            try:
                query_start = (
                    datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=300)
                ).strftime("%Y-%m-%d")
                extra += " AND date >= :query_start "
                params["query_start"] = query_start
            except Exception:
                pass
        if end_date:
            extra += " AND date <= :query_end "
            params["query_end"] = end_date
        q = text(
            f"SELECT date, close, volume FROM {table} WHERE code = :code "
            "AND close IS NOT NULL AND volume IS NOT NULL " + extra + " ORDER BY date ASC"
        )
        rows = self.session.execute(q, params).fetchall()
        out = []
        for r in rows:
            dt_str = _date_to_str(r[0])
            try:
                close_val = float(r[1])
                vol_val = float(r[2])
            except (TypeError, ValueError):
                continue
            out.append((dt_str, close_val, vol_val))
        return out

    def exists(self, code: str, market_type: str, date_str: str) -> bool:
        r = self.session.execute(
            text(
                "SELECT 1 FROM mean_frequency_resonance_indicators "
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
            rows = self.get_history(code, market_type, start_date, end_date)
            if len(rows) < WINDOW + 1:
                self.skipped_stocks += 1
                return True

            dates = [r[0] for r in rows]
            closes = [r[1] for r in rows]
            volumes = [r[2] for r in rows]

            results = self.calc.calculate(closes, volumes, dates=dates, window=WINDOW)
            if not results:
                self.skipped_stocks += 1
                return True

            saved = 0
            skipped = 0
            for i, res in enumerate(results):
                if res is None:
                    continue
                dt_str = dates[i]
                if start_date and dt_str < start_date:
                    continue
                if end_date and dt_str > end_date:
                    continue
                if skip_existing and self.exists(code, market_type, dt_str):
                    skipped += 1
                    continue

                self.session.execute(
                    text("""
                        INSERT INTO mean_frequency_resonance_indicators
                        (code, date, market_type,
                         macro_displacement_delta, amplitude, ratio_d20, ratio_d1,
                         instant_deviation, rising_days_z, falling_days_f,
                         efficiency_m20_minus_m, ma20_d, mavol20_m, bias,
                         d1, d1_date, d20, d20_date, created_at)
                        VALUES
                        (:code, :date, :market_type,
                         :macro_displacement_delta, :amplitude, :ratio_d20, :ratio_d1,
                         :instant_deviation, :rising_days_z, :falling_days_f,
                         :efficiency_m20_minus_m, :ma20_d, :mavol20_m, :bias,
                         :d1, :d1_date, :d20, :d20_date, :created_at)
                        ON CONFLICT (code, date, market_type) DO NOTHING
                    """),
                    {
                        "code": code,
                        "date": dt_str,
                        "market_type": market_type,
                        "macro_displacement_delta": res.get("macro_displacement_delta"),
                        "amplitude": res.get("amplitude"),
                        "ratio_d20": res.get("ratio_d20"),
                        "ratio_d1": res.get("ratio_d1"),
                        "instant_deviation": res.get("instant_deviation"),
                        "rising_days_z": res.get("rising_days_z"),
                        "falling_days_f": res.get("falling_days_f"),
                        "efficiency_m20_minus_m": res.get("efficiency_m20_minus_m"),
                        "ma20_d": res.get("ma20_d"),
                        "mavol20_m": res.get("mavol20_m"),
                        "bias": res.get("bias"),
                        "d1": res.get("d1"),
                        "d1_date": res.get("d1_date"),
                        "d20": res.get("d20"),
                        "d20_date": res.get("d20_date"),
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
            f"开始全量补算 mean_frequency_resonance_indicators：共 {total} 只股票，跳过已存在={skip_existing}"
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
        description="全量计算 A 股+港股 GMS 均值频率共振指标，已计算记录跳过"
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
    parser.add_argument("--no-skip", action="store_true", help="不逐条检查是否已存在，直接插入（重复由 ON CONFLICT DO NOTHING 忽略，可加速）")
    parser.add_argument("--test", type=int, metavar="N", help="测试模式：仅处理前 N 只股票")
    args = parser.parse_args()

    backfill = GMSMeanFrequencyBackfill()
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
