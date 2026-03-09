#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股季线数据生成器
基于A股月线数据生成季线数据并保存到数据库
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from backend_core.database.db import SessionLocal
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quarterly_generation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QuarterlyDataGenerator:
    """A股季线数据生成器（基于月线数据累加）"""
    
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
                CREATE TABLE IF NOT EXISTS quarterly_quotes (
                    code TEXT,
                    ts_code TEXT,
                    name TEXT,
                    market TEXT,
                    date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    change_percent REAL,
                    change REAL,
                    amplitude REAL,
                    turnover_rate REAL,
                    collected_source TEXT,
                    collected_date TIMESTAMP,
                    PRIMARY KEY (code, date)
                )
            '''))
            self.session.commit()
            logger.info("A股季线数据表初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")

    def get_stock_list(self) -> List[Dict[str, str]]:
        try:
            result = self.session.execute(text("SELECT code, name FROM stock_basic_info ORDER BY code"))
            stocks = [{'code': row[0], 'name': row[1] if row[1] else ''} for row in result.fetchall()]
            logger.info(f"从数据库获取到 {len(stocks)} 只A股")
            return stocks
        except Exception as e:
            logger.error(f"获取A股列表失败: {e}")
            return []

    def generate_single_stock_quarterly_data(self, stock_code: str, start_date: str, end_date: str) -> bool:
        try:
            query = text("""
                SELECT date, open, high, low, close, volume, amount, name
                FROM monthly_quotes
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
            
            # 季线聚合 (QE 表示季度末)，name 取第一条
            quarterly_df = df.resample('QE').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'amount': 'sum',
                'name': 'first'
            })
            
            quarterly_df.dropna(subset=['open', 'close'], inplace=True)
            if quarterly_df.empty:
                return True

            quarterly_df['change_percent'] = quarterly_df['close'].pct_change(fill_method=None) * 100
            quarterly_df['change'] = quarterly_df['close'].diff()
            quarterly_df['pre_close'] = quarterly_df['close'].shift(1)
            quarterly_df['amplitude'] = (quarterly_df['high'] - quarterly_df['low']) / quarterly_df['pre_close'] * 100
            
            for date, row in quarterly_df.iterrows():
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
                        'turnover_rate': None, 'collected_source': 'generated_from_monthly',
                        'collected_date': datetime.now().isoformat()
                    }
                    
                    self.session.execute(text("""
                        INSERT INTO quarterly_quotes
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
                    logger.error(f"保存股票 {stock_code} 季线数据失败: {e}")
                    continue
            
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"生成股票 {stock_code} 季线数据失败: {e}")
            self.session.rollback()  # 回滚失败的事务，避免影响后续查询
            self.failed_count += 1
            return False

    def generate_current_quarter_data(self, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        try:
            today = datetime.now()
            quarter_start = datetime(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            start_date = (quarter_start - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            
            logger.info(f"开始生成A股当前季线数据: 本季度 {quarter_start.strftime('%Y-%m-%d')} 到今天 {end_date}")
            result = self.generate_quarterly_data(start_date, end_date, stock_codes)
            logger.info(f"A股当前季线数据生成完成: {result}")
            return result
        except Exception as e:
            logger.error(f"生成A股当前季线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

    def generate_quarterly_data(self, start_date: str, end_date: str, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        try:
            logger.info(f"开始生成A股季线数据: {start_date} 到 {end_date}")
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
            
            stocks = [{'code': code} for code in stock_codes] if stock_codes else self.get_stock_list()
            if not stocks:
                logger.error("没有找到需要处理的A股")
                return {'total': 0, 'success': 0, 'failed': 0}
            
            logger.info(f"准备处理 {len(stocks)} 只A股")
            self.generated_count = 0
            self.failed_count = 0
            
            success_count = 0
            for i, stock in enumerate(stocks, 1):
                if self.generate_single_stock_quarterly_data(stock['code'], query_start_date, end_date):
                    success_count += 1
                if i % 100 == 0:
                    logger.info(f"已处理 {i}/{len(stocks)} 只A股")
            
            result = {'total': len(stocks), 'success': success_count, 'failed': self.failed_count, 'generated_rows': self.generated_count}
            logger.info(f"A股季线数据生成完成: {result}")
            return result
        except Exception as e:
            logger.error(f"批量生成A股季线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

def main():
    import argparse
    parser = argparse.ArgumentParser(description='基于月线数据生成A股季线数据')
    parser.add_argument('start_date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('end_date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--stocks', nargs='+', help='指定股票代码列表')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理前5只股票')
    args = parser.parse_args()
    
    generator = QuarterlyDataGenerator()
    try:
        if args.test:
            logger.info("测试模式：只处理前5只股票")
            stocks = generator.get_stock_list()[:5]
            stock_codes = [stock['code'] for stock in stocks]
        else:
            stock_codes = args.stocks
        generator.generate_quarterly_data(args.start_date, args.end_date, stock_codes)
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        sys.exit(1)
    finally:
        generator.session.close()

if __name__ == "__main__":
    main()
