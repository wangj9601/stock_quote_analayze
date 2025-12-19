#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用akshare采集历史行情数据
支持指定日期范围批量采集所有股票的历史数据
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import time
import random

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import akshare as ak
import pandas as pd
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.rsi_calculator import RSICalculator
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('akshare_historical_collect.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AkshareHistoricalCollector:
    """使用akshare采集历史行情数据"""
    
    def __init__(self):
        self.session = SessionLocal()
        self.collected_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_stocks = []
        self._init_macd_table()
        self._init_macd_table()
        self._init_kdj_table()
        self._init_rsi_table()
        
    def __del__(self):
        """析构函数，确保session被关闭"""
        if hasattr(self, 'session'):
            self.session.close()

    def _init_kdj_table(self):
        """初始化KDJ指标表结构"""
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
            logger.debug("KDJ指标表初始化完成")
        except Exception as e:
            logger.warning(f"KDJ指标表初始化失败（可能已存在）: {e}")
            self.session.rollback()
            self.session.rollback()

    def _init_rsi_table(self):
        """初始化RSI指标表结构"""
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS rsi_indicators (
                    code VARCHAR(20) NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL,
                    rsi6 REAL,
                    rsi12 REAL,
                    rsi24 REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
            '''))
            self.session.commit()
            logger.debug("RSI指标表初始化完成")
        except Exception as e:
            logger.warning(f"RSI指标表初始化失败（可能已存在）: {e}")
            self.session.rollback()
        """初始化MACD指标表结构"""
        try:
            self.session.execute(text('''
                CREATE TABLE IF NOT EXISTS macd_indicators (
                    code VARCHAR(20) NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL,
                    dif REAL,
                    dea REAL,
                    macd REAL,
                    ema12 REAL,
                    ema26 REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
            '''))
            self.session.commit()
            logger.debug("MACD指标表初始化完成")
        except Exception as e:
            logger.warning(f"MACD指标表初始化失败（可能已存在）: {e}")
            self.session.rollback()
    
    def get_stock_list(self) -> List[Dict[str, str]]:
        """
        从stock_basic_info表获取股票列表
        
        Returns:
            List[Dict]: 股票信息列表，包含code和name
        """
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
            
            logger.info(f"从数据库获取到 {len(stocks)} 只股票")
            return stocks
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def check_existing_data(self, stock_code: str, start_date: str, end_date: str) -> List[str]:
        """
        检查指定股票在日期范围内已存在的数据日期
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            List[str]: 已存在的日期列表
        """
        try:
            result = self.session.execute(text("""
                SELECT date 
                FROM historical_quotes 
                WHERE code = :stock_code 
                AND date >= :start_date 
                AND date <= :end_date
                ORDER BY date
            """), {
                'stock_code': stock_code,
                'start_date': start_date,
                'end_date': end_date
            })
            
            existing_dates = [row[0] for row in result.fetchall()]
            return existing_dates
            
        except Exception as e:
            logger.error(f"检查股票 {stock_code} 已存在数据失败: {e}")
            return []
    
    def collect_single_stock_data(self, stock_code: str, start_date: str, end_date: str) -> bool:
        """
        采集单只股票的历史数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            bool: 采集是否成功
        """
        try:
            # 检查已存在的数据
            existing_dates = self.check_existing_data(stock_code, start_date, end_date)
            if existing_dates:
                logger.debug(f"股票 {stock_code} 在 {start_date} 到 {end_date} 期间已有 {len(existing_dates)} 天数据")
            
            # 使用akshare获取历史数据
            logger.info(f"开始采集股票 {stock_code} 的历史数据...")
            
            # 添加重试机制
            max_retries = 5
            df = None
            for attempt in range(max_retries):
                try:
                    # 使用akshare获取历史数据
                    df = ak.stock_zh_a_hist(
                        symbol=stock_code,
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq"  # 前复权
                    )
                    break
                except (AttributeError, ValueError, IndexError) as e:
                    # 捕获常见的解析错误，如 AttributeError: 'NoneType' object has no attribute 'text'
                    # 这通常意味着akshare无法从网页解析数据，可能是反爬虫限制或数据为空
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"股票 {stock_code} 第 {attempt + 1} 次采集遭受解析错误，{wait_time:.1f}秒后重试: {e}")
                        time.sleep(wait_time)
                except Exception as e:
                    # 捕获网络错误，如SSLError
                    error_str = str(e)
                    is_ssl_error = "SSLError" in error_str or "Connection" in error_str or "UNEXPECTED_EOF_WHILE_READING" in error_str
                    
                    if attempt < max_retries - 1:
                        # 对于SSL或连接错误，等待时间加长
                        wait_time = (attempt + 1) * 5 + random.uniform(1, 3) if is_ssl_error else (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"股票 {stock_code} 第 {attempt + 1} 次采集失败，{wait_time:.1f}秒后重试: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"股票 {stock_code} 采集最终失败: {e}")
            
            if df is None or df.empty:
                logger.warning(f"股票 {stock_code} 未获取到有效数据")
                return False

            
            logger.info(f"股票 {stock_code} 采集到 {len(df)} 条数据")
            
            # 处理数据并插入数据库
            success_count = 0
            skip_count = 0
            
            for _, row in df.iterrows():
                try:
                    # 转换日期格式
                    trade_date = pd.to_datetime(row['日期']).strftime('%Y-%m-%d')
                    
                    # 检查是否已存在
                    if trade_date in existing_dates:
                        skip_count += 1
                        continue
                    
                    # 准备插入数据
                    data = {
                        'code': stock_code,
                        'ts_code': f"{stock_code}.SZ" if stock_code.startswith('0') else f"{stock_code}.SH",
                        'name': '',  # 从stock_basic_info表获取
                        'market': 'SZ' if stock_code.startswith('0') else 'SH',
                        'date': trade_date,
                        'open': float(row['开盘']) if pd.notna(row['开盘']) else None,
                        'high': float(row['最高']) if pd.notna(row['最高']) else None,
                        'low': float(row['最低']) if pd.notna(row['最低']) else None,
                        'close': float(row['收盘']) if pd.notna(row['收盘']) else None,
                        'pre_close': float(row['前收盘']) if pd.notna(row['前收盘']) else None,
                        'volume': float(row['成交量']) if pd.notna(row['成交量']) else None,
                        'amount': float(row['成交额']) if pd.notna(row['成交额']) else None,
                        'change_percent': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                        'change': float(row['涨跌额']) if pd.notna(row['涨跌额']) else None,
                        'amplitude': float(row['振幅']) if pd.notna(row['振幅']) else None,
                        'turnover_rate': float(row['换手率']) if pd.notna(row['换手率']) else None,
                        'collected_source': 'akshare',
                        'collected_date': datetime.now().isoformat()
                    }
                    
                    # 插入数据
                    self.session.execute(text("""
                        INSERT INTO historical_quotes
                        (code, ts_code, name, market, date, open, high, low, close, pre_close, 
                         volume, amount, change_percent, change, amplitude, turnover_rate, 
                         collected_source, collected_date)
                        VALUES (:code, :ts_code, :name, :market, :date, :open, :high, :low, :close, :pre_close,
                                :volume, :amount, :change_percent, :change, :amplitude, :turnover_rate,
                                :collected_source, :collected_date)
                    """), data)
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"处理股票 {stock_code} 日期 {trade_date} 数据时出错: {e}")
                    continue
            
            # 提交事务
            self.session.commit()
            
            self.collected_count += success_count
            self.skipped_count += skip_count
            
            logger.info(f"股票 {stock_code} 处理完成: 新增 {success_count} 条，跳过 {skip_count} 条")
            
            # 计算并保存MACD指标（仅对新增的数据）
            if success_count > 0:
                try:
                    self._calculate_and_save_macd(stock_code, start_date, end_date)
                except Exception as e:
                    logger.warning(f"股票 {stock_code} MACD指标计算失败: {e}")

            # 计算并保存KDJ指标
            if success_count > 0:
                try:
                    self._calculate_and_save_kdj(stock_code, start_date, end_date)
                except Exception as e:
                    logger.warning(f"股票 {stock_code} KDJ指标计算失败: {e}")
                except Exception as e:
                    logger.warning(f"股票 {stock_code} KDJ指标计算失败: {e}")

            # 计算并保存RSI指标
            if success_count > 0:
                try:
                    self._calculate_and_save_rsi(stock_code, start_date, end_date)
                except Exception as e:
                    logger.warning(f"股票 {stock_code} RSI指标计算失败: {e}")
            time.sleep(random.uniform(0.5, 1.5))
            
            return True
            
        except Exception as e:
            logger.error(f"采集股票 {stock_code} 历史数据失败: {e}")
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def collect_historical_data(self, start_date: str, end_date: str, stock_codes: Optional[List[str]] = None) -> Dict[str, any]:
        """
        批量采集历史行情数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            stock_codes: 指定股票代码列表，如果为None则采集所有股票
            
        Returns:
            Dict: 采集结果统计
        """
        try:
            logger.info(f"开始批量采集历史行情数据: {start_date} 到 {end_date}")
            
            # 获取股票列表
            if stock_codes:
                stocks = []
                for code in stock_codes:
                    result = self.session.execute(text("""
                        SELECT code, name FROM stock_basic_info WHERE code = :code
                    """), {'code': code})
                    row = result.fetchone()
                    if row:
                        stocks.append({'code': row[0], 'name': row[1] if row[1] else ''})
                    else:
                        logger.warning(f"股票代码 {code} 在stock_basic_info表中不存在")
            else:
                stocks = self.get_stock_list()
            
            if not stocks:
                logger.error("没有找到需要采集的股票")
                return {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'collected': 0,
                    'skipped': 0,
                    'failed_details': []
                }
            
            logger.info(f"准备采集 {len(stocks)} 只股票的历史数据")
            
            # 重置计数器
            self.collected_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_stocks = []
            
            # 批量采集
            success_count = 0
            for i, stock in enumerate(stocks, 1):
                logger.info(f"进度: {i}/{len(stocks)} - 采集股票 {stock['code']} ({stock['name']})")
                
                if self.collect_single_stock_data(stock['code'], start_date, end_date):
                    success_count += 1
                
                # 每处理10只股票输出一次进度
                if i % 10 == 0:
                    logger.info(f"已处理 {i}/{len(stocks)} 只股票，成功 {success_count} 只")
            
            # 记录采集日志
            self._log_collection_result(start_date, end_date, len(stocks), success_count)
            
            result = {
                'total': len(stocks),
                'success': success_count,
                'failed': self.failed_count,
                'collected': self.collected_count,
                'skipped': self.skipped_count,
                'failed_details': self.failed_stocks
            }
            
            logger.info(f"批量采集完成:")
            logger.info(f"  - 总计股票: {result['total']}")
            logger.info(f"  - 成功采集: {result['success']}")
            logger.info(f"  - 采集失败: {result['failed']}")
            logger.info(f"  - 新增数据: {result['collected']} 条")
            logger.info(f"  - 跳过数据: {result['skipped']} 条")
            
            return result
            
        except Exception as e:
            logger.error(f"批量采集历史数据失败: {e}")
            return {
                'total': 0,
                'success': 0,
                'failed': 1,
                'collected': 0,
                'skipped': 0,
                'failed_details': [str(e)]
            }
    
    def _calculate_and_save_macd(self, stock_code: str, start_date: str, end_date: str):
        """
        计算并保存MACD指标
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        try:
            # 查询该股票最近至少26天的收盘价数据（用于计算MACD）
            # 需要查询更多天数以确保有足够的数据
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            
            result = self.session.execute(text("""
                SELECT date, close 
                FROM historical_quotes 
                WHERE code = :stock_code 
                AND date >= :query_start_date 
                AND date <= :end_date
                AND close IS NOT NULL
                ORDER BY date ASC
            """), {
                'stock_code': stock_code,
                'query_start_date': query_start_date,
                'end_date': end_date
            })
            
            rows = result.fetchall()
            if len(rows) < 26:
                logger.debug(f"股票 {stock_code} 历史数据不足26天，跳过MACD计算")
                return
            
            # 提取收盘价列表
            closes = [float(row[1]) for row in rows]
            dates = [row[0] for row in rows]
            
            # 使用MACD计算器批量计算
            calculator = MACDCalculator()
            macd_results = calculator.calculate_macd_batch(closes)
            
            if not macd_results:
                return
            
            # 保存MACD数据（只保存日期范围内的数据）
            macd_saved_count = 0
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            for i, macd_data in enumerate(macd_results):
                if macd_data['dif'] is None:
                    continue
                
                date_obj = dates[i] if isinstance(dates[i], datetime) else datetime.strptime(str(dates[i]), '%Y-%m-%d').date()
                
                # 只保存日期范围内的数据
                if date_obj < start_date_obj or date_obj > end_date_obj:
                    continue
                
                date_str = date_obj.strftime('%Y-%m-%d') if isinstance(date_obj, datetime) else str(date_obj)
                
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
                        'market_type': 'CN',
                        'dif': macd_data['dif'],
                        'dea': macd_data['dea'],
                        'macd': macd_data['macd'],
                        'ema12': macd_data['ema12'],
                        'ema26': macd_data['ema26'],
                        'created_at': datetime.now()
                    })
                    macd_saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} MACD数据失败: {e}")
                    continue
            
            if macd_saved_count > 0:
                self.session.commit()
                logger.debug(f"股票 {stock_code} MACD指标计算完成，保存 {macd_saved_count} 条数据")
            
        except Exception as e:
            logger.error(f"计算股票 {stock_code} MACD指标失败: {e}")
            self.session.rollback()

    def _calculate_and_save_kdj(self, stock_code: str, start_date: str, end_date: str):
        """
        计算并保存KDJ指标
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        try:
            # 查询该股票最近至少20天的收盘价数据（用于计算KDJ）
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            
            result = self.session.execute(text("""
                SELECT date, close, high, low 
                FROM historical_quotes 
                WHERE code = :stock_code 
                AND date >= :query_start_date 
                AND date <= :end_date
                AND close IS NOT NULL 
                AND high IS NOT NULL 
                AND low IS NOT NULL
                ORDER BY date ASC
            """), {
                'stock_code': stock_code,
                'query_start_date': query_start_date,
                'end_date': end_date
            })
            
            rows = result.fetchall()
            if len(rows) < 9:
                logger.debug(f"股票 {stock_code} 历史数据不足9天，跳过KDJ计算")
                return
            
            # 提取数据列表
            dates = [row[0] for row in rows]
            closes = [float(row[1]) for row in rows]
            highs = [float(row[2]) for row in rows]
            lows = [float(row[3]) for row in rows]
            
            # 使用KDJ计算器批量计算
            calculator = KDJCalculator()
            kdj_results = calculator.calculate_kdj_batch(closes, highs, lows)
            
            if not kdj_results:
                return
            
            # 保存KDJ数据（只保存日期范围内的数据）
            kdj_saved_count = 0
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            for i, kdj_data in enumerate(kdj_results):
                date_obj = dates[i] if isinstance(dates[i], datetime) else datetime.strptime(str(dates[i]), '%Y-%m-%d').date()
                
                # 只保存日期范围内的数据
                if date_obj < start_date_obj or date_obj > end_date_obj:
                    continue
                
                date_str = date_obj.strftime('%Y-%m-%d') if isinstance(date_obj, datetime) else str(date_obj)
                
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
                        'market_type': 'CN',
                        'k': kdj_data['k'],
                        'd': kdj_data['d'],
                        'j': kdj_data['j'],
                        'rsv': kdj_data['rsv'],
                        'created_at': datetime.now()
                    })
                    kdj_saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} KDJ数据失败: {e}")
                    continue
            
            if kdj_saved_count > 0:
                self.session.commit()
                logger.debug(f"股票 {stock_code} KDJ指标计算完成，保存 {kdj_saved_count} 条数据")
            
        except Exception as e:
            logger.error(f"计算股票 {stock_code} KDJ指标失败: {e}")
            self.session.rollback()

    def _calculate_and_save_rsi(self, stock_code: str, start_date: str, end_date: str):
        """
        计算并保存RSI指标
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        try:
            # 查询该股票最近至少30天的收盘价数据（用于计算RSI，RSI24需要24+周期）
            query_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
            
            result = self.session.execute(text("""
                SELECT date, close
                FROM historical_quotes 
                WHERE code = :stock_code 
                AND date >= :query_start_date 
                AND date <= :end_date
                AND close IS NOT NULL 
                ORDER BY date ASC
            """), {
                'stock_code': stock_code,
                'query_start_date': query_start_date,
                'end_date': end_date
            })
            
            rows = result.fetchall()
            if len(rows) < 7: # rsi6至少需要7天数据 (1 for diff, 6 for avg)
                logger.debug(f"股票 {stock_code} 历史数据不足7天，跳过RSI计算")
                return
            
            # 提取数据列表
            dates = [row[0] for row in rows]
            closes = [float(row[1]) for row in rows]
            
            # 使用RSI计算器批量计算
            calculator = RSICalculator()
            rsi_results = calculator.calculate_rsi_batch(closes)
            
            if not rsi_results:
                return
            
            # 保存RSI数据（只保存日期范围内的数据）
            rsi_saved_count = 0
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            for i, rsi_data in enumerate(rsi_results):
                date_obj = dates[i] if isinstance(dates[i], datetime) else datetime.strptime(str(dates[i]), '%Y-%m-%d').date()
                
                # 只保存日期范围内的数据
                if date_obj < start_date_obj or date_obj > end_date_obj:
                    continue
                
                date_str = date_obj.strftime('%Y-%m-%d') if isinstance(date_obj, datetime) else str(date_obj)
                
                try:
                    self.session.execute(text("""
                        INSERT INTO rsi_indicators
                        (code, date, market_type, rsi6, rsi12, rsi24, created_at)
                        VALUES (:code, :date, :market_type, :rsi6, :rsi12, :rsi24, :created_at)
                        ON CONFLICT (code, date, market_type) DO UPDATE SET
                            rsi6 = EXCLUDED.rsi6,
                            rsi12 = EXCLUDED.rsi12,
                            rsi24 = EXCLUDED.rsi24,
                            created_at = EXCLUDED.created_at
                    """), {
                        'code': stock_code,
                        'date': date_str,
                        'market_type': 'CN',
                        'rsi6': rsi_data.get('rsi6'),
                        'rsi12': rsi_data.get('rsi12'),
                        'rsi24': rsi_data.get('rsi24'),
                        'created_at': datetime.now()
                    })
                    rsi_saved_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock_code} 日期 {date_str} RSI数据失败: {e}")
                    continue
            
            if rsi_saved_count > 0:
                self.session.commit()
                logger.debug(f"股票 {stock_code} RSI指标计算完成，保存 {rsi_saved_count} 条数据")
            
        except Exception as e:
            logger.error(f"计算股票 {stock_code} RSI指标失败: {e}")
            self.session.rollback()
    
    def _log_collection_result(self, start_date: str, end_date: str, total_stocks: int, success_stocks: int):
        """记录采集结果到日志表"""
        try:
            self.session.execute(text("""
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message)
            """), {
                'operation_type': 'akshare_historical_collect',
                'operation_desc': f'采集日期范围: {start_date} 到 {end_date}\n总计股票: {total_stocks}\n成功采集: {success_stocks}\n新增数据: {self.collected_count}\n跳过数据: {self.skipped_count}',
                'affected_rows': self.collected_count,
                'status': 'success' if self.failed_count == 0 else 'partial_success',
                'error_message': '\n'.join(self.failed_stocks) if self.failed_stocks else None
            })
            self.session.commit()
            
        except Exception as e:
            logger.error(f"记录采集日志失败: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='使用akshare采集历史行情数据')
    parser.add_argument('start_date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('end_date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--stocks', nargs='+', help='指定股票代码列表，不指定则采集所有股票')
    parser.add_argument('--test', action='store_true', help='测试模式，只采集前5只股票')
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        logger.error("日期格式错误，请使用 YYYY-MM-DD 格式")
        sys.exit(1)
    
    # 创建采集器
    collector = AkshareHistoricalCollector()
    
    try:
        # 执行采集
        if args.test:
            logger.info("测试模式：只采集前5只股票")
            stocks = collector.get_stock_list()[:5]
            stock_codes = [stock['code'] for stock in stocks]
        else:
            stock_codes = args.stocks
        
        result = collector.collect_historical_data(args.start_date, args.end_date, stock_codes)
        
        if result['failed'] > 0:
            logger.warning(f"采集完成，但有 {result['failed']} 只股票采集失败")
            if result['failed_details']:
                logger.warning("失败详情:")
                for detail in result['failed_details'][:10]:  # 只显示前10个
                    logger.warning(f"  - {detail}")
        else:
            logger.info("采集完成，所有股票都成功采集")
            
    except KeyboardInterrupt:
        logger.info("用户中断采集")
    except Exception as e:
        logger.error(f"采集过程中发生错误: {e}")
        sys.exit(1)
    finally:
        collector.session.close()

if __name__ == "__main__":
    main()
