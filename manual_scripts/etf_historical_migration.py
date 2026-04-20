#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF历史行情迁移脚本

数据源降级策略:
1) 东方财富 fund_etf_hist_em
2) 新浪 fund_etf_hist_sina
3) 同花顺 fund_etf_spot_ths (仅支持单日近似补录)

说明:
- 目标表: fund_historical_quotes
- 主键: (code, date)
- 默认使用 UPSERT 覆写同日数据; 开启 --skip-existing 时仅补缺
"""

import argparse
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import text

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend_core.database.db import SessionLocal  # noqa: E402


def _now() -> datetime:
    return datetime.now()


def _to_ymd(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")


def _as_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _normalize_code(code: str) -> str:
    c = str(code or "").strip().lower()
    if c.startswith("sh") or c.startswith("sz"):
        c = c[2:]
    return c


def _to_sina_symbol(code: str) -> str:
    c = _normalize_code(code)
    if c.startswith(("1", "15", "16")):
        return f"sz{c}"
    return f"sh{c}"


class EtfHistoricalMigration:
    def __init__(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[List[str]],
        batch_size: int,
        sleep_ms: int,
        skip_existing: bool,
        recalc_indicators: bool,
        max_retries: int,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.codes = [_normalize_code(c) for c in codes] if codes else None
        self.batch_size = max(1, int(batch_size))
        self.sleep_ms = max(0, int(sleep_ms))
        self.skip_existing = bool(skip_existing)
        self.recalc_indicators = bool(recalc_indicators)
        self.max_retries = max(1, int(max_retries))

        self.session = SessionLocal()
        self.stats = {
            "total_etf": 0,
            "success_etf": 0,
            "failed_etf": 0,
            "inserted_rows": 0,
            "updated_rows": 0,
            "skipped_rows": 0,
        }
        self.source_hits = Counter()
        self.failures: List[Tuple[str, str]] = []

    def close(self):
        self.session.close()

    def run(self) -> int:
        try:
            etf_list = self._load_etf_list()
            self.stats["total_etf"] = len(etf_list)
            if not etf_list:
                print("未找到可迁移ETF代码，脚本结束。")
                return 1

            print(
                f"开始迁移ETF历史行情: {self.start_date} ~ {self.end_date}, "
                f"ETF数量={len(etf_list)}, skip_existing={self.skip_existing}"
            )
            started = _now()

            for idx, (code, name) in enumerate(etf_list, start=1):
                ok = self._migrate_one(code=code, name=name)
                if ok:
                    self.stats["success_etf"] += 1
                else:
                    self.stats["failed_etf"] += 1

                if idx % self.batch_size == 0:
                    self._print_progress(idx)
                    self._sleep()

            elapsed = (_now() - started).total_seconds()
            self._print_summary(elapsed)
            # 有失败则返回非0，便于上层自动化识别
            return 0 if self.stats["failed_etf"] == 0 else 2
        finally:
            self.close()

    def _sleep(self):
        if self.sleep_ms <= 0:
            return
        base = self.sleep_ms / 1000.0
        time.sleep(base + random.uniform(0.0, 0.2))

    def _print_progress(self, done: int):
        print(
            f"[进度] {done}/{self.stats['total_etf']} "
            f"成功ETF={self.stats['success_etf']} 失败ETF={self.stats['failed_etf']} "
            f"插入={self.stats['inserted_rows']} 更新={self.stats['updated_rows']} 跳过={self.stats['skipped_rows']}"
        )

    def _print_summary(self, elapsed_seconds: float):
        print("\n========== 迁移完成 ==========")
        print(f"耗时: {elapsed_seconds:.1f}s")
        print(
            f"ETF总数={self.stats['total_etf']} 成功={self.stats['success_etf']} 失败={self.stats['failed_etf']}"
        )
        print(
            f"行统计: 插入={self.stats['inserted_rows']} 更新={self.stats['updated_rows']} 跳过={self.stats['skipped_rows']}"
        )
        print(f"源命中统计: {dict(self.source_hits)}")
        if self.failures:
            print("失败明细(前20条):")
            for code, err in self.failures[:20]:
                print(f"- {code}: {err}")
        print("================================")

    def _load_etf_list(self) -> List[Tuple[str, str]]:
        if self.codes:
            rows = []
            for c in self.codes:
                row = self.session.execute(
                    text("SELECT code, COALESCE(name, '') FROM fund_basic_info WHERE code=:code"),
                    {"code": c},
                ).fetchone()
                if row:
                    rows.append((_normalize_code(row[0]), str(row[1] or "")))
                else:
                    rows.append((_normalize_code(c), ""))
            return rows

        result = self.session.execute(
            text(
                """
                SELECT code, COALESCE(name, '')
                FROM fund_basic_info
                WHERE COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
                """
            )
        ).fetchall()
        return [(_normalize_code(r[0]), str(r[1] or "")) for r in result]

    def _fetch_with_retry(self, source: str, fn, code: str, name: str) -> Optional[pd.DataFrame]:
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                df = fn(code, name)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                last_err = e
            wait_s = min(2.0 * attempt, 8.0) + random.uniform(0.0, 0.3)
            time.sleep(wait_s)
        if last_err:
            raise RuntimeError(f"{source}获取失败: {last_err}") from last_err
        return None

    def _migrate_one(self, code: str, name: str) -> bool:
        try:
            fetchers = [
                ("eastmoney", self._fetch_eastmoney),
                ("sina", self._fetch_sina),
                ("ths", self._fetch_ths_daily_snapshot),
            ]

            df = None
            used_source = None
            for source, fn in fetchers:
                try:
                    df = self._fetch_with_retry(source, fn, code, name)
                except Exception:
                    df = None
                if df is not None and not df.empty:
                    used_source = source
                    self.source_hits[source] += 1
                    break

            if df is None or df.empty:
                self.failures.append((code, "三源均未获取到可用数据"))
                return False

            inserted, updated, skipped = self._upsert_rows(code, name, used_source, df)
            self.stats["inserted_rows"] += inserted
            self.stats["updated_rows"] += updated
            self.stats["skipped_rows"] += skipped

            if self.recalc_indicators and (inserted > 0 or updated > 0):
                self._recalc_indicators(code)

            return True
        except Exception as e:
            self.session.rollback()
            self.failures.append((code, str(e)))
            return False

    def _fetch_eastmoney(self, code: str, _name: str) -> pd.DataFrame:
        df = ak.fund_etf_hist_em(
            symbol=_normalize_code(code),
            period="daily",
            start_date=_to_ymd(self.start_date),
            end_date=_to_ymd(self.end_date),
            adjust="",
        )
        if df is None or df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": pd.to_datetime(df.get("日期")),
                "open": df.get("开盘"),
                "high": df.get("最高"),
                "low": df.get("最低"),
                "close": df.get("收盘"),
                "volume": df.get("成交量"),
                "amount": df.get("成交额"),
                "amplitude": df.get("振幅"),
                "change_percent": df.get("涨跌幅"),
                "change": df.get("涨跌额"),
                "turnover_rate": df.get("换手率"),
            }
        )

    def _fetch_sina(self, code: str, _name: str) -> pd.DataFrame:
        symbol = _to_sina_symbol(code)
        df = ak.fund_etf_hist_sina(symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()

        mapped = pd.DataFrame(
            {
                "date": pd.to_datetime(df.get("date")),
                "open": df.get("open"),
                "high": df.get("high"),
                "low": df.get("low"),
                "close": df.get("close"),
                "volume": df.get("volume"),
                "amount": None,
                "amplitude": None,
                "change_percent": None,
                "change": None,
                "turnover_rate": None,
            }
        )
        return mapped

    def _fetch_ths_daily_snapshot(self, code: str, _name: str) -> pd.DataFrame:
        """
        同花顺在 akshare 仅提供 fund_etf_spot_ths（实时快照）。
        这里仅在请求区间包含“今天”时，补录今日单日 close/pre_close/change_percent。
        """
        start_obj = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        end_obj = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        today_obj = datetime.now().date()
        if not (start_obj <= today_obj <= end_obj):
            return pd.DataFrame()

        df = ak.fund_etf_spot_ths()
        if df is None or df.empty:
            return pd.DataFrame()

        code_col = "基金代码" if "基金代码" in df.columns else None
        close_col = "当前-单位净值" if "当前-单位净值" in df.columns else None
        pre_close_col = "前一日-单位净值" if "前一日-单位净值" in df.columns else None
        growth_col = "增长率" if "增长率" in df.columns else None

        if code_col is None:
            return pd.DataFrame()

        sub = df[df[code_col].astype(str).str.strip() == _normalize_code(code)]
        if sub.empty:
            return pd.DataFrame()
        row = sub.iloc[0]

        close_v = _to_float(row.get(close_col)) if close_col else None
        pre_close_v = _to_float(row.get(pre_close_col)) if pre_close_col else None
        change_pct = _to_float(row.get(growth_col)) if growth_col else None
        change_v = None
        if close_v is not None and pre_close_v is not None:
            change_v = close_v - pre_close_v

        return pd.DataFrame(
            [
                {
                    "date": pd.to_datetime(today_obj),
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": close_v,
                    "volume": None,
                    "amount": None,
                    "amplitude": None,
                    "change_percent": change_pct,
                    "change": change_v,
                    "turnover_rate": None,
                    "pre_close": pre_close_v,
                }
            ]
        )

    def _existing_dates(self, code: str) -> set:
        rows = self.session.execute(
            text(
                """
                SELECT date
                FROM fund_historical_quotes
                WHERE code=:code
                  AND date >= :start_date
                  AND date <= :end_date
                """
            ),
            {"code": code, "start_date": self.start_date, "end_date": self.end_date},
        ).fetchall()
        return {str(r[0]) for r in rows}

    def _upsert_rows(self, code: str, name: str, source: str, df: pd.DataFrame) -> Tuple[int, int, int]:
        inserted = 0
        updated = 0
        skipped = 0

        existing_dates = self._existing_dates(code) if self.skip_existing else set()
        start_obj = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        end_obj = datetime.strptime(self.end_date, "%Y-%m-%d").date()

        for _, row in df.iterrows():
            d_obj = _as_date(row.get("date"))
            if d_obj is None:
                continue
            if d_obj < start_obj or d_obj > end_obj:
                continue

            d_str = d_obj.strftime("%Y-%m-%d")
            if self.skip_existing and d_str in existing_dates:
                skipped += 1
                continue

            pre_close_v = _to_float(row.get("pre_close"))
            close_v = _to_float(row.get("close"))
            if pre_close_v is None and close_v is not None and _to_float(row.get("change")) is not None:
                pre_close_v = close_v - _to_float(row.get("change"))

            existed = self.session.execute(
                text(
                    """
                    SELECT 1
                    FROM fund_historical_quotes
                    WHERE code=:code AND date=:date
                    LIMIT 1
                    """
                ),
                {"code": code, "date": d_str},
            ).fetchone()

            params = {
                "code": code,
                "name": name or "",
                "date": d_str,
                "open": _to_float(row.get("open")),
                "high": _to_float(row.get("high")),
                "low": _to_float(row.get("low")),
                "close": close_v,
                "pre_close": pre_close_v,
                "volume": _to_float(row.get("volume")),
                "amount": _to_float(row.get("amount")),
                "change_percent": _to_float(row.get("change_percent")),
                "change": _to_float(row.get("change")),
                "amplitude": _to_float(row.get("amplitude")),
                "turnover_rate": _to_float(row.get("turnover_rate")),
                "collected_source": source,
                "collected_date": _now(),
            }
            self.session.execute(
                text(
                    """
                    INSERT INTO fund_historical_quotes
                    (code, name, date, open, high, low, close, pre_close,
                     volume, amount, change_percent, change, amplitude, turnover_rate,
                     collected_source, collected_date)
                    VALUES
                    (:code, :name, :date, :open, :high, :low, :close, :pre_close,
                     :volume, :amount, :change_percent, :change, :amplitude, :turnover_rate,
                     :collected_source, :collected_date)
                    ON CONFLICT (code, date) DO UPDATE SET
                        name = EXCLUDED.name,
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        pre_close = EXCLUDED.pre_close,
                        volume = EXCLUDED.volume,
                        amount = EXCLUDED.amount,
                        change_percent = EXCLUDED.change_percent,
                        change = EXCLUDED.change,
                        amplitude = EXCLUDED.amplitude,
                        turnover_rate = EXCLUDED.turnover_rate,
                        collected_source = EXCLUDED.collected_source,
                        collected_date = EXCLUDED.collected_date
                    """
                ),
                params,
            )
            if existed:
                updated += 1
            else:
                inserted += 1

        self.session.commit()
        return inserted, updated, skipped

    def _recalc_indicators(self, code: str):
        # 延迟导入避免脚本启动时引入额外初始化成本
        from backend_core.data_collectors.akshare.etf_collector import ETFCollector

        collector = ETFCollector()
        try:
            collector._calculate_all_indicators(code, self.start_date, self.end_date)
        finally:
            collector.session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETF历史行情迁移脚本")
    parser.add_argument("--start-date", required=True, help="开始日期: YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="结束日期: YYYY-MM-DD")
    parser.add_argument("--codes", nargs="*", help="指定ETF代码列表，不传则读取 fund_basic_info")
    parser.add_argument("--batch-size", type=int, default=20, help="每批处理ETF数量，默认20")
    parser.add_argument("--sleep-ms", type=int, default=500, help="每批处理后休眠毫秒数，默认500")
    parser.add_argument("--skip-existing", action="store_true", help="仅补缺，不更新已存在记录")
    parser.add_argument(
        "--recalc-indicators",
        action="store_true",
        help="迁移后触发ETF指标重算（MA/MACD/KDJ/RSI/BOLL/MAVOL/均值频率）",
    )
    parser.add_argument("--max-retries", type=int, default=3, help="单数据源最大重试次数，默认3")
    return parser.parse_args()


def validate_dates(start_date: str, end_date: str):
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式错误，需为 YYYY-MM-DD") from exc
    if s > e:
        raise ValueError("开始日期不能晚于结束日期")


def main():
    args = parse_args()
    try:
        validate_dates(args.start_date, args.end_date)
    except Exception as e:
        print(f"参数校验失败: {e}")
        sys.exit(1)

    runner = EtfHistoricalMigration(
        start_date=args.start_date,
        end_date=args.end_date,
        codes=args.codes,
        batch_size=args.batch_size,
        sleep_ms=args.sleep_ms,
        skip_existing=args.skip_existing,
        recalc_indicators=args.recalc_indicators,
        max_retries=args.max_retries,
    )
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    # 允许在 PowerShell 下强制 UTF-8 输出，减少中文乱码
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
