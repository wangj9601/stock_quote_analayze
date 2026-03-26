#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOLL指标回溯计算批处理程序
用于批量计算所有股票的历史BOLL数据 (20, 2)
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import logging
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.utils.boll_calculator import BOLLCalculator
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('boll_backfill.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BOLLBackfillProcessor:
    """BOLL指标回溯计算处理器"""
    
    def __init__(self, window: int = 20, k: int = 2):
        """
        初始化处理器
        """
        self.session = SessionLocal()
        self.calculator = BOLLCalculator(window, k)
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_stocks = []
        self._ensure_table_exists()
        
    def __del__(self):
        """析构函数，确保session被关闭"""
        if hasattr(self, 'session'):
            self.session.close()

    def _ensure_table_exists(self):
        """确保BOLL表存在"""
        try:
            # 尝试从 SQLAlchemy 模型创建表是不够的，如果直接用 SQL
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS boll_indicators (
                    code VARCHAR(20) NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL,
                    mid REAL,
                    upper REAL,
                    lower REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
            '''))
            self.session.commit()
        except Exception as e:
            logger.warning(f"BOLL表初始化失败: {e}")
            self.session.rollback()
    
    def get_stock_list(self, market_type: str) -> List[str]:
        """获取股票代码列表"""
        try:
            if market_type == 'CN':
                result = self.session.execute(text("""
                    SELECT DISTINCT h.code
                    FROM historical_quotes h
                    JOIN stock_basic_info s ON CAST(s.code AS TEXT) = CAST(h.code AS TEXT)
                    WHERE COALESCE(s.collect_enabled, TRUE) = TRUE
                    ORDER BY h.code
                """))
            elif market_type == 'HK':
                result = self.session.execute(text("""
                    SELECT DISTINCT h.code
                    FROM historical_quotes_hk h
                    JOIN stock_basic_info_hk s ON s.code = h.code
                    WHERE COALESCE(s.collect_enabled, TRUE) = TRUE
                    ORDER BY h.code
                """))
            else:
                return []
            
            stocks = [row[0] for row in result.fetchall()]
            logger.info(f"从数据库获取到 {len(stocks)} 只{market_type}股票")
            return stocks
        except Exception as e:
            logger.error(f"获取{market_type}股票列表失败: {e}")
            return []
    
    def get_historical_data(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[tuple]:
        """获取历史行情数据"""
        try:
            table_name = "historical_quotes" if market_type == 'CN' else "historical_quotes_hk"
            base_query = f"SELECT date, close FROM {table_name} WHERE code = :code AND close IS NOT NULL"
            params = {'code': stock_code}
            
            conditions = []
            if start_date:
                conditions.append("date >= :start_date")
                params['start_date'] = start_date
            if end_date:
                conditions.append("date <= :end_date")
                params['end_date'] = end_date
                
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            base_query += " ORDER BY date ASC"
            
            result = self.session.execute(text(base_query), params)
            return result.fetchall()
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 历史数据失败: {e}")
            return []
    
    def check_existing_boll(self, stock_code: str, market_type: str, date: str) -> bool:
        """检查BOLL数据是否已存在"""
        try:
            result = self.session.execute(text("""
                SELECT COUNT(*) FROM boll_indicators 
                WHERE code = :code AND market_type = :market_type AND date = :date
            """), {'code': stock_code, 'market_type': market_type, 'date': date})
            return result.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"检查BOLL数据是否存在失败: {e}")
            return False
    
    def process_single_stock(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, skip_existing: bool = True) -> bool:
        """处理单只股票的BOLL计算"""
        try:
            rows = self.get_historical_data(stock_code, market_type, start_date, end_date)
            if len(rows) < self.calculator.window:
                logger.debug(f"股票 {stock_code} 历史数据不足{self.calculator.window}天，跳过BOLL计算")
                self.skipped_count += 1
                return True
            
            dates = []
            closes = []
            for row in rows:
                date_val = row[0]
                date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, datetime) else str(date_val)
                dates.append(date_str)
                closes.append(float(row[1]))
            
            boll_results = self.calculator.calculate_boll_batch(closes)
            if not boll_results:
                self.failed_count += 1
                return False
            
            saved_count = 0
            skipped_count = 0
            for i, boll_data in enumerate(boll_results):
                if boll_data['mid'] is None: continue
                date_str = dates[i]
                # we rely on ON CONFLICT in the execute call below instead of checking individually
                
                try:
                    self.session.execute(text("""
                        INSERT INTO boll_indicators (code, date, market_type, mid, upper, lower, created_at)
                        VALUES (:code, :date, :market_type, :mid, :upper, :lower, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            mid = EXCLUDED.mid, upper = EXCLUDED.upper, lower = EXCLUDED.lower,
                            created_at = EXCLUDED.created_at
                    """), {
                        'code': stock_code, 'date': date_str, 'market_type': market_type,
                        'mid': boll_data['mid'], 'upper': boll_data['upper'], 'lower': boll_data['lower'],
                        'created_at': datetime.now()
                    })
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} BOLL数据失败: {e}")
            
            if saved_count > 0:
                self.session.commit()
                self.processed_count += saved_count
                logger.info(f"股票 {stock_code} BOLL计算完成: 新增 {saved_count} 条，跳过 {skipped_count} 条")
            else:
                self.skipped_count += 1
            return True
        except Exception as e:
            logger.error(f"处理股票 {stock_code} BOLL计算失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def process_batch(self, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, stock_codes: Optional[List[str]] = None, skip_existing: bool = True):
        """批量处理BOLL计算"""
        try:
            logger.info(f"开始批量计算BOLL指标: 市场={market_type}, 开始日期={start_date}, 结束日期={end_date}")
            self.processed_count = 0; self.skipped_count = 0; self.failed_count = 0; self.failed_stocks = []
            
            stocks_info = []
            if stock_codes:
                stocks_info = [(code, market_type if market_type != 'ALL' else 'CN') for code in stock_codes]
            elif market_type == 'ALL':
                stocks_a = self.get_stock_list('CN'); stocks_hk = self.get_stock_list('HK')
                stocks_info = [(code, 'CN') for code in stocks_a] + [(code, 'HK') for code in stocks_hk]
            else:
                stocks = self.get_stock_list(market_type)
                stocks_info = [(code, market_type) for code in stocks]
            
            if not stocks_info:
                logger.error("没有找到需要处理的股票")
                return
            
            logger.info(f"准备处理 {len(stocks_info)} 只股票的BOLL数据")
            for i, (stock_code, m_type) in enumerate(stocks_info):
                self.process_single_stock(stock_code, m_type, start_date, end_date, skip_existing)
                if (i + 1) % 10 == 0:
                    logger.info(f"进度: {i+1}/{len(stocks_info)} - 已增 {self.processed_count}, 跳过 {self.skipped_count}, 失败 {self.failed_count}")
            
            logger.info(f"批量BOLL计算完成: 总计={len(stocks_info)}, 新增={self.processed_count}, 跳过={self.skipped_count}, 失败={self.failed_count}")
        except Exception as e:
            logger.error(f"批量BOLL计算失败: {e}")

def main():
    parser = argparse.ArgumentParser(description='BOLL指标回溯计算批处理程序')
    parser.add_argument('--market', choices=['CN', 'HK', 'ALL'], default='ALL', help='市场类型')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--code', help='指定股票代码')
    parser.add_argument('--no-skip', action='store_true', help='强制重新计算')
    parser.add_argument('--test', action='store_true', help='测试模式')
    args = parser.parse_args()
    
    processor = BOLLBackfillProcessor()
    try:
        stock_codes = [args.code] if args.code else None
        if args.test:
             if args.market == 'ALL':
                 processor.process_batch('CN', args.start_date, args.end_date, processor.get_stock_list('CN')[:3], not args.no_skip)
                 processor.process_batch('HK', args.start_date, args.end_date, processor.get_stock_list('HK')[:3], not args.no_skip)
             else:
                 stocks = processor.get_stock_list(args.market)[:5]
                 processor.process_batch(args.market, args.start_date, args.end_date, stocks, not args.no_skip)
        else:
             processor.process_batch(args.market, args.start_date, args.end_date, stock_codes, not args.no_skip)
    finally:
        processor.session.close()

if __name__ == "__main__":
    main()
