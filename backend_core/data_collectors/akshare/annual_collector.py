#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股年线数据生成器 - 基于A股半年线数据生成年线数据并保存到数据库"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from backend_core.database.db import SessionLocal
from backend_core.data_collectors.akshare.period_agg import resample_ohlcv_to_period_ends
from sqlalchemy import text

from backend_core.logging_utils import should_log_to_file, resolve_log_file
_handlers = [logging.StreamHandler()]
if should_log_to_file():
    _handlers.append(logging.FileHandler(resolve_log_file('annual_generation.log'), encoding='utf-8'))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=_handlers)
logger = logging.getLogger(__name__)

class AnnualDataGenerator:
    """A股年线数据生成器（基于半年线数据累加）"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.generated_count = 0
        self.failed_count = 0
        self._init_db()

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()

    def _init_db(self):
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS annual_quotes (
                    code TEXT, ts_code TEXT, name TEXT, market TEXT, date TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL,
                    change_percent REAL, change REAL, amplitude REAL, turnover_rate REAL,
                    collected_source TEXT, collected_date TIMESTAMP,
                    PRIMARY KEY (code, date)
                )
            '''))
            self.session.commit()
            logger.info("A股年线数据表初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")

    def get_stock_list(self) -> List[Dict[str, str]]:
        try:
            result = self.session.execute(text("SELECT code, name FROM stock_basic_info WHERE COALESCE(collect_enabled, TRUE) = TRUE ORDER BY code"))
            stocks = [{'code': row[0], 'name': row[1] if row[1] else ''} for row in result.fetchall()]
            logger.info(f"从数据库获取到 {len(stocks)} 只A股")
            return stocks
        except Exception as e:
            logger.error(f"获取A股列表失败: {e}")
            return []

    def generate_single_stock_annual_data(self, stock_code: str, start_date: str, end_date: str) -> bool:
        try:
            query = text("""
                SELECT date, open, high, low, close, volume, amount, name
                FROM semiannual_quotes
                WHERE code = :code AND date >= :start_date AND date <= :end_date
                ORDER BY date ASC
            """)
            
            result = self.session.execute(query, {'code': stock_code, 'start_date': start_date, 'end_date': end_date})
            rows = result.fetchall()
            if not rows:
                return True
                
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'name'])
            # 处理日期格式：支持 YYYY-MM-DD 和 YYYYMMDD 格式
            def normalize_date(date_val):
                if isinstance(date_val, str):
                    # 如果是 YYYYMMDD 格式（8位数字），转换为 YYYY-MM-DD
                    if len(date_val) == 8 and date_val.isdigit():
                        return f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                return date_val
            df['date'] = df['date'].apply(normalize_date)
            df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
            df = df.dropna(subset=['date'])  # 删除无法解析的日期行
            df.set_index('date', inplace=True)
            stock_name = df['name'].iloc[0] if not df['name'].empty else ''
            
            # 年线：按自然年最后一天（12-31）聚合
            annual_df = resample_ohlcv_to_period_ends(df, "annual")
            
            annual_df.dropna(subset=['open', 'close'], inplace=True)
            if annual_df.empty:
                return True

            annual_df['change_percent'] = annual_df['close'].pct_change(fill_method=None) * 100
            annual_df['change'] = annual_df['close'].diff()
            annual_df['pre_close'] = annual_df['close'].shift(1)
            annual_df['amplitude'] = (annual_df['high'] - annual_df['low']) / annual_df['pre_close'] * 100
            
            for date, row in annual_df.iterrows():
                try:
                    trade_date = date.strftime('%Y-%m-%d')
                    market = 'SZ' if stock_code.startswith('0') or stock_code.startswith('3') else 'SH'
                    ts_code = f"{stock_code}.{market}"
                    
                    data = {
                        'code': stock_code, 'ts_code': ts_code, 'name': stock_name, 'market': market,
                        'date': trade_date, 'open': float(row['open']), 'high': float(row['high']),
                        'low': float(row['low']), 'close': float(row['close']), 'volume': float(row['volume']),
                        'amount': float(row['amount']),
                        'change_percent': float(row['change_percent']) if pd.notna(row['change_percent']) else None,
                        'change': float(row['change']) if pd.notna(row['change']) else None,
                        'amplitude': float(row['amplitude']) if pd.notna(row['amplitude']) else None,
                        'turnover_rate': None, 'collected_source': 'generated_from_semiannual',
                        'collected_date': datetime.now().isoformat()
                    }
                    
                    self.session.execute(text("""
                        INSERT INTO annual_quotes
                        (code, ts_code, name, market, date, open, high, low, close, 
                         volume, amount, change_percent, change, amplitude, turnover_rate, 
                         collected_source, collected_date)
                        VALUES (:code, :ts_code, :name, :market, :date, :open, :high, :low, :close,
                                :volume, :amount, :change_percent, :change, :amplitude, :turnover_rate,
                                :collected_source, :collected_date)
                        ON CONFLICT(code, date) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
                        volume=excluded.volume, amount=excluded.amount, change_percent=excluded.change_percent,
                        change=excluded.change, amplitude=excluded.amplitude, collected_date=excluded.collected_date
                    """), data)
                    self.generated_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 年线数据失败: {e}")
                    continue
            
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"生成股票 {stock_code} 年线数据失败: {e}")
            self.failed_count += 1
            return False

    def generate_current_annual_data(self, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        try:
            today = datetime.now()
            year_start = datetime(today.year, 1, 1)
            start_date = (year_start - timedelta(days=365)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            
            logger.info(f"开始生成A股当前年线数据: 本年 {year_start.strftime('%Y-%m-%d')} 到今天 {end_date}")
            result = self.generate_annual_data(start_date, end_date, stock_codes)
            logger.info(f"A股当前年线数据生成完成: {result}")
            return result
        except Exception as e:
            logger.error(f"生成A股当前年线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

    def generate_annual_data(self, start_date: str, end_date: str, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        try:
            logger.info(f"开始生成A股年线数据: {start_date} 到 {end_date}")
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
            
            stocks = [{'code': code} for code in stock_codes] if stock_codes else self.get_stock_list()
            if not stocks:
                logger.error("没有找到需要处理的A股")
                return {'total': 0, 'success': 0, 'failed': 0}
            
            logger.info(f"准备处理 {len(stocks)} 只A股")
            self.generated_count = 0
            self.failed_count = 0
            
            success_count = 0
            for i, stock in enumerate(stocks, 1):
                if self.generate_single_stock_annual_data(stock['code'], query_start_date, end_date):
                    success_count += 1
                if i % 100 == 0:
                    logger.info(f"已处理 {i}/{len(stocks)} 只A股")
            
            result = {'total': len(stocks), 'success': success_count, 'failed': self.failed_count, 'generated_rows': self.generated_count}
            logger.info(f"A股年线数据生成完成: {result}")
            return result
        except Exception as e:
            logger.error(f"批量生成A股年线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

def main():
    import argparse
    parser = argparse.ArgumentParser(description='基于半年线数据生成A股年线数据')
    parser.add_argument('start_date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('end_date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--stocks', nargs='+', help='指定股票代码列表')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理前5只股票')
    args = parser.parse_args()
    
    generator = AnnualDataGenerator()
    try:
        if args.test:
            logger.info("测试模式：只处理前5只股票")
            stocks = generator.get_stock_list()[:5]
            stock_codes = [stock['code'] for stock in stocks]
        else:
            stock_codes = args.stocks
        generator.generate_annual_data(args.start_date, args.end_date, stock_codes)
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        sys.exit(1)
    finally:
        generator.session.close()

if __name__ == "__main__":
    main()
