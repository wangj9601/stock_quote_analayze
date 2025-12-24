#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA指标回溯计算批处理程序
用于批量计算所有股票的历史MA数据（MA5, MA10, MA20, MA30, MA60, MA120, MA200）
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import argparse
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from backend_core.utils.ma_calculator import MACalculator
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ma_backfill.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MABackfillProcessor:
    """MA指标回溯计算处理器"""
    
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
            market_type: 市场类型（'A股' 或 '港股'，或 'CN'/'HK'）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            List[tuple]: (date, close) 列表，按日期升序排列
        """
        try:
            # 统一市场类型标识
            if market_type == 'A股' or market_type == 'CN':
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
            elif market_type == '港股' or market_type == 'HK':
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
    
    def check_existing_ma(self, stock_code: str, market_type: str, date: str) -> bool:
        """
        检查MA数据是否已存在
        
        Args:
            stock_code: 股票代码
            market_type: 市场类型（'CN' 或 'HK'）
            date: 日期
            
        Returns:
            bool: 是否存在
        """
        try:
            result = self.session.execute(text("""
                SELECT COUNT(*) 
                FROM ma_indicators 
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
            logger.error(f"检查MA数据是否存在失败: {e}")
            return False
    
    def process_single_stock(self, stock_code: str, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, skip_existing: bool = True) -> bool:
        """
        处理单只股票的MA计算
        
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
            # market_type 已经是 'CN' 或 'HK' 格式
            query_market_type = market_type
            
            # 获取历史收盘价数据
            rows = self.get_historical_closes(stock_code, query_market_type, start_date, end_date)
            
            if len(rows) < 5:
                logger.debug(f"股票 {stock_code} 历史数据不足5天，跳过MA计算")
                self.skipped_count += 1
                return True
            
            # 构建DataFrame
            df_data = []
            for row in rows:
                date_val = row[0]
                close_val = row[1]
                
                # 统一处理日期格式
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                elif isinstance(date_val, str):
                    date_str = date_val
                    # 处理 YYYYMMDD 格式（8位数字）
                    if len(date_str) == 8 and date_str.isdigit():
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    date_str = str(date_val)
                    # 处理 YYYYMMDD 格式（8位数字）
                    if len(date_str) == 8 and date_str.isdigit():
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                df_data.append({
                    'date': date_str,
                    'close': float(close_val) if close_val else None
                })
            
            df = pd.DataFrame(df_data)
            
            # 统一转换日期格式：先尝试标准格式，再尝试YYYYMMDD格式
            def parse_date(date_str):
                if pd.isna(date_str) or date_str is None:
                    return pd.NaT
                date_str = str(date_str).strip()
                
                # 尝试 YYYY-MM-DD 格式
                if len(date_str) == 10 and '-' in date_str:
                    try:
                        return pd.to_datetime(date_str, format='%Y-%m-%d')
                    except:
                        pass
                
                # 尝试 YYYYMMDD 格式（8位数字）
                if len(date_str) == 8 and date_str.isdigit():
                    try:
                        return pd.to_datetime(date_str, format='%Y%m%d')
                    except:
                        pass
                
                # 默认尝试自动解析
                try:
                    return pd.to_datetime(date_str)
                except:
                    return pd.NaT
            
            df['date'] = df['date'].apply(parse_date)
            
            # 删除无效日期和无效收盘价
            df = df.dropna(subset=['date', 'close'])
            df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
            
            if 'close' not in df.columns or len(df) == 0:
                logger.debug(f"股票 {stock_code} 收盘价数据无效")
                self.skipped_count += 1
                return True
            
            # 计算MA指标
            ma_df = MACalculator.calculate_ma_for_dataframe(df, periods=[5, 10, 20, 30, 60, 120, 200])
            
            # 保存MA数据
            saved_count = 0
            skipped_count = 0
            
            for _, row in ma_df.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d') if isinstance(row['date'], pd.Timestamp) else str(row['date'])
                
                # 检查是否已存在
                if skip_existing and self.check_existing_ma(stock_code, market_type, date_str):
                    skipped_count += 1
                    continue
                
                try:
                    self.session.execute(text("""
                        INSERT INTO ma_indicators
                        (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200, created_at)
                        VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            ma5 = EXCLUDED.ma5,
                            ma10 = EXCLUDED.ma10,
                            ma20 = EXCLUDED.ma20,
                            ma30 = EXCLUDED.ma30,
                            ma60 = EXCLUDED.ma60,
                            ma120 = EXCLUDED.ma120,
                            ma200 = EXCLUDED.ma200,
                            created_at = EXCLUDED.created_at
                    """), {
                        'code': stock_code,
                        'date': date_str,
                        'market_type': market_type,
                        'ma5': self._safe_value(row.get('ma5')),
                        'ma10': self._safe_value(row.get('ma10')),
                        'ma20': self._safe_value(row.get('ma20')),
                        'ma30': self._safe_value(row.get('ma30')),
                        'ma60': self._safe_value(row.get('ma60')),
                        'ma120': self._safe_value(row.get('ma120')),
                        'ma200': self._safe_value(row.get('ma200')),
                        'created_at': datetime.now()
                    })
                    saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} MA数据失败: {e}")
                    continue
            
            if saved_count > 0:
                self.session.commit()
                self.processed_count += saved_count
                logger.info(f"股票 {stock_code} MA计算完成: 新增 {saved_count} 条，跳过 {skipped_count} 条")
            else:
                logger.debug(f"股票 {stock_code} MA数据已全部存在，跳过")
                self.skipped_count += 1
            
            return True
            
        except Exception as e:
            logger.error(f"处理股票 {stock_code} MA计算失败: {e}")
            self.session.rollback()
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def _safe_value(self, val) -> Optional[float]:
        """安全地转换数值"""
        try:
            if val is None or pd.isna(val):
                return None
            return float(val)
        except Exception:
            return None
    
    def process_batch(self, market_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, stock_codes: Optional[List[str]] = None, skip_existing: bool = True):
        """
        批量处理MA计算
        
        Args:
            market_type: 市场类型（'CN' 代表A股，'HK' 代表港股，'ALL' 代表全部）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            stock_codes: 指定股票代码列表（可选）
            skip_existing: 是否跳过已存在的数据
        """
        try:
            logger.info(f"开始批量计算MA指标: 市场={market_type}, 开始日期={start_date}, 结束日期={end_date}")
            
            # 重置计数器
            self.processed_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_stocks = []
            
            # 获取股票列表
            if stock_codes:
                stocks = stock_codes
                # 根据股票代码判断市场类型
                if market_type == 'ALL':
                    market_types = []
                    for code in stock_codes:
                        # 查询数据库判断股票属于哪个市场
                        result = self.session.execute(text("""
                            SELECT COUNT(*) FROM historical_quotes WHERE code = :code
                        """), {'code': code})
                        if result.fetchone()[0] > 0:
                            market_types.append('CN')
                        else:
                            result = self.session.execute(text("""
                                SELECT COUNT(*) FROM historical_quotes_hk WHERE code = :code
                            """), {'code': code})
                            if result.fetchone()[0] > 0:
                                market_types.append('HK')
                            else:
                                logger.warning(f"股票 {code} 在历史行情表中不存在，跳过")
                                market_types.append('CN')  # 默认A股，后续会跳过
                else:
                    market_types = [market_type] * len(stocks)
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
            
            logger.info(f"准备处理 {len(stocks)} 只股票的MA数据")
            
            # 批量处理
            for i, stock_code in enumerate(stocks):
                current_market_type = market_types[i] if i < len(market_types) else market_type
                
                # 转换为数据库中的市场类型标识（使用 CN/HK 格式）
                db_market_type = current_market_type  # 'CN' 或 'HK'
                
                logger.info(f"进度: {i+1}/{len(stocks)} - 处理股票 {stock_code} ({db_market_type})")
                
                self.process_single_stock(stock_code, db_market_type, start_date, end_date, skip_existing)
                
                # 每处理10只股票输出一次进度
                if (i + 1) % 10 == 0:
                    logger.info(f"已处理 {i+1}/{len(stocks)} 只股票，新增 {self.processed_count} 条，跳过 {self.skipped_count} 条，失败 {self.failed_count} 只")
            
            # 输出最终统计
            logger.info(f"批量MA计算完成:")
            logger.info(f"  - 总计股票: {len(stocks)}")
            logger.info(f"  - 新增数据: {self.processed_count} 条")
            logger.info(f"  - 跳过数据: {self.skipped_count} 条")
            logger.info(f"  - 失败股票: {self.failed_count} 只")
            if self.failed_stocks:
                logger.warning("失败详情:")
                for detail in self.failed_stocks[:10]:  # 只显示前10个
                    logger.warning(f"  - {detail}")
                    
        except Exception as e:
            logger.error(f"批量MA计算失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MA指标回溯计算批处理程序')
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
    processor = MABackfillProcessor()
    
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

