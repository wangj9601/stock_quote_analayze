#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD指标回溯计算批处理程序
用于批量计算所有股票的历史MACD数据
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.utils.macd_calculator import MACDCalculator
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('macd_backfill.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MACDBackfillProcessor:
    """MACD指标回溯计算处理器"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.calculator = MACDCalculator()
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
        
        Args:
            market_type: 市场类型（'CN' 或 'HK'）
            
        Returns:
            List[str]: 股票代码列表
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
    
    def get_historical_closes(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[tuple]:
        """
        获取历史收盘价数据
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型（'CN' 或 'HK'）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            List[tuple]: (date, close) 列表，按日期升序排列
        """
        try:
            if market_type == 'CN':
                query = text("""
                    SELECT date, close 
                    FROM historical_quotes 
                    WHERE code = :code 
                    AND close IS NOT NULL
                """)
                params = {'code': stock_code}
                
                if start_date:
                    query = text("""
                        SELECT date, close 
                        FROM historical_quotes 
                        WHERE code = :code 
                        AND date >= :start_date
                        AND close IS NOT NULL
                    """)
                    params['start_date'] = start_date
                
                if end_date:
                    if start_date:
                        query = text("""
                            SELECT date, close 
                            FROM historical_quotes 
                            WHERE code = :code 
                            AND date >= :start_date
                            AND date <= :end_date
                            AND close IS NOT NULL
                        """)
                    else:
                        query = text("""
                            SELECT date, close 
                            FROM historical_quotes 
                            WHERE code = :code 
                            AND date <= :end_date
                            AND close IS NOT NULL
                        """)
                    params['end_date'] = end_date
                
                query = text(str(query) + " ORDER BY date ASC")
            elif market_type == 'HK':
                query = text("""
                    SELECT date, close 
                    FROM historical_quotes_hk 
                    WHERE code = :code 
                    AND close IS NOT NULL
                """)
                params = {'code': stock_code}
                
                if start_date:
                    query = text("""
                        SELECT date, close 
                        FROM historical_quotes_hk 
                        WHERE code = :code 
                        AND date >= :start_date
                        AND close IS NOT NULL
                    """)
                    params['start_date'] = start_date
                
                if end_date:
                    if start_date:
                        query = text("""
                            SELECT date, close 
                            FROM historical_quotes_hk 
                            WHERE code = :code 
                            AND date >= :start_date
                            AND date <= :end_date
                            AND close IS NOT NULL
                        """)
                    else:
                        query = text("""
                            SELECT date, close 
                            FROM historical_quotes_hk 
                            WHERE code = :code 
                            AND date <= :end_date
                            AND close IS NOT NULL
                        """)
                    params['end_date'] = end_date
                
                query = text(str(query) + " ORDER BY date ASC")
            
            result = self.session.execute(query, params)
            rows = result.fetchall()
            return rows
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 历史收盘价失败: {e}")
            return []
    
    def check_existing_macd(self, stock_code: str, market_type: str, date: str) -> bool:
        """
        检查MACD数据是否已存在
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型
            date: 日期
            
        Returns:
            bool: 是否存在
        """
        try:
            result = self.session.execute(text("""
                SELECT COUNT(*) 
                FROM macd_indicators 
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
            logger.error(f"检查MACD数据是否存在失败: {e}")
            return False
    
    def process_single_stock(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, skip_existing: bool = True) -> bool:
        """
        处理单只股票的MACD计算
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型（'A股' 或 '港股'）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            skip_existing: 是否跳过已存在的数据
            
        Returns:
            bool: 是否成功
        """
        try:
            # 获取历史收盘价数据
            rows = self.get_historical_closes(stock_code, market_type, start_date, end_date)
            
            if len(rows) < 26:
                logger.debug(f"股票 {stock_code} 历史数据不足26天，跳过MACD计算")
                self.skipped_count += 1
                return True
            
            # 提取收盘价和日期
            dates = []
            closes = []
            for row in rows:
                date_val = row[0]
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                dates.append(date_str)
                closes.append(float(row[1]))
            
            # 批量计算MACD
            macd_results = self.calculator.calculate_macd_batch(closes)
            
            if not macd_results:
                logger.warning(f"股票 {stock_code} MACD计算失败")
                self.failed_count += 1
                self.failed_stocks.append(f"{stock_code}: MACD计算失败")
                return False
            
            # 保存MACD数据
            saved_count = 0
            skipped_count = 0
            
            for i, macd_data in enumerate(macd_results):
                if macd_data['dif'] is None:
                    continue
                
                date_str = dates[i]
                
                # 检查是否已存在
                if skip_existing and self.check_existing_macd(stock_code, market_type, date_str):
                    skipped_count += 1
                    continue
                
                try:
                    self.session.execute(text("""
                        INSERT INTO macd_indicators
                        (code, date, market_type, dif, dea, macd, ema12, ema26, created_at)
                        VALUES (:code, :date, :market_type, :dif, :dea, :macd, :ema12, :ema26, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            dif = EXCLUDED.dif,
                            dea = EXCLUDED.dea,
                            macd = EXCLUDED.macd,
                            ema12 = EXCLUDED.ema12,
                            ema26 = EXCLUDED.ema26,
                            created_at = EXCLUDED.created_at
                    """), {
                        'code': stock_code,
                        'date': date_str,
                        'market_type': market_type,
                        'dif': macd_data['dif'],
                        'dea': macd_data['dea'],
                        'macd': macd_data['macd'],
                        'ema12': macd_data['ema12'],
                        'ema26': macd_data['ema26'],
                        'created_at': datetime.now()
                    })
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} MACD数据失败: {e}")
                    continue
            
            if saved_count > 0:
                self.session.commit()
                self.processed_count += saved_count
                logger.info(f"股票 {stock_code} MACD计算完成: 新增 {saved_count} 条，跳过 {skipped_count} 条")
            else:
                logger.debug(f"股票 {stock_code} MACD数据已全部存在，跳过")
                self.skipped_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"处理股票 {stock_code} MACD计算失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def process_batch(self, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, stock_codes: Optional[List[str]] = None, skip_existing: bool = True):
        """
        批量处理MACD计算
        
        Args:
            market_type: 市场类型（'CN' 代表A股，'HK' 代表港股，'ALL' 代表全部）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            stock_codes: 指定股票代码列表（可选）
            skip_existing: 是否跳过已存在的数据
        """
        try:
            logger.info(f"开始批量计算MACD指标: 市场={market_type}, 开始日期={start_date}, 结束日期={end_date}")
            
            # 重置计数器
            self.processed_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_stocks = []
            
            # 获取股票列表
            if stock_codes:
                stocks = stock_codes
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
            
            logger.info(f"准备处理 {len(stocks)} 只股票的MACD数据")
            
            # 批量处理
            for i, stock_code in enumerate(stocks):
                if market_type == 'ALL':
                    current_market_type = market_types[i]
                else:
                    current_market_type = market_type
                
                logger.info(f"进度: {i+1}/{len(stocks)} - 处理股票 {stock_code} ({current_market_type})")
                
                self.process_single_stock(stock_code, current_market_type, start_date, end_date, skip_existing)
                
                # 每处理10只股票输出一次进度
                if (i + 1) % 10 == 0:
                    logger.info(f"已处理 {i+1}/{len(stocks)} 只股票，新增 {self.processed_count} 条，跳过 {self.skipped_count} 条，失败 {self.failed_count} 只")
            
            # 输出最终统计
            logger.info(f"批量MACD计算完成:")
            logger.info(f"  - 总计股票: {len(stocks)}")
            logger.info(f"  - 新增数据: {self.processed_count} 条")
            logger.info(f"  - 跳过数据: {self.skipped_count} 条")
            logger.info(f"  - 失败股票: {self.failed_count} 只")
            if self.failed_stocks:
                logger.warning("失败详情:")
                for detail in self.failed_stocks[:10]:  # 只显示前10个
                    logger.warning(f"  - {detail}")
                    
        except Exception as e:
            logger.error(f"批量MACD计算失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MACD指标回溯计算批处理程序')
    parser.add_argument('--market', choices=['CN', 'HK', 'ALL'], default='ALL', help='市场类型（默认：全部）')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--code', help='指定股票代码（可选，只处理该股票）')
    parser.add_argument('--no-skip', action='store_true', help='不跳过已存在的数据（强制重新计算）')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理前5只股票')
    
    args = parser.parse_args()
    
    # 验证日期格式
    if args.start_date:
        try:
            datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            logger.error("开始日期格式错误，请使用 YYYY-MM-DD 格式")
            sys.exit(1)
    
    if args.end_date:
        try:
            datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            logger.error("结束日期格式错误，请使用 YYYY-MM-DD 格式")
            sys.exit(1)
    
    # 创建处理器
    processor = MACDBackfillProcessor()
    
    try:
        # 执行处理
        stock_codes = [args.code] if args.code else None
        
        if args.test:
            logger.info("测试模式：只处理前5只股票")
            if args.market == 'ALL':
                stocks_a = processor.get_stock_list('CN')[:3]
                stocks_hk = processor.get_stock_list('HK')[:2]
                stock_codes = stocks_a + stocks_hk
            else:
                stocks = processor.get_stock_list(args.market)[:5]
                stock_codes = stocks
        
        processor.process_batch(
            market_type=args.market,
            start_date=args.start_date,
            end_date=args.end_date,
            stock_codes=stock_codes,
            skip_existing=not args.no_skip
        )
        
    except KeyboardInterrupt:
        logger.info("用户中断处理")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        processor.session.close()


if __name__ == "__main__":
    main()

