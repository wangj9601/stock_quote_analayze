#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股月线数据生成器
基于A股日线数据生成月线数据并保存到数据库
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from backend_core.database.db import SessionLocal
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monthly_generation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MonthlyDataGenerator:
    """A股月线数据生成器"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.generated_count = 0
        self.failed_count = 0
        self._init_db()

    def __del__(self):
        """析构函数，确保session被关闭"""
        if hasattr(self, 'session'):
            self.session.close()

    def _init_db(self):
        """初始化数据库表结构"""
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS monthly_quotes (
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
            logger.info("A股月线数据表初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")

    def get_stock_list(self) -> List[Dict[str, str]]:
        """从stock_basic_info表获取A股列表"""
        try:
            result = self.session.execute(text("""
                SELECT code, name 
                FROM stock_basic_info 
                ORDER BY code
            """))
            
            stocks = []
            for row in result.fetchall():
                stocks.append({
                    'code': row[0],
                    'name': row[1] if row[1] else ''
                })
            
            logger.info(f"从数据库获取到 {len(stocks)} 只A股")
            return stocks
        except Exception as e:
            logger.error(f"获取A股列表失败: {e}")
            return []

    def generate_single_stock_monthly_data(self, stock_code: str, start_date: str, end_date: str) -> bool:
        """
        生成单只股票的月线数据
        """
        try:
            # 1. 获取日线数据
            query = text("""
                SELECT date, open, high, low, close, volume, amount, name
                FROM historical_quotes
                WHERE code = :code AND date >= :start_date AND date <= :end_date
                ORDER BY date ASC
            """)
            
            result = self.session.execute(query, {
                'code': stock_code,
                'start_date': start_date,
                'end_date': end_date
            })
            
            rows = result.fetchall()
            if not rows:
                return True
                
            # 转换为DataFrame
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
            
            # 获取股票名称
            stock_name = df['name'].iloc[0] if not df['name'].empty else ''
            
            # 2. 重采样为月线 (ME 表示月末)
            monthly_df = df.resample('ME').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'amount': 'sum'
            })
            
            # 去除无效行
            monthly_df.dropna(subset=['open', 'close'], inplace=True)
            
            if monthly_df.empty:
                return True

            # 3. 计算技术指标
            monthly_df['change_percent'] = monthly_df['close'].pct_change(fill_method=None) * 100
            monthly_df['change'] = monthly_df['close'].diff()
            monthly_df['pre_close'] = monthly_df['close'].shift(1)
            monthly_df['amplitude'] = (monthly_df['high'] - monthly_df['low']) / monthly_df['pre_close'] * 100
            
            # 4. 保存数据
            for date, row in monthly_df.iterrows():
                try:
                    trade_date = date.strftime('%Y-%m-%d')
                    market = 'SZ' if stock_code.startswith('0') or stock_code.startswith('3') else 'SH'
                    ts_code = f"{stock_code}.{market}"
                    
                    data = {
                        'code': stock_code,
                        'ts_code': ts_code,
                        'name': stock_name,
                        'market': market,
                        'date': trade_date,
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']),
                        'amount': float(row['amount']),
                        'change_percent': float(row['change_percent']) if pd.notna(row['change_percent']) else None,
                        'change': float(row['change']) if pd.notna(row['change']) else None,
                        'amplitude': float(row['amplitude']) if pd.notna(row['amplitude']) else None,
                        'turnover_rate': None,
                        'collected_source': 'generated_from_daily',
                        'collected_date': datetime.now().isoformat()
                    }
                    
                    self.session.execute(text("""
                        INSERT INTO monthly_quotes
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
                    logger.error(f"保存股票 {stock_code} 月线数据失败: {e}")
                    continue
            
            self.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"生成股票 {stock_code} 月线数据失败: {e}")
            self.session.rollback()  # 回滚失败的事务，避免影响后续查询
            self.failed_count += 1
            return False

    def generate_current_month_data(self, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        """
        生成当前月的月线数据（每日更新模式）
        计算本月1号到今天的数据，覆盖写入
        """
        try:
            today = datetime.now()
            
            # 计算本月1号
            first_day = today.replace(day=1)
            
            # 为了计算涨跌幅，需要获取上月的数据
            # 向前扩展60天确保能获取到上月收盘价
            start_date = (first_day - timedelta(days=60)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            
            logger.info(f"开始生成A股当前月线数据: 本月1号 {first_day.strftime('%Y-%m-%d')} 到今天 {end_date}")
            
            # 调用通用生成方法
            result = self.generate_monthly_data(start_date, end_date, stock_codes)
            
            logger.info(f"A股当前月线数据生成完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"生成A股当前月线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

    def generate_monthly_data(self, start_date: str, end_date: str, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        """批量生成A股月线数据"""
        try:
            logger.info(f"开始生成A股月线数据: {start_date} 到 {end_date}")
            
            # 为了计算涨跌幅，自动向前多取60天的数据
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            
            if stock_codes:
                stocks = [{'code': code} for code in stock_codes]
            else:
                stocks = self.get_stock_list()
            
            if not stocks:
                logger.error("没有找到需要处理的A股")
                return {'total': 0, 'success': 0, 'failed': 0}
            
            logger.info(f"准备处理 {len(stocks)} 只A股")
            
            self.generated_count = 0
            self.failed_count = 0
            
            success_count = 0
            for i, stock in enumerate(stocks, 1):
                if self.generate_single_stock_monthly_data(stock['code'], query_start_date, end_date):
                    success_count += 1
                
                if i % 100 == 0:
                    logger.info(f"已处理 {i}/{len(stocks)} 只A股")
            
            self._log_operation_result(start_date, end_date, len(stocks), success_count)
            
            result = {
                'total': len(stocks),
                'success': success_count,
                'failed': self.failed_count,
                'generated_rows': self.generated_count
            }
            
            logger.info(f"A股月线数据生成完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"批量生成A股月线数据失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 1}

    def _log_operation_result(self, start_date: str, end_date: str, total_stocks: int, success_stocks: int):
        """记录操作日志"""
        try:
            self.session.execute(text("""
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
            """), {
                'operation_type': 'generate_monthly_from_daily',
                'operation_desc': f'生成日期范围: {start_date} 到 {end_date}\n总计A股: {total_stocks}\n成功处理: {success_stocks}\n生成记录: {self.generated_count}',
                'affected_rows': self.generated_count,
                'status': 'success' if self.failed_count == 0 else 'partial_success',
                'error_message': None,
                'collect_source': 'akshare'
            })
            self.session.commit()
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='基于日线数据生成A股月线数据')
    parser.add_argument('start_date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('end_date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--stocks', nargs='+', help='指定股票代码列表')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理前5只股票')
    
    args = parser.parse_args()
    
    generator = MonthlyDataGenerator()
    
    try:
        if args.test:
            logger.info("测试模式：只处理前5只股票")
            stocks = generator.get_stock_list()[:5]
            stock_codes = [stock['code'] for stock in stocks]
        else:
            stock_codes = args.stocks
        
        generator.generate_monthly_data(args.start_date, args.end_date, stock_codes)
        
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        sys.exit(1)
    finally:
        generator.session.close()

if __name__ == "__main__":
    main()
