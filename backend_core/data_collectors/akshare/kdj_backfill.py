#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KDJ指标回溯计算批处理程序
用于批量计算所有股票的历史KDJ数据
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
from backend_core.utils.kdj_calculator import KDJCalculator
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kdj_backfill.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class KDJBackfillProcessor:
    """KDJ指标回溯计算处理器"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.calculator = KDJCalculator()
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
        """确保KDJ表存在"""
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS kdj_indicators (
                    code VARCHAR(20) NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL,
                    k REAL,
                    d REAL,
                    j REAL,
                    rsv REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
            '''))
            self.session.commit()
        except Exception as e:
            logger.warning(f"KDJ表初始化失败: {e}")
            self.session.rollback()
    
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
                    SELECT DISTINCT h.code
                    FROM historical_quotes h
                    JOIN stock_basic_info s ON CAST(s.code AS TEXT) = CAST(h.code AS TEXT)
                    WHERE COALESCE(s.collect_enabled, TRUE) = TRUE
                    ORDER BY code
                """))   
            elif market_type == 'HK':
                result = self.session.execute(text("""
                    SELECT DISTINCT h.code
                    FROM historical_quotes_hk h
                    JOIN stock_basic_info_hk s ON s.code = h.code
                    WHERE COALESCE(s.collect_enabled, TRUE) = TRUE
                    ORDER BY code
                """))
            
            stocks = [row[0] for row in result.fetchall()]
            logger.info(f"从数据库获取到 {len(stocks)} 只{market_type}股票")
            return stocks
            
        except Exception as e:
            logger.error(f"获取{market_type}股票列表失败: {e}")
            return []
    
    def get_historical_data(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[tuple]:
        """
        获取历史行情数据
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型（'CN' 或 'HK'）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            List[tuple]: (date, close, high, low) 列表，按日期升序排列
        """
        try:
            table_name = "historical_quotes" if market_type == 'CN' else "historical_quotes_hk"
            
            base_query = f"""
                SELECT date, close, high, low
                FROM {table_name}
                WHERE code = :code 
                AND close IS NOT NULL
                AND high IS NOT NULL
                AND low IS NOT NULL
            """
            
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
            rows = result.fetchall()
            return rows
            
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 历史数据失败: {e}")
            return []
    
    def check_existing_kdj(self, stock_code: str, market_type: str, date: str) -> bool:
        """
        检查KDJ数据是否已存在
        
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
                FROM kdj_indicators 
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
            logger.error(f"检查KDJ数据是否存在失败: {e}")
            return False
    
    def process_single_stock(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, skip_existing: bool = True) -> bool:
        """
        处理单只股票的KDJ计算
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型（'CN' 或 'HK'）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            skip_existing: 是否跳过已存在的数据
            
        Returns:
            bool: 是否成功
        """
        try:
            # 获取历史收盘价数据
            rows = self.get_historical_data(stock_code, market_type, start_date, end_date)
            
            if len(rows) < 9:
                logger.debug(f"股票 {stock_code} 历史数据不足9天，跳过KDJ计算")
                self.skipped_count += 1
                return True
            
            # 提取数据
            dates = []
            closes = []
            highs = []
            lows = []
            
            for row in rows:
                date_val = row[0]
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                    
                dates.append(date_str)
                closes.append(float(row[1]))
                highs.append(float(row[2]))
                lows.append(float(row[3]))
            
            # 批量计算KDJ
            kdj_results = self.calculator.calculate_kdj_batch(closes, highs, lows)
            
            if not kdj_results:
                logger.warning(f"股票 {stock_code} KDJ计算失败")
                self.failed_count += 1
                self.failed_stocks.append(f"{stock_code}: KDJ计算失败")
                return False
            
            # 保存KDJ数据
            saved_count = 0
            skipped_count = 0
            
            for i, kdj_data in enumerate(kdj_results):
                date_str = dates[i]
                
                # 检查是否已存在
                if skip_existing and self.check_existing_kdj(stock_code, market_type, date_str):
                    skipped_count += 1
                    continue
                
                try:
                    self.session.execute(text("""
                        INSERT INTO kdj_indicators
                        (code, date, market_type, k, d, j, rsv, created_at)
                        VALUES (:code, :date, :market_type, :k, :d, :j, :rsv, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            k = EXCLUDED.k,
                            d = EXCLUDED.d,
                            j = EXCLUDED.j,
                            rsv = EXCLUDED.rsv,
                            created_at = EXCLUDED.created_at
                    """), {
                        'code': stock_code,
                        'date': date_str,
                        'market_type': market_type,
                        'k': kdj_data['k'],
                        'd': kdj_data['d'],
                        'j': kdj_data['j'],
                        'rsv': kdj_data['rsv'],
                        'created_at': datetime.now()
                    })
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} KDJ数据失败: {e}")
                    continue
            
            if saved_count > 0:
                self.session.commit()
                self.processed_count += saved_count
                logger.info(f"股票 {stock_code} KDJ计算完成: 新增 {saved_count} 条，跳过 {skipped_count} 条")
            else:
                logger.debug(f"股票 {stock_code} KDJ数据已全部存在，跳过")
                self.skipped_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"处理股票 {stock_code} KDJ计算失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def process_batch(self, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, stock_codes: Optional[List[str]] = None, skip_existing: bool = True):
        """
        批量处理KDJ计算
        
        Args:
            market_type: 市场类型（'CN' 代表A股，'HK' 代表港股，'ALL' 代表全部）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            stock_codes: 指定股票代码列表（可选）
            skip_existing: 是否跳过已存在的数据
        """
        try:
            logger.info(f"开始批量计算KDJ指标: 市场={market_type}, 开始日期={start_date}, 结束日期={end_date}")
            
            # 重置计数器
            self.processed_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_stocks = []
            
            # 获取股票列表
            stocks_info = []
            
            if stock_codes:
                stocks_info = [(code, market_type if market_type != 'ALL' else 'CN') for code in stock_codes]
            elif market_type == 'ALL':
                stocks_a = self.get_stock_list('CN')
                stocks_hk = self.get_stock_list('HK')
                stocks_info = [(code, 'CN') for code in stocks_a] + [(code, 'HK') for code in stocks_hk]
            else:
                stocks = self.get_stock_list(market_type)
                stocks_info = [(code, market_type) for code in stocks]
            
            if not stocks_info:
                logger.error("没有找到需要处理的股票")
                return
            
            logger.info(f"准备处理 {len(stocks_info)} 只股票的KDJ数据")
            
            # 批量处理
            for i, (stock_code, m_type) in enumerate(stocks_info):
                logger.info(f"进度: {i+1}/{len(stocks_info)} - 处理股票 {stock_code} ({m_type})")
                
                self.process_single_stock(stock_code, m_type, start_date, end_date, skip_existing)
                
                # 每处理10只股票输出一次进度
                if (i + 1) % 10 == 0:
                    logger.info(f"已处理 {i+1}/{len(stocks_info)} 只股票，新增 {self.processed_count} 条，跳过 {self.skipped_count} 条，失败 {self.failed_count} 只")
            
            # 输出最终统计
            logger.info(f"批量KDJ计算完成:")
            logger.info(f"  - 总计股票: {len(stocks_info)}")
            logger.info(f"  - 新增数据: {self.processed_count} 条")
            logger.info(f"  - 跳过数据: {self.skipped_count} 条")
            logger.info(f"  - 失败股票: {self.failed_count} 只")
            if self.failed_stocks:
                logger.warning("失败详情:")
                for detail in self.failed_stocks[:10]:  # 只显示前10个
                    logger.warning(f"  - {detail}")
                    
        except Exception as e:
            logger.error(f"批量KDJ计算失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='KDJ指标回溯计算批处理程序')
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
    processor = KDJBackfillProcessor()
    
    try:
        # 执行处理
        stock_codes = [args.code] if args.code else None
        
        if args.test:
            logger.info("测试模式：只处理前5只股票")
            if args.market == 'ALL':
                stocks_a = processor.get_stock_list('CN')[:3]
                stocks_hk = processor.get_stock_list('HK')[:2]
                stock_codes = stocks_a + stocks_hk
                # 注意：这里如果指定Code，process_batch里面会假设market_type，
                # 但这里我传入的stock_codes只是代码列表。
                # 所以上面的 process_batch 逻辑里，如果 market_type='ALL' 而 stock_codes 有值，会默认使用 'CN'。
                # 为了简化，测试模式下我们直接调用 process_batch 不传 stock_codes，而是靠内部截断？
                # 不，process_batch 内部逻辑是：如果有 stock_codes，就只处理这些。
                # 如果 market_type 是 ALL，且没有 stock_codes，它会自己去取列表。
                # 如果 market is ALL 和 stock_codes 都有...?
                # 我上面的逻辑是：
                # if stock_codes: loop stocks_info = [(code, market_type if market_type != 'ALL' else 'CN')]
                # 这在 --test 模式下对 ALL 市场有问题，因为它会把 HK 代码当成 CN 代码（如果传了 ALL）。
                
                # 让我们修正一下调用逻辑，直接传入 None 给 stock_codes，但在 process_batch 内部做截断
                # 或者简单点，分别调用
                pass
            
        
        # 简单起见，如果是测试模式，且 ALL，手动分两次调用或者修改 process_batch
        # 但因为我已经写了 process_batch，我不想改得太复杂。
        # 让 --test 仅仅作为 flag 传给 process_batch? 不，process_batch 没有 test 参数。
        # 
        # 让我们修改 main 函数中的逻辑来适配：
        if args.test and args.market == 'ALL':
             # 这种情况下，不如分别跑
             logger.info("测试模式：分别运行 CN 和 HK")
             processor.process_batch('CN', args.start_date, args.end_date, processor.get_stock_list('CN')[:3], not args.no_skip)
             processor.process_batch('HK', args.start_date, args.end_date, processor.get_stock_list('HK')[:3], not args.no_skip)
        elif args.test:
             # 指定了市场
             stocks = processor.get_stock_list(args.market)[:5]
             processor.process_batch(args.market, args.start_date, args.end_date, stocks, not args.no_skip)
        else:
             # 正常模式
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
