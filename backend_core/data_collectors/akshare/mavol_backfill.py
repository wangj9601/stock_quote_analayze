#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVOL指标回溯计算批处理程序
用于批量计算所有股票的历史MAVOL数据（MAVOL5, MAVOL10, MAVOL20, MAVOL30, MAVOL60, MAVOL120, MAVOL200）
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import logging
import argparse
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.utils.mavol_calculator import MAVOLCalculator
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mavol_backfill.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MAVOLBackfillProcessor:
    """MAVOL指标回溯计算处理器"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_stocks = []
        
    def __del__(self):
        """析构函数，确保session被关闭"""
        if hasattr(self, 'session'):
            self.session.close()
    
    def get_stock_list(self, market_type: str) -> List[str]:
        """
        获取股票代码列表
        """
        try:
            if market_type == 'CN':
                result = self.session.execute(text("""
                    SELECT DISTINCT code 
                    FROM historical_quotes 
                    ORDER BY code
                """))   
            elif market_type == 'HK':
                result = self.session.execute(text("""
                    SELECT DISTINCT code 
                    FROM historical_quotes_hk 
                    ORDER BY code
                """))
            
            stocks = [row[0] for row in result.fetchall()]
            logger.info(f"从数据库获取到 {len(stocks)} 只{market_type}股票")
            return stocks
            
        except Exception as e:
            logger.error(f"获取{market_type}股票列表失败: {e}")
            return []
    
    def get_historical_volumes(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[tuple]:
        """
        获取历史成交量数据
        """
        try:
            table = "historical_quotes" if market_type in ['CN', 'A股'] else "historical_quotes_hk"
            
            query_str = f"SELECT date, volume FROM {table} WHERE code = :code AND volume IS NOT NULL"
            params = {'code': stock_code}
            
            if start_date:
                query_str += " AND date >= :start_date"
                params['start_date'] = start_date
            
            if end_date:
                query_str += " AND date <= :end_date"
                params['end_date'] = end_date
                
            query_str += " ORDER BY date ASC"
            
            result = self.session.execute(text(query_str), params)
            rows = result.fetchall()
            return rows
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 历史成交量失败: {e}")
            return []
    
    def check_existing_mavol(self, stock_code: str, market_type: str, date: str) -> bool:
        """
        检查MAVOL数据是否已存在
        """
        try:
            result = self.session.execute(text("""
                SELECT COUNT(*) 
                FROM mavol_indicators 
                WHERE code = :code 
                AND market_type = :market_type 
                AND date = :date
            """), {
                'code': stock_code,
                'market_type': market_type,
                'date': date
            })
            count = result.fetchone()[0]
            return count > 0
        except Exception as e:
            logger.error(f"检查MAVOL数据是否存在失败: {e}")
            return False
    
    def process_single_stock(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, skip_existing: bool = True) -> bool:
        """
        处理单只股票的MAVOL计算
        """
        try:
            rows = self.get_historical_volumes(stock_code, market_type, start_date, end_date)
            
            if len(rows) < 5:
                # logger.debug(f"股票 {stock_code} 历史数据不足5天，跳过MAVOL计算")
                self.skipped_count += 1
                return True
            
            # 构建DataFrame
            df_data = []
            for row in rows:
                date_val = row[0]
                vol_val = row[1]
                
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                
                df_data.append({
                    'date': date_str,
                    'volume': float(vol_val) if vol_val else None
                })
            
            df = pd.DataFrame(df_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.dropna(subset=['date', 'volume'])
            df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
            
            if len(df) == 0:
                self.skipped_count += 1
                return True
            
            # 计算MAVOL指标
            mavol_df = MAVOLCalculator.calculate_mavol_for_dataframe(df)
            
            # 保存MAVOL数据
            saved_count = 0
            skipped_in_stock = 0
            
            for _, row in mavol_df.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                
                if skip_existing and self.check_existing_mavol(stock_code, market_type, date_str):
                    skipped_in_stock += 1
                    continue
                
                try:
                    self.session.execute(text("""
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
                    """), {
                        'code': stock_code,
                        'date': date_str,
                        'market_type': market_type,
                        'mavol5': self._safe_value(row.get('mavol5')),
                        'mavol10': self._safe_value(row.get('mavol10')),
                        'mavol20': self._safe_value(row.get('mavol20')),
                        'mavol30': self._safe_value(row.get('mavol30')),
                        'mavol60': self._safe_value(row.get('mavol60')),
                        'mavol120': self._safe_value(row.get('mavol120')),
                        'mavol200': self._safe_value(row.get('mavol200')),
                        'created_at': datetime.now()
                    })
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} MAVOL数据失败: {e}")
                    continue
            
            if saved_count > 0:
                self.session.commit()
                self.processed_count += saved_count
                logger.info(f"股票 {stock_code} MAVOL计算完成: 新增 {saved_count} 条，跳过 {skipped_in_stock} 条")
            else:
                self.skipped_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"处理股票 {stock_code} MAVOL计算失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def _safe_value(self, val) -> Optional[float]:
        if val is None or pd.isna(val):
            return None
        return float(val)
    
    def process_batch(self, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, stock_codes: Optional[List[str]] = None, skip_existing: bool = True):
        try:
            logger.info(f"开始批量计算MAVOL指标: 市场={market_type}, 开始日期={start_date}, 结束日期={end_date}")
            
            if stock_codes:
                stocks = stock_codes
                market_types = [market_type] * len(stocks) # Simplified for batch
            elif market_type == 'ALL':
                stocks_a = self.get_stock_list('CN')
                stocks_hk = self.get_stock_list('HK')
                stocks = stocks_a + stocks_hk
                market_types = ['CN'] * len(stocks_a) + ['HK'] * len(stocks_hk)
            else:
                stocks = self.get_stock_list(market_type)
                market_types = [market_type] * len(stocks)
            
            if not stocks:
                logger.error("没有找到需要处理的股票")
                return
            
            for i, stock_code in enumerate(stocks):
                curr_market = market_types[i]
                logger.info(f"进度: {i+1}/{len(stocks)} - 处理股票 {stock_code} ({curr_market})")
                self.process_single_stock(stock_code, curr_market, start_date, end_date, skip_existing)
                
            logger.info(f"批量MAVOL计算完成: 新增 {self.processed_count} 条，跳过 {self.skipped_count} 只股票，失败 {self.failed_count} 只")
                    
        except Exception as e:
            logger.error(f"批量MAVOL计算失败: {e}")

def main():
    parser = argparse.ArgumentParser(description='MAVOL指标回溯计算批处理程序')
    parser.add_argument('--market', choices=['CN', 'HK', 'ALL'], default='ALL', help='市场类型')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--code', help='指定股票代码')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已存在的数据')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理前5只股票')
    
    args = parser.parse_args()
    processor = MAVOLBackfillProcessor()
    
    try:
        stock_codes = [args.code] if args.code else None
        if args.test:
            if args.market == 'ALL':
                stock_codes = processor.get_stock_list('CN')[:3] + processor.get_stock_list('HK')[:2]
            else:
                stock_codes = processor.get_stock_list(args.market)[:5]
        
        processor.process_batch(
            market_type=args.market,
            start_date=args.start_date,
            end_date=args.end_date,
            stock_codes=stock_codes,
            skip_existing=not args.no_skip
        )
    finally:
        processor.session.close()

if __name__ == "__main__":
    main()
