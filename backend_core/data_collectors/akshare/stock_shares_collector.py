import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
_current_dir = Path(__file__).resolve().parent
# akshare (parent) -> data_collectors (parent) -> backend_core (parent) -> root
_project_root = str(_current_dir.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
import logging
import time
import random
from datetime import datetime, timedelta

from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text


class StockSharesCollector(AKShareCollector):
    """股本数据采集器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    def _get_stocks_to_update(self, session, mode: str = 'incremental', max_stocks: Optional[int] = None):
        """
        获取需要更新股本数据的股票列表

        Args:
            session: 数据库会话
            mode: 'full' 全量更新, 'incremental' 增量更新（只更新未填充或超过7天的）
            max_stocks: 最大更新数量限制

        Returns:
            list: [(code, name), ...]
        """
        if mode == 'full':
            query = "SELECT code, name FROM stock_basic_info ORDER BY code"
        else:
            # 增量模式：只更新 shares_updated_at 为 NULL 或超过 7 天的
            query = """
                SELECT code, name FROM stock_basic_info
                WHERE shares_updated_at IS NULL
                   OR shares_updated_at < NOW() - INTERVAL '7 days'
                ORDER BY shares_updated_at ASC NULLS FIRST, code
            """

        if max_stocks:
            query += f" LIMIT {max_stocks}"

        result = session.execute(text(query))
        return result.fetchall()

    def _fetch_shares_info(self, code: str) -> Dict[str, Optional[float]]:
        """
        从 akshare 获取单只股票的股本信息

        Args:
            code: 股票代码

        Returns:
            dict: {'total_shares': float, 'free_float_shares': float}
        """
        try:
            df = self._retry_on_failure(ak.stock_individual_info_em, symbol=code)

            if df is None or df.empty:
                return {'total_shares': None, 'free_float_shares': None}

            total_shares = None
            free_float_shares = None

            for _, row in df.iterrows():
                item = str(row.get('item', '')).strip()
                value = row.get('value', None)

                if item in ('总股本', '总股本(股)'):
                    try:
                        total_shares = float(value)
                    except (ValueError, TypeError):
                        pass
                elif item in ('流通股', '流通股(股)', '流通股本', '流通股本(股)'):
                    try:
                        free_float_shares = float(value)
                    except (ValueError, TypeError):
                        pass

            return {
                'total_shares': total_shares,
                'free_float_shares': free_float_shares
            }

        except Exception as e:
            self.logger.warning(f"获取股票 {code} 股本信息失败: {e}")
            return {'total_shares': None, 'free_float_shares': None}

    def collect_shares(self, mode: str = 'incremental', max_stocks: Optional[int] = None) -> Dict[str, int]:
        """
        采集并更新股本数据

        Args:
            mode: 'full' 全量更新, 'incremental' 增量更新
            max_stocks: 最大更新数量限制

        Returns:
            dict: 采集结果统计
        """
        session = SessionLocal()
        success_count = 0
        fail_count = 0
        skip_count = 0

        try:
            # 确保字段存在
            session.execute(text('''
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='total_shares') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN total_shares REAL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='free_float_shares') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN free_float_shares REAL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='shares_updated_at') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN shares_updated_at TIMESTAMP;
                    END IF;
                END
                $$;
            '''))
            session.commit()

            stocks = self._get_stocks_to_update(session, mode, max_stocks)
            total = len(stocks)
            self.logger.info(f"股本数据采集开始，模式: {mode}，待更新股票数: {total}")

            for i, stock in enumerate(stocks, 1):
                code = stock[0]
                name = stock[1] or ''

                # 跳过退市股票
                if '退' in name:
                    skip_count += 1
                    continue

                try:
                    shares_info = self._fetch_shares_info(code)

                    if shares_info['total_shares'] is not None or shares_info['free_float_shares'] is not None:
                        session.execute(text('''
                            UPDATE stock_basic_info
                            SET total_shares = COALESCE(:total_shares, total_shares),
                                free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                                shares_updated_at = :updated_at
                            WHERE code = :code
                        '''), {
                            'code': code,
                            'total_shares': shares_info['total_shares'],
                            'free_float_shares': shares_info['free_float_shares'],
                            'updated_at': datetime.now()
                        })
                        success_count += 1
                        self.logger.debug(f"更新股票 {code}({name}) 股本数据: "
                                          f"总股本={shares_info['total_shares']}, "
                                          f"流通股本={shares_info['free_float_shares']}")
                    else:
                        skip_count += 1
                        self.logger.debug(f"股票 {code}({name}) 未获取到股本数据，跳过")

                except Exception as e:
                    fail_count += 1
                    self.logger.error(f"处理股票 {code}({name}) 股本数据时异常: {e}")

                # 每 50 条提交一次
                if i % 50 == 0:
                    session.commit()
                    self.logger.info(f"股本数据采集进度: {i}/{total}，"
                                     f"成功: {success_count}，失败: {fail_count}，跳过: {skip_count}")

                # 限速：避免请求过于频繁
                time.sleep(random.uniform(0.3, 0.8))

            session.commit()

            result = {
                'total': total,
                'success': success_count,
                'failed': fail_count,
                'skipped': skip_count
            }
            self.logger.info(f"股本数据采集完成: {result}")
            return result

        except Exception as e:
            self.logger.error(f"股本数据采集异常: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': success_count,
                'failed': fail_count,
                'skipped': skip_count,
                'error': str(e)
            }
        finally:
            session.close()

    def run(self, mode: str = 'incremental', max_stocks: Optional[int] = None):
        """
        运行采集器

        Args:
            mode: 'full' 全量更新, 'incremental' 增量更新
            max_stocks: 最大更新数量限制
        """
        self.logger.info(f"股本数据采集器启动，模式: {mode}")
        result = self.collect_shares(mode=mode, max_stocks=max_stocks)
        self.logger.info(f"股本数据采集器结束，结果: {result}")
        return result


if __name__ == "__main__":
    import argparse
    from backend_core.data_collectors.akshare.stock_shares_collector import StockSharesCollector

    parser = argparse.ArgumentParser(description='股本数据采集器')
    parser.add_argument('--mode', choices=['full', 'incremental'], default='incremental',
                        help='更新模式: full=全量, incremental=增量(默认)')
    parser.add_argument('--max-stocks', type=int, default=None,
                        help='最大更新数量限制')
    args = parser.parse_args()

    collector = StockSharesCollector()
    collector.run(mode=args.mode, max_stocks=args.max_stocks)


