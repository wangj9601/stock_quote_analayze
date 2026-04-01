import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
_current_dir = Path(__file__).resolve().parent
# akshare (parent) -> data_collectors (parent) -> backend_core (parent) -> root
_project_root = str(_current_dir.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time

from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

A_SHARE_LOT_SIZE = 100  # A股1手=100股


class HistoricalTurnoverRateCollector(AKShareCollector):
    """历史换手率数据采集器（多级回退）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器

        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))

    def _get_turnover_rate_from_realtime(self, session, code: str, trade_date: str) -> Optional[float]:
        """
        Level 1: 从实时数据表获取换手率

        Args:
            session: 数据库会话
            code: 股票代码
            trade_date: 交易日期 (YYYY-MM-DD)

        Returns:
            Optional[float]: 换手率，获取失败返回 None
        """
        try:
            result = session.execute(text('''
                SELECT turnover_rate
                FROM stock_realtime_quote
                WHERE code = :code AND trade_date = :trade_date
            '''), {'code': code, 'trade_date': trade_date})

            row = result.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return None

        except Exception as e:
            self.logger.debug(f"Level 1 - 从实时表获取 {code} 在 {trade_date} 的换手率失败: {e}")
            return None

    def _calculate_from_free_float_shares(self, session, code: str, trade_date: str) -> Optional[float]:
        """
        Level 2: 从 stock_basic_info.free_float_shares + historical_quotes.volume 计算换手率

        historical_quotes.volume 单位为「手」，free_float_shares 单位为「股」。
        换手率 = (成交量(手) * 100) / 流通股本(股) * 100

        Args:
            session: 数据库会话
            code: 股票代码
            trade_date: 交易日期 (YYYY-MM-DD)

        Returns:
            Optional[float]: 换手率，计算失败返回 None
        """
        try:
            # 获取流通股本
            result = session.execute(text('''
                SELECT free_float_shares FROM stock_basic_info WHERE code = :code
            '''), {'code': code})
            row = result.fetchone()

            if not row or row[0] is None or float(row[0]) <= 0:
                return None

            free_float_shares = float(row[0])

            # 获取成交量
            result = session.execute(text('''
                SELECT volume FROM historical_quotes
                WHERE code = :code AND date = :trade_date
            '''), {'code': code, 'trade_date': trade_date})
            vol_row = result.fetchone()

            if not vol_row or vol_row[0] is None or float(vol_row[0]) <= 0:
                return None

            volume = float(vol_row[0])
            volume_shares = volume * A_SHARE_LOT_SIZE
            turnover_rate = round(volume_shares / free_float_shares * 100, 4)
            self.logger.debug(f"Level 2 - 通过流通股本计算 {code} 换手率: volume_hand={volume}, volume_shares={volume_shares}, "
                              f"free_float={free_float_shares}, rate={turnover_rate}")
            return turnover_rate

        except Exception as e:
            self.logger.debug(f"Level 2 - 从流通股本计算 {code} 换手率失败: {e}")
            return None

    def _calculate_from_market_value(self, session, code: str, trade_date: str) -> Optional[float]:
        """
        Level 3: 从实时表的 circulating_market_value / current_price 推算流通股本后计算换手率

        流通股本 = 流通市值 / 最新价
        historical_quotes.volume 单位为「手」，推算的流通股本单位为「股」。
        换手率 = (成交量(手) * 100) / 流通股本(股) * 100

        Args:
            session: 数据库会话
            code: 股票代码
            trade_date: 交易日期 (YYYY-MM-DD)

        Returns:
            Optional[float]: 换手率，计算失败返回 None
        """
        try:
            # 获取流通市值和最新价（从最近的实时数据获取）
            result = session.execute(text('''
                SELECT circulating_market_value, current_price
                FROM stock_realtime_quote
                WHERE code = :code AND circulating_market_value IS NOT NULL AND current_price > 0
                ORDER BY trade_date DESC
                LIMIT 1
            '''), {'code': code})
            row = result.fetchone()

            if not row or row[0] is None or row[1] is None:
                return None

            circ_market_value = float(row[0])
            current_price = float(row[1])

            if circ_market_value <= 0 or current_price <= 0:
                return None

            # 推算流通股本
            free_float_shares = circ_market_value / current_price

            # 获取成交量
            result = session.execute(text('''
                SELECT volume FROM historical_quotes
                WHERE code = :code AND date = :trade_date
            '''), {'code': code, 'trade_date': trade_date})
            vol_row = result.fetchone()

            if not vol_row or vol_row[0] is None or float(vol_row[0]) <= 0:
                return None

            volume = float(vol_row[0])
            volume_shares = volume * A_SHARE_LOT_SIZE
            turnover_rate = round(volume_shares / free_float_shares * 100, 4)
            self.logger.debug(f"Level 3 - 通过流通市值推算 {code} 换手率: volume_hand={volume}, volume_shares={volume_shares}, "
                              f"circ_mv={circ_market_value}, price={current_price}, rate={turnover_rate}")
            return turnover_rate

        except Exception as e:
            self.logger.debug(f"Level 3 - 从流通市值推算 {code} 换手率失败: {e}")
            return None

    def _get_turnover_rate_with_fallback(self, session, code: str, trade_date: str) -> tuple:
        """
        多级回退获取换手率

        Returns:
            tuple: (turnover_rate, source_level)
                   source_level: 1=实时表直取, 2=流通股本计算, 3=流通市值推算, 0=全部失败
        """
        # Level 1: 实时表直取
        rate = self._get_turnover_rate_from_realtime(session, code, trade_date)
        if rate is not None:
            return rate, 1

        # Level 2: 流通股本计算
        rate = self._calculate_from_free_float_shares(session, code, trade_date)
        if rate is not None:
            return rate, 2

        # Level 3: 流通市值推算
        rate = self._calculate_from_market_value(session, code, trade_date)
        if rate is not None:
            return rate, 3

        return None, 0

    def collect_turnover_rate_for_date(self, date_str: str, progress_every: int = 0) -> bool:
        """
        为指定日期采集所有股票的历史换手率数据

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            progress_every: 每成功更新 N 条打印一次进度日志；<=0 表示不打印

        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info(f"开始采集 {date_str} 的历史换手率数据...")

            session = SessionLocal()
            try:
                # 查询该日期已有的股票数据，但缺少换手率
                result = session.execute(text('''
                    SELECT DISTINCT code, name
                    FROM historical_quotes
                    WHERE date = :date AND (turnover_rate IS NULL OR turnover_rate = 0)
                '''), {'date': date_str})

                stocks_to_update = result.fetchall()

                if not stocks_to_update:
                    self.logger.info(f"{date_str} 的所有股票换手率数据已完整，无需更新")
                    return True

                self.logger.info(f"需要更新换手率数据的股票数量: {len(stocks_to_update)}")

                level_counts = {1: 0, 2: 0, 3: 0}
                success_count = 0
                fail_count = 0

                for stock in stocks_to_update:
                    code = stock[0]
                    name = stock[1]

                    try:
                        turnover_rate, level = self._get_turnover_rate_with_fallback(session, code, date_str)

                        if turnover_rate is not None:
                            update_result = session.execute(text('''
                                UPDATE historical_quotes
                                SET turnover_rate = :turnover_rate
                                WHERE code = :code AND date = :date
                            '''), {
                                'turnover_rate': turnover_rate,
                                'code': code,
                                'date': date_str
                            })

                            if update_result.rowcount > 0:
                                success_count += 1
                                level_counts[level] = level_counts.get(level, 0) + 1
                                self.logger.debug(f"成功更新 {code}({name}) 换手率: {turnover_rate} (Level {level})")
                                if progress_every > 0 and success_count % progress_every == 0:
                                    processed = success_count + fail_count
                                    total = len(stocks_to_update)
                                    self.logger.info(
                                        f"{date_str} 换手率回填进度: 已成功更新 {success_count} 条，"
                                        f"失败 {fail_count} 条，处理 {processed}/{total}"
                                    )
                            else:
                                fail_count += 1
                        else:
                            fail_count += 1
                            self.logger.debug(f"股票 {code}({name}) 在 {date_str} 三级回退均无法获取换手率")

                    except Exception as e:
                        fail_count += 1
                        self.logger.error(f"处理股票 {code}({name}) 换手率数据时异常: {e}")

                    time.sleep(0.01)

                session.commit()
                self.logger.info(
                    f"{date_str} 换手率采集完成 - 成功: {success_count}, 失败: {fail_count} | "
                    f"Level 1(实时表): {level_counts.get(1, 0)}, "
                    f"Level 2(流通股本): {level_counts.get(2, 0)}, "
                    f"Level 3(流通市值): {level_counts.get(3, 0)}"
                )
                return True

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"采集 {date_str} 历史换手率数据时异常: {e}")
            return False

    def collect_turnover_rate_for_period(self, start_date: str, end_date: str, progress_every: int = 0) -> bool:
        """
        为指定时间段采集历史换手率数据

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            progress_every: 传递给单日回填的进度日志阈值

        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info(f"开始采集 {start_date} 到 {end_date} 的历史换手率数据...")

            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            current_dt = start_dt
            total_success = 0
            total_fail = 0

            while current_dt <= end_dt:
                current_date_str = current_dt.strftime('%Y-%m-%d')

                # 跳过周末
                if current_dt.weekday() < 5:
                    if self.collect_turnover_rate_for_date(current_date_str, progress_every=progress_every):
                        total_success += 1
                    else:
                        total_fail += 1

                current_dt += timedelta(days=1)
                time.sleep(0.1)

            self.logger.info(f"时间段 {start_date} 到 {end_date} 换手率采集完成，"
                             f"成功日期: {total_success}, 失败日期: {total_fail}")
            return total_fail == 0

        except Exception as e:
            self.logger.error(f"采集时间段 {start_date} 到 {end_date} 历史换手率数据时异常: {e}")
            return False

    def collect_missing_turnover_rate(self, days_back: int = 30, progress_every: int = 0) -> bool:
        """
        采集最近N天缺失的换手率数据

        Args:
            days_back: 往前追溯的天数
            progress_every: 传递给按区间回填的进度日志阈值

        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info(f"开始采集最近 {days_back} 天缺失的换手率数据...")

            end_date = datetime.now()
            # 确保结束日期是过去的工作日
            while end_date.weekday() >= 5:
                end_date -= timedelta(days=1)

            start_date = end_date - timedelta(days=days_back)

            self.logger.info(f"采集日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

            if start_date >= end_date:
                self.logger.error("日期范围无效")
                return False

            return self.collect_turnover_rate_for_period(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                progress_every=progress_every,
            )

        except Exception as e:
            self.logger.error(f"采集缺失换手率数据时异常: {e}")
            return False

    def run(self):
        """运行采集器"""
        try:
            self.logger.info("历史换手率数据采集器启动（多级回退模式）...")

            success = self.collect_missing_turnover_rate(30)

            if success:
                self.logger.info("历史换手率数据采集完成")
            else:
                self.logger.warning("历史换手率数据采集部分失败")

        except Exception as e:
            self.logger.error(f"历史换手率数据采集器运行异常: {e}")
        finally:
            self.logger.info("历史换手率数据采集器退出")


if __name__ == "__main__":
    collector = HistoricalTurnoverRateCollector()
    collector.run()
