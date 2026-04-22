#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史数据采集API服务
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import shutil
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import akshare as ak
import pandas as pd
import time
import random

from backend_api.database import get_db
from backend_api.models import (
    DataCollectionRequest,
    DataCollectionResponse,
    DataCollectionStatus,
    TushareHistoricalCollectionRequest,
    RealtimeCollectionRequest,
    RealtimeCollectionResponse,
    RealtimeHistoricalCollectionRequest,
    FileHistoricalCollectionRequest,
    HKFileHistoricalCollectionRequest,
)
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.rsi_calculator import RSICalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from sqlalchemy import text, bindparam

router = APIRouter(prefix="/api/data-collection", tags=["数据采集"])

# 全局变量存储采集任务状态
collection_tasks = {}
task_lock = threading.Lock()
# 全局变量控制单任务执行
current_task_id = None
task_execution_lock = threading.Lock()

logger = logging.getLogger(__name__)

class AkshareDataCollector:
    """akshare数据采集器"""
    
    def __init__(self, db_session: Session):
        self.session = db_session
        self.collected_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_stocks = []
        # 初始化港股表结构，添加全量采集标志字段
        self._init_hk_table_structure()
    
    def _init_hk_table_structure(self):
        """初始化港股表结构，添加全量采集标志字段"""
        try:
            # 尝试添加全量采集相关字段（如果不存在）
            try:
                self.session.execute(text("""
                    ALTER TABLE stock_basic_info_hk 
                    ADD COLUMN IF NOT EXISTS full_collection_completed BOOLEAN DEFAULT FALSE
                """))
                self.session.commit()
            except Exception:
                # PostgreSQL不支持IF NOT EXISTS，使用DO块
                try:
                    self.session.execute(text("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='stock_basic_info_hk' 
                                AND column_name='full_collection_completed'
                            ) THEN
                                ALTER TABLE stock_basic_info_hk 
                                ADD COLUMN full_collection_completed BOOLEAN DEFAULT FALSE;
                            END IF;
                        END $$;
                    """))
                    self.session.commit()
                except Exception as e:
                    logger.debug(f"字段 full_collection_completed 可能已存在: {e}")
                    self.session.rollback()
            
            try:
                self.session.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='stock_basic_info_hk' 
                            AND column_name='full_collection_date'
                        ) THEN
                            ALTER TABLE stock_basic_info_hk 
                            ADD COLUMN full_collection_date TIMESTAMP;
                        END IF;
                    END $$;
                """))
                self.session.commit()
            except Exception as e:
                logger.debug(f"字段 full_collection_date 可能已存在: {e}")
                self.session.rollback()
            
            try:
                self.session.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='stock_basic_info_hk' 
                            AND column_name='full_collection_start_date'
                        ) THEN
                            ALTER TABLE stock_basic_info_hk 
                            ADD COLUMN full_collection_start_date TEXT;
                        END IF;
                    END $$;
                """))
                self.session.commit()
            except Exception as e:
                logger.debug(f"字段 full_collection_start_date 可能已存在: {e}")
                self.session.rollback()
            
            try:
                self.session.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='stock_basic_info_hk' 
                            AND column_name='full_collection_end_date'
                        ) THEN
                            ALTER TABLE stock_basic_info_hk 
                            ADD COLUMN full_collection_end_date TEXT;
                        END IF;
                    END $$;
                """))
                self.session.commit()
            except Exception as e:
                logger.debug(f"字段 full_collection_end_date 可能已存在: {e}")
                self.session.rollback()
                
        except Exception as e:
            logger.warning(f"初始化港股表结构失败（可能字段已存在）: {e}")
            self.session.rollback()
        
    def get_stock_list(self, only_uncompleted: bool = False) -> List[Dict[str, str]]:
        """从stock_basic_info表获取股票列表"""
        try:
            self.session.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info' AND column_name='collect_enabled') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
                    END IF;
                END
                $$;
            """))
            self.session.commit()
            if only_uncompleted:
                # 只返回未完成全量采集的股票
                result = self.session.execute(text("""
                    SELECT code, name, full_collection_completed, full_collection_date
                    FROM stock_basic_info 
                    WHERE COALESCE(collect_enabled, TRUE) = TRUE
                      AND (full_collection_completed = FALSE OR full_collection_completed IS NULL)
                    ORDER BY code
                """))
            else:
                # 返回所有股票，包含全量采集状态
                result = self.session.execute(text("""
                    SELECT code, name, full_collection_completed, full_collection_date
                    FROM stock_basic_info 
                    WHERE COALESCE(collect_enabled, TRUE) = TRUE
                    ORDER BY code
                """))
            
            stocks = []
            for row in result.fetchall():
                stocks.append({
                    'code': str(row[0]),  # 确保code是字符串
                    'name': row[1] if row[1] else '',
                    'full_collection_completed': bool(row[2]) if row[2] is not None else False,
                    'full_collection_date': row[3].isoformat() if row[3] else None
                })
            
            logger.info(f"从数据库获取到 {len(stocks)} 只股票")
            return stocks
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def get_stock_list_from_realtime_quote(self) -> List[Dict[str, str]]:
        """从 A 股实时行情表 stock_realtime_quote 获取股票列表（去重 code）"""
        try:
            result = self.session.execute(text("""
                SELECT code, MAX(name) AS name
                FROM stock_realtime_quote
                GROUP BY code
                ORDER BY code
            """))
            stocks = []
            for row in result.fetchall():
                stocks.append({
                    'code': str(row[0]).strip(),
                    'name': (row[1] or '').strip() if row[1] else ''
                })
            logger.info(f"从实时行情表获取到 {len(stocks)} 只A股")
            return stocks
        except Exception as e:
            logger.error(f"从实时行情表获取股票列表失败: {e}")
            return []

    def get_hk_stock_list(self, only_uncompleted: bool = False) -> List[Dict[str, str]]:
        """从stock_basic_info_hk表获取港股列表"""
        try:
            self.session.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info_hk' AND column_name='collect_enabled') THEN
                        ALTER TABLE stock_basic_info_hk ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
                    END IF;
                END
                $$;
            """))
            self.session.commit()
            # 检查是否有数据
            count_result = self.session.execute(text("SELECT count(*) FROM stock_basic_info_hk"))
            count = count_result.scalar()
            
            if count < 100: # 如果数据太少，尝试重新获取
                logger.info("港股基础信息表数据过少，尝试从AkShare获取最新列表...")
                try:
                    df = ak.stock_hk_spot()
                    if df is not None and not df.empty:
                        # akshare返回列: symbol, name, ...
                        for _, row in df.iterrows():
                            code = str(row['symbol'])
                            name = str(row['name'])
                            # 简单的插入，忽略冲突
                            self.session.execute(text("""
                                INSERT INTO stock_basic_info_hk (code, name, create_date)
                                VALUES (:code, :name, :create_date)
                                ON CONFLICT (code) DO UPDATE SET name = :name
                            """), {
                                'code': code,
                                'name': name,
                                'create_date': datetime.now()
                            })
                        self.session.commit()
                        logger.info(f"已更新港股基础信息表，共 {len(df)} 条")
                except Exception as e:
                    logger.error(f"从AkShare获取港股列表失败: {e}")
            
            # 查询数据库
            if only_uncompleted:
                # 只获取未完成全量采集的港股
                result = self.session.execute(text("""
                    SELECT code, name
                    FROM stock_basic_info_hk 
                    WHERE COALESCE(collect_enabled, TRUE) = TRUE
                      AND (full_collection_completed IS NULL OR full_collection_completed = FALSE)
                    ORDER BY code
                """))
            else:
                # 获取所有港股
                result = self.session.execute(text("""
                    SELECT code, name
                    FROM stock_basic_info_hk 
                    WHERE COALESCE(collect_enabled, TRUE) = TRUE
                    ORDER BY code
                """))
            
            stocks = []
            for row in result.fetchall():
                stocks.append({
                    'code': str(row[0]),
                    'name': row[1] if row[1] else ''
                })
            
            logger.info(f"从数据库获取到 {len(stocks)} 只港股" + ("（仅未完成全量采集）" if only_uncompleted else ""))
            return stocks
            
        except Exception as e:
            logger.error(f"获取港股列表失败: {e}")
            return []
    
    def check_existing_data(self, stock_code: str, start_date: str, end_date: str) -> List[str]:
        """检查指定股票在日期范围内已存在的数据日期"""
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

    # -----------------------------------------------
    # 节假日缓存：{ market -> set of date strings }
    # -----------------------------------------------
    _holiday_cache: Dict[str, set] = {}
    _holiday_cache_loaded: bool = False

    def _load_holidays(self):
        """从 trading_calendar 表加载全部节假日到内存缓存（每次任务只加载一次）"""
        if self._holiday_cache_loaded:
            return
        try:
            result = self.session.execute(text("""
                SELECT market, holiday_date::text
                FROM trading_calendar
                ORDER BY market, holiday_date
            """))
            for row in result.fetchall():
                mkt, hd = row[0], row[1]
                if mkt not in self._holiday_cache:
                    self._holiday_cache[mkt] = set()
                self._holiday_cache[mkt].add(hd)
            self._holiday_cache_loaded = True
            cn_cnt = len(self._holiday_cache.get('CN', set()))
            hk_cnt = len(self._holiday_cache.get('HK', set()))
            logger.info(f"已加载采集日历节假日: A股 {cn_cnt} 天, 港股 {hk_cnt} 天")
        except Exception as e:
            logger.warning(f"加载节假日失败（将不进行节假日过滤）: {e}")
            self._holiday_cache_loaded = True  # 防止反复重试

    def is_holiday(self, market: str, date_str: str) -> bool:
        """判断指定市场的某天是否为节假日（使用内存缓存）"""
        self._load_holidays()
        return date_str in self._holiday_cache.get(market, set())

    def get_non_holiday_date_range(self, market: str, start_date: str, end_date: str) -> List[str]:
        """返回 start_date ~ end_date 之间排除节假日后的日期列表"""
        self._load_holidays()
        import pandas as pd
        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 仅工作日
        result = []
        holidays = self._holiday_cache.get(market, set())
        for d in dates:
            ds = d.strftime('%Y-%m-%d')
            if ds not in holidays:
                result.append(ds)
        return result


    def collect_single_stock_data(self, stock_code: str, stock_name: str, start_date: str, end_date: str, indicators: Optional[List[str]] = None) -> bool:
        """采集单只股票的历史数据"""
        # 名称含「退」的股票（退市等）不再写入历史行情表
        if stock_name and '退' in stock_name:
            logger.info(f"跳过名称含「退」的A股: {stock_code} {stock_name}")
            return True
        try:
            # 检查已存在的数据
            existing_dates = self.check_existing_data(stock_code, start_date, end_date)
            if existing_dates:
                logger.debug(f"股票 {stock_code} 在 {start_date} 到 {end_date} 期间已有 {len(existing_dates)} 天数据")
            
            # 使用akshare获取历史数据：优先东方财富，失败后回退新浪
            logger.info(f"开始采集股票 {stock_code} 的历史数据...")
            source = 'akshare_eastmoney'
            start_ymd = pd.to_datetime(start_date).strftime('%Y%m%d')
            end_ymd = pd.to_datetime(end_date).strftime('%Y%m%d')
            df = None

            # 1) 东方财富接口（stock_zh_a_hist）重试
            max_retries = 3
            last_em_error = None
            for attempt in range(max_retries):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=stock_code,
                        period='daily',
                        start_date=start_ymd,
                        end_date=end_ymd,
                        adjust=""  # 不复权
                    )
                    break
                except Exception as e:
                    last_em_error = e
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"股票 {stock_code} 第 {attempt + 1} 次东财接口采集失败，{wait_time:.1f}秒后重试: {e}")
                        time.sleep(wait_time)

            # 2) 东财失败或无数据时，回退新浪接口（stock_zh_a_daily）
            if df is None or df.empty:
                source = 'akshare_sina'
                logger.warning(f"股票 {stock_code} 东财接口不可用或无数据，回退新浪接口。东财错误: {last_em_error}")
                try:
                    if stock_code.startswith("6"):
                        sina_symbol = "sh" + stock_code
                    elif stock_code.startswith(("0", "3")):
                        sina_symbol = "sz" + stock_code
                    else:
                        sina_symbol = "bj" + stock_code

                    daily_df = ak.stock_zh_a_daily(
                        symbol=sina_symbol,
                        start_date=start_ymd,
                        end_date=end_ymd,
                        adjust=""
                    )

                    if daily_df is not None and not daily_df.empty:
                        daily_df = daily_df.copy()
                        daily_df['date'] = pd.to_datetime(daily_df['date'])
                        daily_df = daily_df.sort_values('date')
                        pre_close = daily_df['close'].shift(1)
                        daily_df['change_amount'] = daily_df['close'] - pre_close
                        daily_df['change_percent'] = (daily_df['change_amount'] / pre_close) * 100
                        daily_df['amplitude'] = ((daily_df['high'] - daily_df['low']) / pre_close) * 100

                        # 统一成下游写库逻辑使用的中文列名
                        df = pd.DataFrame()
                        df['日期'] = daily_df['date'].dt.strftime('%Y-%m-%d')
                        df['开盘'] = daily_df['open']
                        df['最高'] = daily_df['high']
                        df['最低'] = daily_df['low']
                        df['收盘'] = daily_df['close']
                        df['成交量'] = daily_df['volume']
                        df['成交额'] = daily_df['amount'] if 'amount' in daily_df.columns else None
                        df['涨跌幅'] = daily_df['change_percent']
                        df['涨跌额'] = daily_df['change_amount']
                        df['振幅'] = daily_df['amplitude']
                        df['换手率'] = daily_df['turnover'] * 100 if 'turnover' in daily_df.columns else None
                except Exception as e2:
                    logger.error(f"股票 {stock_code} 新浪接口采集失败: {e2}")
                    self.failed_count += 1
                    self.failed_stocks.append(f"{stock_code}: 东财={last_em_error} | 新浪={str(e2)}")
                    return False

            if df is None:
                logger.error(f"股票 {stock_code} 采集失败：东财与新浪均不可用")
                self.failed_count += 1
                self.failed_stocks.append(f"{stock_code}: 东财={last_em_error} | 新浪=无数据")
                return False
            
            if df.empty:
                logger.warning(f"股票 {stock_code} 在指定日期范围内没有数据")
                return True
            
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

                    # 节假日检查：若为 CN 市场节假日则跳过
                    if self.is_holiday('CN', trade_date):
                        logger.debug(f"A股节假日跳过: {stock_code} {trade_date}")
                        skip_count += 1
                        continue
                    
                    # 准备插入数据
                    data = {
                        'code': stock_code,
                        'ts_code': f"{stock_code}.SZ" if stock_code.startswith('0') else f"{stock_code}.SH",
                        'name': stock_name,  # 从stock_basic_info表获取
                        'market': 'SZ' if stock_code.startswith('0') else 'SH',
                        'date': trade_date,
                        'open': float(row['开盘']) if pd.notna(row['开盘']) else None,
                        'high': float(row['最高']) if pd.notna(row['最高']) else None,
                        'low': float(row['最低']) if pd.notna(row['最低']) else None,
                        'close': float(row['收盘']) if pd.notna(row['收盘']) else None,
                        'pre_close': None,  # akshare没有提供前收盘价，设为None
                        'volume': float(row['成交量']) if pd.notna(row['成交量']) else None,
                        'amount': float(row['成交额']) if pd.notna(row['成交额']) else None,
                        'change_percent': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                        'change': float(row['涨跌额']) if pd.notna(row['涨跌额']) else None,
                        'amplitude': float(row['振幅']) if pd.notna(row['振幅']) else None,
                        'turnover_rate': float(row['换手率']) if pd.notna(row['换手率']) else None,
                        'collected_source': source,
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
            
            # 生成指标数据
            if indicators and success_count > 0:
                self._generate_indicators(stock_code, start_date, end_date, indicators)
            
            # 更新该股票的全量采集标志
            self._update_full_collection_flag(stock_code, start_date, end_date)
            
            # 添加随机延迟，避免请求过于频繁
            time.sleep(random.uniform(0.5, 1.5))
            
            return True
            
        except Exception as e:
            logger.error(f"采集股票 {stock_code} 历史数据失败: {e}")
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def _update_full_collection_flag(self, stock_code: str, start_date: str, end_date: str):
        """更新股票的全量采集标志"""
        try:
            # 更新全量采集标志
            self.session.execute(text("""
                UPDATE stock_basic_info 
                SET full_collection_completed = TRUE,
                    full_collection_date = CURRENT_TIMESTAMP,
                    full_collection_start_date = :start_date,
                    full_collection_end_date = :end_date
                WHERE code = :stock_code
            """), {
                'stock_code': stock_code,
                'start_date': start_date,
                'end_date': end_date
            })
            
            self.session.commit()
            logger.info(f"已更新股票 {stock_code} 的全量采集标志")
            
        except Exception as e:
            logger.error(f"更新股票 {stock_code} 全量采集标志失败: {e}")
            # 不抛出异常，避免影响主流程
    
    def _log_collection_result(self, start_date: str, end_date: str, total_stocks: int, success_stocks: int):
        """记录采集结果到日志表"""
        try:
            self.session.execute(text("""
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
            """), {
                'operation_type': 'akshare_historical_collect',
                'operation_desc': f'采集日期范围: {start_date} 到 {end_date}\n总计股票: {total_stocks}\n成功采集: {success_stocks}\n新增数据: {self.collected_count}\n跳过数据: {self.skipped_count}',
                'affected_rows': self.collected_count,
                'status': 'success' if self.failed_count == 0 else 'partial_success',
                'error_message': '\n'.join(self.failed_stocks) if self.failed_stocks else None,
                'collect_source': 'akshare'
            })
            self.session.commit()
            
        except Exception as e:
            logger.error(f"记录采集日志失败: {e}")
    
    # 增量生成指标时向前取历史的天数（满足 MA200 等长周期计算）
    INDICATOR_LOOKBACK_DAYS = 300

    @staticmethod
    def compute_dynamic_indicator_lookback_days(indicators: Optional[List[str]]) -> int:
        """按本次选择的指标动态计算回看天数（自然日）。
        说明：
        - 仅用于保证首日指标可计算，不代表写入范围；
        - 写入范围应由 only_write_dates 或调用方的日期区间控制。
        """
        if not indicators:
            return 0
        selected = {str(i).strip().lower() for i in indicators if i}
        # 经验换算：交易日 -> 自然日，约乘 1.5 并留少量缓冲
        lookback_map = {
            "ma": 390,      # ~260 交易日（覆盖 MA200 并留缓冲）
            "mavol": 390,   # 同 MA
            "macd": 90,     # ~60 交易日
            "kdj": 90,      # ~60 交易日
            "rsi": 90,      # ~60 交易日
            "boll": 90,     # ~60 交易日
            "pvfrs": 90,    # >=21，保守取 60 交易日窗口
            # icost 为累计型，内部按“历史至 end_date”计算，此处不额外前扩
            "icost": 0,
        }
        days = max((lookback_map.get(k, 0) for k in selected), default=0)
        return days

    def _generate_indicators(self, stock_code: str, start_date: str, end_date: str, indicators: List[str], do_commit: bool = True, incremental_dates: Optional[List[str]] = None, market: str = 'CN'):
        """为指定股票生成技术指标数据。do_commit=False 时由调用方批量提交以提升性能。
        incremental_dates: 若指定，则仅写入这些日期的指标（增量模式，用于每日同步后只更新当日）。"""
        try:
            if do_commit:
                logger.info(f"开始为股票 {stock_code} ({market}) 生成指标: {', '.join(indicators)}" + (" [增量]" if incremental_dates else ""))
            
            # 端口历史行情表切换
            source_table = "historical_quotes_hk" if market == 'HK' else "historical_quotes"
            market_type_val = 'HK' if market == 'HK' else 'CN'
            
            query_start = start_date
            if incremental_dates:
                # 增量模式：仍需足够历史用于 MA200 等，向前扩展查询
                from datetime import datetime as dt
                min_inc = min(incremental_dates)
                start_dt = dt.strptime(min_inc, '%Y-%m-%d').date()
                lookback_start = (start_dt - timedelta(days=self.INDICATOR_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
                if lookback_start < query_start:
                    query_start = lookback_start

            result = self.session.execute(text(f"""
                SELECT date, open, high, low, close, volume
                FROM {source_table} 
                WHERE code = :stock_code 
                AND date >= :start_date 
                AND date <= :end_date
                ORDER BY date
            """), {
                'stock_code': stock_code,
                'start_date': query_start,
                'end_date': end_date
            })
            
            data = result.fetchall()
            only_dates = set(incremental_dates) if incremental_dates else None

            if not data:
                if 'icost' in indicators:
                    self._generate_icost_indicators(
                        stock_code, end_date, do_commit=do_commit, only_dates=only_dates, market=market
                    )
                else:
                    logger.warning(f"股票 {stock_code} 没有历史数据，无法生成指标")
                return
            
            df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            if 'ma' in indicators:
                self._generate_ma_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'mavol' in indicators:
                self._generate_mavol_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'macd' in indicators:
                self._generate_macd_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'kdj' in indicators:
                self._generate_kdj_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'rsi' in indicators:
                self._generate_rsi_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'boll' in indicators:
                self._generate_boll_indicators(stock_code, df, do_commit=do_commit, only_dates=only_dates, market_type=market_type_val)
            if 'pvfrs' in indicators:
                self._generate_pvfrs_indicators(stock_code, query_start, end_date, do_commit=do_commit, only_dates=only_dates, market=market)
            if 'icost' in indicators:
                self._generate_icost_indicators(stock_code, end_date, do_commit=do_commit, only_dates=only_dates, market=market)
            
            if do_commit:
                logger.info(f"股票 {stock_code} 指标生成完成")
        except Exception as e:
            logger.error(f"为股票 {stock_code} 生成指标失败: {e}")
            # 无论单只提交还是批量提交，只要当前股票处理抛错，都必须回滚事务。
            # 否则会让后续 SQL 全部进入 InFailedSqlTransaction 连锁失败。
            self.session.rollback()
    
    def generate_indicators_for_date_range(
        self,
        start_date: str,
        end_date: str,
        indicators: List[str],
        extended_start_days: int = 0,
        market: str = 'CN',
        only_write_dates: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """为指定日期范围内有历史数据的股票批量生成技术指标。
        extended_start_days: 向前扩展查询历史的天数，便于 MA200 等长周期指标有足够数据（如 300）。
        only_write_dates: 若指定（如港股文件导入成功的交易日），仅对这些日期写入指标行；计算仍会用更早历史，但不写入其它日期。"""
        if not indicators:
            return {'total': 0, 'success': 0, 'failed': 0}
        try:
            query_start = start_date
            if extended_start_days > 0:
                from datetime import datetime as dt, timedelta
                start_dt = dt.strptime(start_date, '%Y-%m-%d').date()
                query_start = (start_dt - timedelta(days=extended_start_days)).strftime('%Y-%m-%d')
                logger.info(f"指标计算使用扩展历史: 查询起始 {query_start}（向前 {extended_start_days} 天）")
            # 端口历史行情表切换
            source_table = "historical_quotes_hk" if market == 'HK' else "historical_quotes"
            if only_write_dates:
                uniq_days = sorted(set(only_write_dates))
                logger.info(
                    f"指标写入仅限以下导入成功的交易日（共 {len(uniq_days)} 天）: {uniq_days[:15]}"
                    f"{'...' if len(uniq_days) > 15 else ''}"
                )
                seen_codes = set()
                codes = []
                for d in uniq_days:
                    r = self.session.execute(
                        text(f"SELECT DISTINCT code FROM {source_table} WHERE date = :d ORDER BY code"),
                        {'d': d},
                    )
                    for row in r.fetchall():
                        c = row[0]
                        if c not in seen_codes:
                            seen_codes.add(c)
                            codes.append(c)
            else:
                result = self.session.execute(text(f"""
                    SELECT DISTINCT code FROM {source_table} 
                    WHERE date >= :start_date AND date <= :end_date
                    ORDER BY code
                """), {'start_date': query_start, 'end_date': end_date})
                codes = [row[0] for row in result.fetchall()]
            incremental = only_write_dates if only_write_dates else None
            BATCH_SIZE = 50  # 每 50 只股票批量提交一次，减少 commit 次数
            logger.info(f"指标数据生成: 共 {len(codes)} 只股票，每 {BATCH_SIZE} 只批量提交，每 100 条打印进度")
            success = 0
            failed = 0
            for idx, code in enumerate(codes):
                if (idx + 1) % 100 == 0:
                    logger.info(f"指标生成进度: {idx + 1}/{len(codes)}（成功 {success}，失败 {failed}）")
                if task_id:
                    with task_lock:
                        if task_id in collection_tasks:
                            indicator_progress = 20 + int(((idx + 1) / max(1, len(codes))) * 79)
                            collection_tasks[task_id].update({
                                "progress": min(99, indicator_progress),
                                "warning_message": f"指标生成中（{idx + 1}/{len(codes)}）",
                            })
                try:
                    self._generate_indicators(
                        str(code), query_start, end_date, indicators,
                        do_commit=False, incremental_dates=incremental, market=market,
                    )
                    success += 1
                except Exception as e:
                    logger.error(f"为股票 {code} 生成指标失败: {e}")
                    failed += 1
                    self.session.rollback()
                # 每 BATCH_SIZE 只股票提交一次，显著减少磁盘 I/O
                if (idx + 1) % BATCH_SIZE == 0:
                    self.session.commit()
            self.session.commit()  # 最后一批
            logger.info(f"指标生成完成: 总数={len(codes)}, 成功={success}, 失败={failed}")
            return {'total': len(codes), 'success': success, 'failed': failed}
        except Exception as e:
            logger.error(f"批量生成指标失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 0}

    def compute_indicator_query_start(self, start_date: str, extended_start_days: int) -> str:
        """与 generate_indicators_for_date_range 一致：向前扩展查询起点（用于删除旧指标区间）。"""
        if extended_start_days <= 0:
            return start_date
        from datetime import datetime as dt, timedelta
        start_dt = dt.strptime(start_date, '%Y-%m-%d').date()
        return (start_dt - timedelta(days=extended_start_days)).strftime('%Y-%m-%d')

    def delete_indicator_rows_for_range(
        self,
        range_start: str,
        range_end: str,
        indicators: List[str],
        market: str = 'CN',
    ) -> None:
        """在重新写入前删除指定日期区间、市场类型的指标行（与本次要生成的指标类型一致）。"""
        if not indicators:
            return
        market_type = 'HK' if market == 'HK' else 'CN'
        table_map = {
            'ma': 'ma_indicators',
            'mavol': 'mavol_indicators',
            'macd': 'macd_indicators',
            'kdj': 'kdj_indicators',
            'rsi': 'rsi_indicators',
            'boll': 'boll_indicators',
            'pvfrs': 'mean_frequency_resonance_indicators',
            'icost': 'icost_indicators',
        }
        for key in indicators:
            tbl = table_map.get(key)
            if not tbl:
                continue
            try:
                self.session.execute(text(f"""
                    DELETE FROM {tbl}
                    WHERE market_type = :mt AND date >= :ds AND date <= :de
                """), {'mt': market_type, 'ds': range_start, 'de': range_end})
                logger.info(
                    f"已删除 {tbl} 中 market_type={market_type}、日期 [{range_start}, {range_end}] 的旧指标数据"
                )
            except Exception as e:
                logger.error(f"删除 {tbl} 旧指标失败: {e}")
                self.session.rollback()
                raise
        self.session.commit()

    def delete_indicator_rows_for_dates(
        self,
        dates: List[str],
        indicators: List[str],
        market: str = 'CN',
    ) -> None:
        """删除指定若干交易日的指标行（用于港股文件导入：只清本次导入日，不扫整段扩展区间）。"""
        if not indicators or not dates:
            return
        market_type = 'HK' if market == 'HK' else 'CN'
        table_map = {
            'ma': 'ma_indicators',
            'mavol': 'mavol_indicators',
            'macd': 'macd_indicators',
            'kdj': 'kdj_indicators',
            'rsi': 'rsi_indicators',
            'boll': 'boll_indicators',
            'pvfrs': 'mean_frequency_resonance_indicators',
            'icost': 'icost_indicators',
        }
        uniq_days = sorted(set(dates))
        for key in indicators:
            tbl = table_map.get(key)
            if not tbl:
                continue
            try:
                stmt = text(
                    f"DELETE FROM {tbl} WHERE market_type = :mt AND date IN :ds"
                ).bindparams(bindparam('ds', expanding=True))
                self.session.execute(stmt, {'mt': market_type, 'ds': uniq_days})
                logger.info(
                    f"已删除 {tbl} 中 market_type={market_type}、日期 IN ({len(uniq_days)} 天) 的旧指标数据"
                )
            except Exception as e:
                logger.error(f"按日期删除 {tbl} 旧指标失败: {e}")
                self.session.rollback()
                raise
        self.session.commit()
    
    def _generate_ma_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成MA指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            ma_calc = MACalculator()
            ma_df = ma_calc.calculate_ma_for_dataframe(df)
            for _, row in ma_df.iterrows():
                if pd.isna(row['date']):
                    continue
                d = row['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                data = {
                    'code': stock_code,
                    'date': d,
                    'market_type': market_type,
                    'ma5': row.get('ma5'), 'ma10': row.get('ma10'), 'ma20': row.get('ma20'),
                    'ma30': row.get('ma30'), 'ma60': row.get('ma60'), 'ma120': row.get('ma120'), 'ma200': row.get('ma200')
                }
                self.session.execute(text("""
                    INSERT INTO ma_indicators
                    (code, date, market_type, ma5, ma10, ma20, ma30, ma60, ma120, ma200)
                    VALUES (:code, :date, :market_type, :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma200)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        ma5 = EXCLUDED.ma5, ma10 = EXCLUDED.ma10, ma20 = EXCLUDED.ma20, ma30 = EXCLUDED.ma30,
                        ma60 = EXCLUDED.ma60, ma120 = EXCLUDED.ma120, ma200 = EXCLUDED.ma200
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} MA指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} MA指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def _generate_mavol_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成MAVOL指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            mavol_calc = MAVOLCalculator()
            mavol_df = mavol_calc.calculate_mavol_for_dataframe(df)
            for _, row in mavol_df.iterrows():
                if pd.isna(row['date']):
                    continue
                d = row['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                data = {
                    'code': stock_code, 'date': d, 'market_type': market_type,
                    'mavol5': row.get('mavol5'), 'mavol10': row.get('mavol10'), 'mavol20': row.get('mavol20'),
                    'mavol30': row.get('mavol30'), 'mavol60': row.get('mavol60'), 'mavol120': row.get('mavol120'), 'mavol200': row.get('mavol200')
                }
                self.session.execute(text("""
                    INSERT INTO mavol_indicators
                    (code, date, market_type, mavol5, mavol10, mavol20, mavol30, mavol60, mavol120, mavol200)
                    VALUES (:code, :date, :market_type, :mavol5, :mavol10, :mavol20, :mavol30, :mavol60, :mavol120, :mavol200)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        mavol5 = EXCLUDED.mavol5, mavol10 = EXCLUDED.mavol10, mavol20 = EXCLUDED.mavol20, mavol30 = EXCLUDED.mavol30,
                        mavol60 = EXCLUDED.mavol60, mavol120 = EXCLUDED.mavol120, mavol200 = EXCLUDED.mavol200
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} MAVOL指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} MAVOL指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def _generate_macd_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成MACD指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            from backend_core.utils.macd_calculator import MACDCalculator
            macd_calc = MACDCalculator()
            macd_data = macd_calc.calculate_macd_batch(df['close'].tolist())
            for i, macd_row in enumerate(macd_data):
                if i >= len(df):
                    break
                d = df.iloc[i]['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                data = {
                    'code': stock_code, 'date': d, 'market_type': market_type,
                    'dif': macd_row.get('dif'), 'dea': macd_row.get('dea'), 'macd': macd_row.get('macd'),
                    'ema12': macd_row.get('ema12'), 'ema26': macd_row.get('ema26')
                }
                self.session.execute(text("""
                    INSERT INTO macd_indicators (code, date, market_type, dif, dea, macd, ema12, ema26)
                    VALUES (:code, :date, :market_type, :dif, :dea, :macd, :ema12, :ema26)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET dif = EXCLUDED.dif, dea = EXCLUDED.dea, macd = EXCLUDED.macd, ema12 = EXCLUDED.ema12, ema26 = EXCLUDED.ema26
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} MACD指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} MACD指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def _generate_kdj_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成KDJ指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            kdj_calc = KDJCalculator()
            kdj_data = kdj_calc.calculate_kdj_batch(df['close'].tolist(), df['high'].tolist(), df['low'].tolist())
            for i, (_, row) in enumerate(df.iterrows()):
                if i >= len(kdj_data):
                    break
                d = row['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                kdj = kdj_data[i]
                data = {'code': stock_code, 'date': d, 'market_type': market_type, 'k': kdj.get('k'), 'd': kdj.get('d'), 'j': kdj.get('j'), 'rsv': kdj.get('rsv')}
                self.session.execute(text("""
                    INSERT INTO kdj_indicators (code, date, market_type, k, d, j, rsv)
                    VALUES (:code, :date, :market_type, :k, :d, :j, :rsv)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET k = EXCLUDED.k, d = EXCLUDED.d, j = EXCLUDED.j, rsv = EXCLUDED.rsv
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} KDJ指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} KDJ指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def _generate_rsi_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成RSI指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            rsi_calc = RSICalculator()
            rsi_data = rsi_calc.calculate_rsi_batch(df['close'].tolist())
            for i, (_, row) in enumerate(df.iterrows()):
                if i >= len(rsi_data):
                    break
                d = row['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                rsi = rsi_data[i]
                data = {'code': stock_code, 'date': d, 'market_type': market_type, 'rsi6': rsi.get('rsi6'), 'rsi12': rsi.get('rsi12'), 'rsi24': rsi.get('rsi24')}
                self.session.execute(text("""
                    INSERT INTO rsi_indicators (code, date, market_type, rsi6, rsi12, rsi24)
                    VALUES (:code, :date, :market_type, :rsi6, :rsi12, :rsi24)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET rsi6 = EXCLUDED.rsi6, rsi12 = EXCLUDED.rsi12, rsi24 = EXCLUDED.rsi24
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} RSI指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} RSI指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def _generate_boll_indicators(self, stock_code: str, df: pd.DataFrame, do_commit: bool = True, only_dates: Optional[set] = None, market_type: str = 'CN'):
        """生成BOLL指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            boll_calc = BOLLCalculator()
            boll_data = boll_calc.calculate_boll_batch(df['close'].tolist())
            for i, (_, row) in enumerate(df.iterrows()):
                if i >= len(boll_data):
                    break
                d = row['date'].strftime('%Y-%m-%d')
                if only_dates is not None and d not in only_dates:
                    continue
                boll = boll_data[i]
                data = {'code': stock_code, 'date': d, 'market_type': market_type, 'mid': boll.get('mid'), 'upper': boll.get('upper'), 'lower': boll.get('lower')}
                self.session.execute(text("""
                    INSERT INTO boll_indicators (code, date, market_type, mid, upper, lower)
                    VALUES (:code, :date, :market_type, :mid, :upper, :lower)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET mid = EXCLUDED.mid, upper = EXCLUDED.upper, lower = EXCLUDED.lower
                """), data)
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} BOLL指标生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} BOLL指标失败: {e}")
            if do_commit:
                self.session.rollback()

    def _generate_icost_indicators(
        self,
        stock_code: str,
        end_date: str,
        do_commit: bool = True,
        only_dates: Optional[set] = None,
        market: str = 'CN',
    ):
        """无穷成本均线：自该股最早行情至 end_date 的累计成交额/成交量；仅写入 only_dates（增量）或全部。"""
        try:
            from backend_core.utils.infinite_cost_calculator import calculate_infinite_cost_for_dataframe, icost_rows_for_db

            source_table = "historical_quotes_hk" if market == 'HK' else "historical_quotes"
            market_type = 'HK' if market == 'HK' else 'CN'

            result = self.session.execute(
                text(f"""
                SELECT date, open, high, low, close, volume, amount, turnover_rate
                FROM {source_table}
                WHERE code = :stock_code AND date <= :end_date
                ORDER BY date
            """),
                {'stock_code': stock_code, 'end_date': end_date},
            )
            rows = result.fetchall()
            if not rows:
                return
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            icost_df = calculate_infinite_cost_for_dataframe(df)
            if icost_df.empty:
                return
            db_rows = icost_rows_for_db(icost_df)
            for row in db_rows:
                d = row.get('date') or ''
                if only_dates is not None and d not in only_dates:
                    continue
                data = {
                    'code': stock_code,
                    'date': d,
                    'market_type': market_type,
                    'ic_price': row.get('ic_price'),
                    'cum_amount': row.get('cum_amount'),
                    'cum_volume': row.get('cum_volume'),
                }
                self.session.execute(
                    text("""
                    INSERT INTO icost_indicators (code, date, market_type, ic_price, cum_amount, cum_volume)
                    VALUES (:code, :date, :market_type, :ic_price, :cum_amount, :cum_volume)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        ic_price = EXCLUDED.ic_price,
                        cum_amount = EXCLUDED.cum_amount,
                        cum_volume = EXCLUDED.cum_volume
                """),
                    data,
                )
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} 无穷成本均线(icost)生成完成")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} icost 指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    # PVFRS 至少需要约 21 个交易日；回退查询最多取这么多条以防单表过大
    PVFRS_MIN_ROWS = 21
    PVFRS_MAX_LOOKBACK_ROWS = 400

    def _generate_pvfrs_indicators(self, stock_code: str, start_date: str, end_date: str, do_commit: bool = True, only_dates: Optional[set] = None, market: str = 'CN'):
        """生成PVFRS指标。do_commit=False 时由调用方批量提交。only_dates 非空时仅写入这些日期（增量）。"""
        try:
            from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
            
            if do_commit:
                logger.info(f"开始为股票 {stock_code} ({market}) 生成PVFRS指标")

            # 端口历史行情表切换
            source_table = "historical_quotes_hk" if market == 'HK' else "historical_quotes"
            market_type = 'HK' if market == 'HK' else 'CN'
            
            result = self.session.execute(text(f"""
                SELECT date, close, volume
                FROM {source_table} 
                WHERE code = :stock_code 
                AND date >= :start_date 
                AND date <= :end_date
                ORDER BY date
            """), {
                'stock_code': stock_code,
                'start_date': start_date,
                'end_date': end_date
            })
            
            history_rows = result.fetchall()
            # 窗口内不足 21 条时：回退为取 end_date 及之前的全部可用行情（最多 PVFRS_MAX_LOOKBACK_ROWS），
            # 避免「扩展起点」之后数据稀疏但库中更早仍有足够日线时仍无法计算。
            if len(history_rows) < self.PVFRS_MIN_ROWS:
                result_fb = self.session.execute(text(f"""
                    SELECT date, close, volume FROM (
                        SELECT date, close, volume
                        FROM {source_table}
                        WHERE code = :stock_code AND date <= :end_date
                        ORDER BY date DESC
                        LIMIT :lim
                    ) AS pvfrs_hist
                    ORDER BY date ASC
                """), {
                    'stock_code': stock_code,
                    'end_date': end_date,
                    'lim': self.PVFRS_MAX_LOOKBACK_ROWS,
                })
                history_rows = result_fb.fetchall()

            if not history_rows or len(history_rows) < self.PVFRS_MIN_ROWS:
                logger.debug(
                    f"股票 {stock_code} 历史数据不足（当前 {len(history_rows or [])} 条），"
                    f"跳过 PVFRS（需至少 {self.PVFRS_MIN_ROWS} 个交易日）"
                )
                return
            
            class HistoryRow:
                def __init__(self, date, close, volume):
                    self.date = date
                    self.close = close
                    self.volume = volume
            
            orm_rows = [HistoryRow(row[0], row[1], row[2]) for row in history_rows]
            calculator = MeanFrequencyResonanceCalculator()
            pvfrs_df = calculator.calculate_for_dataframe(orm_rows)
            
            if pvfrs_df.empty:
                logger.warning(f"股票 {stock_code} PVFRS计算结果为空")
                return
            
            for _, row in pvfrs_df.iterrows():
                d = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
                if only_dates is not None and d not in only_dates:
                    continue
                data = {
                    'code': stock_code,
                    'date': d,
                    'market_type': market_type,
                    'macro_displacement_delta': row.get('macro_displacement_delta'),
                    'amplitude': row.get('amplitude'),
                    'ratio_d20': row.get('ratio_d20'),
                    'ratio_d1': row.get('ratio_d1'),
                    'instant_deviation': row.get('instant_deviation'),
                    'rising_days_z': row.get('rising_days_z'),
                    'falling_days_f': row.get('falling_days_f'),
                    'efficiency_m20_minus_m': row.get('efficiency_m20_minus_m'),
                    'ma20_d': row.get('ma20_d'),
                    'mavol20_m': row.get('mavol20_m'),
                    'bias': row.get('bias')
                }
                
                # 插入或更新PVFRS指标数据
                self.session.execute(text("""
                    INSERT INTO mean_frequency_resonance_indicators
                    (code, date, market_type, macro_displacement_delta, amplitude, ratio_d20, ratio_d1,
                     instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m, 
                     ma20_d, mavol20_m, bias)
                    VALUES (:code, :date, :market_type, :macro_displacement_delta, :amplitude, :ratio_d20, :ratio_d1,
                            :instant_deviation, :rising_days_z, :falling_days_f, :efficiency_m20_minus_m,
                            :ma20_d, :mavol20_m, :bias)
                    ON CONFLICT (code, date, market_type) DO UPDATE SET
                        macro_displacement_delta = EXCLUDED.macro_displacement_delta,
                        amplitude = EXCLUDED.amplitude,
                        ratio_d20 = EXCLUDED.ratio_d20,
                        ratio_d1 = EXCLUDED.ratio_d1,
                        instant_deviation = EXCLUDED.instant_deviation,
                        rising_days_z = EXCLUDED.rising_days_z,
                        falling_days_f = EXCLUDED.falling_days_f,
                        efficiency_m20_minus_m = EXCLUDED.efficiency_m20_minus_m,
                        ma20_d = EXCLUDED.ma20_d,
                        mavol20_m = EXCLUDED.mavol20_m,
                        bias = EXCLUDED.bias
                """), data)
            
            if do_commit:
                self.session.commit()
                logger.info(f"股票 {stock_code} PVFRS指标生成完成，共 {len(pvfrs_df)} 条记录")
        except Exception as e:
            logger.error(f"生成股票 {stock_code} PVFRS指标失败: {e}")
            if do_commit:
                self.session.rollback()
    
    def collect_single_hk_stock_data(self, stock_code: str, stock_name: str, start_date: str, end_date: str, is_full_collection: bool = False, force_update: bool = False) -> bool:
        """
        采集单只港股的历史数据
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            start_date: 开始日期
            end_date: 结束日期
            is_full_collection: 是否全量采集模式
            force_update: 是否强制更新（如果为True，即使数据已存在也会重新采集并更新）
        """
        # 名称含「退」的股票（退市等）不再写入历史行情表
        if stock_name and '退' in stock_name:
            logger.info(f"跳过名称含「退」的港股: {stock_code} {stock_name}")
            return True
        try:
            # 检查已存在的数据（仅在非强制更新模式下）
            existing_dates = []
            if not force_update:
                result = self.session.execute(text("""
                    SELECT date 
                    FROM historical_quotes_hk 
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
                if existing_dates:
                    logger.debug(f"港股 {stock_code} 在 {start_date} 到 {end_date} 期间已有 {len(existing_dates)} 天数据")
            else:
                logger.info(f"港股 {stock_code} 强制更新模式：将重新采集并更新所有数据")
            
            # 使用akshare获取历史数据
            logger.info(f"开始采集港股 {stock_code} 的历史数据...")
            
            df = None
            source = 'akshare_eastmoney'
            
            # 1. 尝试使用 stock_hk_hist (EastMoney)
            try:
                start_date_str = pd.to_datetime(start_date).strftime('%Y%m%d')
                end_date_str = pd.to_datetime(end_date).strftime('%Y%m%d')
                
                # 添加重试机制
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        df = ak.stock_hk_hist(
                            symbol=stock_code,
                            period='daily',
                            start_date=start_date_str,
                            end_date=end_date_str,
                            adjust=""
                        )
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(1)
                        else:
                            raise e

                # 重命名列以统一格式
                if df is not None and not df.empty:
                    column_map = {
                        '日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low',
                        '成交量': 'volume', '成交额': 'amount', '涨跌额': 'change_amount', 
                        '涨跌幅': 'change_percent', '换手率': 'turnover_rate', '振幅': 'amplitude'
                    }
                    df = df.rename(columns=column_map)
                    
            except Exception as e:
                logger.warning(f"EastMoney接口采集失败，尝试Sina接口: {e}")
                source = 'akshare_sina'
                try:
                    # 2. 尝试使用 stock_hk_daily (Sina)
                    df = ak.stock_hk_daily(symbol=stock_code, adjust="")
                    
                    if df is not None and not df.empty:
                        # Sina返回: date, open, high, low, close, volume
                        # 转换数据类型
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        df = df.sort_values('date')
                        
                        # 计算衍生指标
                        df['pre_close'] = df['close'].shift(1)
                        df['change_amount'] = df['close'] - df['pre_close']
                        df['change_percent'] = (df['change_amount'] / df['pre_close']) * 100
                        df['amplitude'] = ((df['high'] - df['low']) / df['pre_close']) * 100
                        df['amount'] = None 
                        df['turnover_rate'] = None 
                        
                        # 过滤日期范围
                        df['date'] = pd.to_datetime(df['date'])
                        mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
                        df = df.loc[mask]
                        
                except Exception as e2:
                    logger.error(f"Sina接口采集也失败: {e2}")
                    self.failed_count += 1
                    self.failed_stocks.append(f"{stock_code}: {str(e)} | {str(e2)}")
                    return False
            
            if df is None or df.empty:
                logger.warning(f"港股 {stock_code} 在指定日期范围内没有数据")
                return True
            
            logger.info(f"港股 {stock_code} 采集到 {len(df)} 条数据 ({source})")
            
            # 计算多周期涨跌幅
            if 'date' in df.columns:
                df = df.sort_values('date')
                if 'close' in df.columns:
                    df['five_day_change_percent'] = df['close'].pct_change(periods=5, fill_method=None) * 100
                    df['ten_day_change_percent'] = df['close'].pct_change(periods=10, fill_method=None) * 100
                    df['thirty_day_change_percent'] = df['close'].pct_change(periods=30, fill_method=None) * 100
                    df['sixty_day_change_percent'] = df['close'].pct_change(periods=60, fill_method=None) * 100
            
            # 处理数据并插入数据库
            success_count = 0
            skip_count = 0
            
            for _, row in df.iterrows():
                try:
                    # 转换日期格式
                    date_val = row['date']
                    if hasattr(date_val, 'strftime'):
                        trade_date = date_val.strftime('%Y-%m-%d')
                    else:
                        trade_date = str(date_val)
                        if len(trade_date) == 8:
                            trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                    
                    # 检查是否已存在（仅在非强制更新模式下）
                    if not force_update and trade_date in existing_dates:
                        skip_count += 1
                        continue

                    # 节假日检查：若为 HK 市场节假日则跳过
                    if self.is_holiday('HK', trade_date):
                        logger.debug(f"港股节假日跳过: {stock_code} {trade_date}")
                        skip_count += 1
                        continue
                        
                    
                    def get_val(row, key, default=None):
                        val = row.get(key)
                        if pd.isna(val) or val == '':
                            return default
                        return float(val)

                    data = {
                        'code': stock_code,
                        'ts_code': stock_code,
                        'name': stock_name,
                        'english_name': None,
                        'date': trade_date,
                        'open': get_val(row, 'open'),
                        'high': get_val(row, 'high'),
                        'low': get_val(row, 'low'),
                        'close': get_val(row, 'close'),
                        'pre_close': get_val(row, 'pre_close'), 
                        'volume': get_val(row, 'volume'),
                        'amount': get_val(row, 'amount'),
                        'change_amount': get_val(row, 'change_amount'),
                        'change_percent': get_val(row, 'change_percent'),
                        'turnover_rate': get_val(row, 'turnover_rate'),
                        'amplitude': get_val(row, 'amplitude'),
                        'five_day_change_percent': get_val(row, 'five_day_change_percent'),
                        'ten_day_change_percent': get_val(row, 'ten_day_change_percent'),
                        'thirty_day_change_percent': get_val(row, 'thirty_day_change_percent'),
                        'sixty_day_change_percent': get_val(row, 'sixty_day_change_percent'),
                        'collected_source': source,
                        'collected_date': datetime.now().isoformat()
                    }
                    
                    # 插入或更新数据（使用ON CONFLICT DO UPDATE实现强制更新）
                    self.session.execute(text("""
                        INSERT INTO historical_quotes_hk
                        (code, ts_code, name, english_name, date, open, high, low, close, pre_close, 
                         volume, amount, change_amount, change_percent, turnover_rate, amplitude,
                         five_day_change_percent, ten_day_change_percent, thirty_day_change_percent, sixty_day_change_percent,
                         collected_source, collected_date)
                        VALUES (:code, :ts_code, :name, :english_name, :date, :open, :high, :low, :close, :pre_close,
                                :volume, :amount, :change_amount, :change_percent, :turnover_rate, :amplitude,
                                :five_day_change_percent, :ten_day_change_percent, :thirty_day_change_percent, :sixty_day_change_percent,
                                :collected_source, :collected_date)
                        ON CONFLICT (code, date) DO UPDATE SET
                            ts_code = EXCLUDED.ts_code,
                            name = EXCLUDED.name,
                            english_name = EXCLUDED.english_name,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            pre_close = EXCLUDED.pre_close,
                            volume = EXCLUDED.volume,
                            amount = EXCLUDED.amount,
                            change_amount = EXCLUDED.change_amount,
                            change_percent = EXCLUDED.change_percent,
                            turnover_rate = EXCLUDED.turnover_rate,
                            amplitude = EXCLUDED.amplitude,
                            five_day_change_percent = EXCLUDED.five_day_change_percent,
                            ten_day_change_percent = EXCLUDED.ten_day_change_percent,
                            thirty_day_change_percent = EXCLUDED.thirty_day_change_percent,
                            sixty_day_change_percent = EXCLUDED.sixty_day_change_percent,
                            collected_source = EXCLUDED.collected_source,
                            collected_date = EXCLUDED.collected_date
                    """), data)
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"处理港股 {stock_code} 日期 {trade_date} 数据时出错: {e}")
                    continue
            
            # 提交事务
            self.session.commit()
            
            self.collected_count += success_count
            self.skipped_count += skip_count
            
            logger.info(f"港股 {stock_code} 处理完成: 新增 {success_count} 条，跳过 {skip_count} 条")
            
            # 如果是全量采集模式，更新该港股的全量采集标志
            if is_full_collection:
                self._update_hk_full_collection_flag(stock_code, start_date, end_date)
            
            # 添加随机延迟
            time.sleep(random.uniform(0.5, 1.5))
            
            return True
            
        except Exception as e:
            logger.error(f"采集港股 {stock_code} 历史数据失败: {e}")
            self.failed_count += 1
            self.failed_stocks.append(f"{stock_code}: {str(e)}")
            return False
    
    def collect_historical_data(self, start_date: str, end_date: str, stock_codes: Optional[List[str]] = None, full_collection_mode: bool = False, market: str = 'CN', force_update: bool = False, indicators: Optional[List[str]] = None) -> Dict[str, any]:
        """批量采集历史行情数据"""
        try:
            logger.info(f"开始批量采集历史行情数据: {start_date} 到 {end_date}, 市场: {market}")
            
            # 获取股票列表
            if stock_codes:
                stocks = []
                for code in stock_codes:
                    result = self.session.execute(text("""
                        SELECT code, name FROM stock_basic_info WHERE code = :code
                    """), {'code': code})
                    row = result.fetchone()
                    if row:
                        stocks.append({'code': str(row[0]), 'name': row[1] if row[1] else ''})
                    else:
                        # 尝试从港股表查询
                        result_hk = self.session.execute(text("""
                            SELECT code, name FROM stock_basic_info_hk WHERE code = :code
                        """), {'code': code})
                        row_hk = result_hk.fetchone()
                        if row_hk:
                            stocks.append({'code': str(row_hk[0]), 'name': row_hk[1] if row_hk[1] else ''})
                        else:
                            # 如果是5位数字代码，尝试作为港股采集
                            if len(code) == 5 and code.isdigit():
                                logger.info(f"股票代码 {code} 未在基础信息表中找到，尝试作为港股采集")
                                stocks.append({'code': code, 'name': code})
                            else:
                                logger.warning(f"股票代码 {code} 在stock_basic_info和stock_basic_info_hk表中都不存在")
            else:
                # 根据模式决定获取哪些股票
                if full_collection_mode:
                    if market == 'HK':
                        # 港股全量采集：只获取未完成全量采集的港股
                        stocks = self.get_hk_stock_list(only_uncompleted=True)
                        logger.info(f"港股全量采集模式：获取到 {len(stocks)} 只未完成全量采集的港股")
                    else:
                        # A股全量采集：只获取未完成全量采集的股票
                        stocks = self.get_stock_list(only_uncompleted=True)
                        logger.info(f"A股全量采集模式：获取到 {len(stocks)} 只未完成全量采集的股票")
                else:
                    # 普通模式：获取所有股票 (默认A股)
                    if market == 'HK':
                        stocks = self.get_hk_stock_list()
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
                
                if len(stock['code']) == 5:
                    # 港股 (5位代码)
                    # 在全量采集模式下，检查是否已采集过
                    if full_collection_mode and market == 'HK':
                        # 检查该港股是否已完成全量采集
                        check_result = self.session.execute(text("""
                            SELECT full_collection_completed 
                            FROM stock_basic_info_hk 
                            WHERE code = :code
                        """), {'code': stock['code']})
                        row = check_result.fetchone()
                        if row and row[0]:
                            logger.info(f"港股 {stock['code']} 已完成全量采集，跳过")
                            self.skipped_count += 1
                            continue
                    
                    if self.collect_single_hk_stock_data(stock['code'], stock['name'], start_date, end_date, full_collection_mode and market == 'HK', force_update):
                        success_count += 1
                else:
                    # A股
                    if self.collect_single_stock_data(stock['code'], stock['name'], start_date, end_date, indicators):
                        success_count += 1
                
                # 休眠控制
                if market == 'HK':
                    time.sleep(5)  # 港股每次采集后休眠5秒
                else:
                    time.sleep(20)  # A股保持20秒 (或者根据需要调整)
                
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
    
    def _update_hk_full_collection_flag(self, stock_code: str, start_date: str, end_date: str):
        """更新港股的全量采集标志"""
        try:
            # 更新港股全量采集标志
            self.session.execute(text("""
                UPDATE stock_basic_info_hk 
                SET full_collection_completed = TRUE,
                    full_collection_date = CURRENT_TIMESTAMP,
                    full_collection_start_date = :start_date,
                    full_collection_end_date = :end_date
                WHERE code = :stock_code
            """), {
                'stock_code': stock_code,
                'start_date': start_date,
                'end_date': end_date
            })
            
            self.session.commit()
            logger.info(f"已更新港股 {stock_code} 的全量采集标志")
            
        except Exception as e:
            logger.error(f"更新港股 {stock_code} 全量采集标志失败: {e}")
            # 不抛出异常，避免影响主流程
    
    def collect_hk_historical_from_realtime(self, start_date: str, end_date: str) -> Dict[str, any]:
        """从港股实时行情表同步到历史行情表"""
        try:
            from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector
            collector = HKHistoricalQuoteCollector()
            
            # 生成日期范围
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            date_range = pd.date_range(start, end)
            
            total_dates = len(date_range)
            success_count = 0
            
            for i, current_date in enumerate(date_range):
                date_str = current_date.strftime('%Y%m%d')
                logger.info(f"[{i+1}/{total_dates}] 正在从实时行情同步港股历史数据: {date_str}")
                day_start = time.time()
                try:
                    if collector.collect_historical_quotes(date_str):
                        success_count += 1
                        logger.info(f"日期 {date_str} 同步完成，耗时: {time.time() - day_start:.2f}s")
                    else:
                        logger.warning(f"日期 {date_str} 同步未发现数据或执行失败，耗时: {time.time() - day_start:.2f}s")
                except Exception as e:
                    logger.error(f"同步日期 {date_str} 失败: {e}, 耗时: {time.time() - day_start:.2f}s")
            
            return {
                'total': total_dates,
                'success': success_count,
                'failed': total_dates - success_count,
                'collected': 0, # 这里难以精确统计条数，除非修改hk_historical
                'skipped': 0,
                'failed_details': []
            }
        except Exception as e:
            logger.error(f"从实时行情同步港股历史数据失败: {e}")
            return {
                'total': 0,
                'success': 0,
                'failed': 1,
                'collected': 0,
                'skipped': 0,
                'failed_details': [str(e)]
            }

    def collect_cn_historical_from_realtime(self, start_date: str, end_date: str) -> Dict[str, any]:
        """从 A 股实时行情表同步到历史行情表（行为与港股 sync 类似）"""
        try:
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            date_range = pd.date_range(start, end)

            total_dates = len(date_range)
            success_count = 0

            for i, current_date in enumerate(date_range):
                trade_date = current_date.strftime('%Y-%m-%d')
                logger.info(f"[{i+1}/{total_dates}] 正在从实时行情同步A股历史数据: {trade_date}")
                day_start = time.time()
                try:
                    # 从实时行情表获取当日全部A股数据
                    result = self.session.execute(text("""
                        SELECT code, name, open, high, low, current_price, pre_close,
                               volume, amount, change_percent, turnover_rate
                        FROM stock_realtime_quote
                        WHERE trade_date = :trade_date
                    """), {'trade_date': trade_date})
                    rows = result.fetchall()

                    if not rows:
                        logger.warning(f"日期 {trade_date} 在实时行情表中无数据")
                        continue

                    for row in rows:
                        code = str(row[0]).strip()
                        name = (row[1] or '').strip() if row[1] else code
                        # 名称含「退」的股票不再写入历史行情表
                        if '退' in (name or ''):
                            continue
                        open_price = row[2]
                        high = row[3]
                        low = row[4]
                        close = row[5]
                        pre_close = row[6]
                        volume = row[7]
                        amount = row[8]
                        change_percent = row[9]
                        turnover_rate = row[10]

                        change = None
                        try:
                            if close is not None and pre_close is not None:
                                change = float(close) - float(pre_close)
                        except Exception:
                            change = None

                        self.session.execute(text("""
                            INSERT INTO historical_quotes
                            (code, name, market, date, open, high, low, close,
                             pre_close, volume, amount, change_percent, change, turnover_rate,
                             collected_source, collected_date)
                            VALUES
                            (:code, :name, :market, :date, :open, :high, :low, :close,
                             :pre_close, :volume, :amount, :change_percent, :change, :turnover_rate,
                             :collected_source, :collected_date)
                            ON CONFLICT (code, date) DO UPDATE SET
                                name = EXCLUDED.name,
                                market = EXCLUDED.market,
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                pre_close = EXCLUDED.pre_close,
                                volume = EXCLUDED.volume,
                                amount = EXCLUDED.amount,
                                change_percent = EXCLUDED.change_percent,
                                change = EXCLUDED.change,
                                turnover_rate = EXCLUDED.turnover_rate,
                                collected_source = EXCLUDED.collected_source,
                                collected_date = EXCLUDED.collected_date
                        """), {
                            'code': code,
                            'name': name,
                            'market': 'A股',
                            'date': trade_date,
                            'open': open_price,
                            'high': high,
                            'low': low,
                            'close': close,
                            'pre_close': pre_close,
                            'volume': volume,
                            'amount': amount,
                            'change_percent': change_percent,
                            'change': change,
                            'turnover_rate': turnover_rate,
                            'collected_source': 'realtime_sync',
                            'collected_date': datetime.now()
                        })

                    self.session.commit()
                    success_count += 1
                    logger.info(f"日期 {trade_date} A股同步完成，耗时: {time.time() - day_start:.2f}s，记录数: {len(rows)}")
                except Exception as e:
                    self.session.rollback()
                    logger.error(f"同步 A股日期 {trade_date} 失败: {e}, 耗时: {time.time() - day_start:.2f}s")

            return {
                'total': total_dates,
                'success': success_count,
                'failed': total_dates - success_count,
                'collected': 0,
                'skipped': 0,
                'failed_details': []
            }
        except Exception as e:
            logger.error(f"从实时行情同步A股历史数据失败: {e}")
            return {
                'total': 0,
                'success': 0,
                'failed': 1,
                'collected': 0,
                'skipped': 0,
                'failed_details': [str(e)]
            }

    def update_multi_day_change_for_date_range(self, start_date: str, end_date: str):
        """
        为指定日期范围内的 A 股历史数据，批量计算并更新
        5天、10天、30天、60天涨跌百分比。
        """
        try:
            import pandas as pd

            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            # 向前多取一段时间，保证有足够的历史数据计算 60 天涨跌
            extended_start = start - pd.Timedelta(days=120)

            logger.info(f"开始批量计算 {start_date} ~ {end_date} 的 5/10/30/60 天涨跌%（扩展查询起始: {extended_start.date()}）")

            result = self.session.execute(text("""
                SELECT code, date, close
                FROM historical_quotes
                WHERE date >= :extended_start AND date <= :end_date
                ORDER BY code, date
            """), {
                'extended_start': extended_start.date().isoformat(),
                'end_date': end.date().isoformat(),
            })

            rows = result.fetchall()
            if not rows:
                logger.warning("指定日期范围内没有历史数据，跳过多周期涨跌计算")
                return

            df = pd.DataFrame(rows, columns=['code', 'date', 'close'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(['code', 'date'])

            # 分组按代码计算多周期涨跌
            def _calc_changes(group: pd.DataFrame) -> pd.DataFrame:
                group = group.sort_values('date')
                group['five_day_change_percent'] = group['close'].pct_change(periods=5, fill_method=None) * 100
                group['ten_day_change_percent'] = group['close'].pct_change(periods=10, fill_method=None) * 100
                group['thirty_day_change_percent'] = group['close'].pct_change(periods=30, fill_method=None) * 100
                group['sixty_day_change_percent'] = group['close'].pct_change(periods=60, fill_method=None) * 100
                
                # 处理由于价格为 0 导致的无穷大数值 (inf)，数据库 numeric 字段无法存储
                import numpy as np
                group = group.replace([np.inf, -np.inf], np.nan)
                return group

            df = df.groupby('code', group_keys=False).apply(_calc_changes)

            # 只更新目标日期范围内的记录
            mask = (df['date'] >= start) & (df['date'] <= end)
            df_update = df.loc[mask].dropna(subset=['close'])

            updated = 0
            total_rows = len(df_update)
            if total_rows > 0:
                logger.info(f"多周期涨跌%更新: 共 {total_rows} 条，每 100 条打印进度")
            for _, row in df_update.iterrows():
                self.session.execute(text("""
                    UPDATE historical_quotes
                    SET
                        five_day_change_percent = :five_day_change_percent,
                        ten_day_change_percent = :ten_day_change_percent,
                        thirty_day_change_percent = :thirty_day_change_percent,
                        sixty_day_change_percent = :sixty_day_change_percent
                    WHERE code = :code AND date = :date
                """), {
                    'five_day_change_percent': float(row['five_day_change_percent']) if pd.notna(row['five_day_change_percent']) else None,
                    'ten_day_change_percent': float(row['ten_day_change_percent']) if pd.notna(row['ten_day_change_percent']) else None,
                    'thirty_day_change_percent': float(row['thirty_day_change_percent']) if pd.notna(row['thirty_day_change_percent']) else None,
                    'sixty_day_change_percent': float(row['sixty_day_change_percent']) if pd.notna(row['sixty_day_change_percent']) else None,
                    'code': str(row['code']),
                    'date': row['date'].date().isoformat(),
                })
                updated += 1
                if updated % 100 == 0:
                    logger.info(f"多周期涨跌%更新进度: {updated}/{total_rows}")

            self.session.commit()
            logger.info(f"多周期涨跌%计算完成，更新记录数: {updated}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"批量计算多周期涨跌%失败: {e}")


def run_realtime_historical_collection_task(
    task_id: str,
    start_date: str,
    end_date: str,
    indicators: Optional[List[str]] = None,
):
    """从实时行情表同步 A 股历史数据（后台任务），并可选生成技术指标"""
    global current_task_id
    try:
        logger.info(f"开始执行实时行情表历史采集任务: {task_id}")

        from backend_api.database import SessionLocal
        db = SessionLocal()

        try:
            collector = AkshareDataCollector(db)

            # 1. 从实时行情表同步到 historical_quotes
            result_sync = collector.collect_cn_historical_from_realtime(start_date, end_date)

            # 2. 生成技术指标（MA/MAVOL/KDJ/RSI/BOLL/PVFRS 等）；未勾选时默认生成全部
            indicator_result = {'total': 0, 'success': 0, 'failed': 0}
            indicators_to_run = indicators if indicators else ['ma', 'mavol', 'kdj', 'rsi', 'boll', 'macd', 'pvfrs']
            logger.info(f"实时行情表历史采集完成，开始生成指标: {indicators_to_run}（扩展历史以计算 MA200 等）")
            indicator_result = collector.generate_indicators_for_date_range(
                start_date, end_date, indicators_to_run, extended_start_days=300
            )

            # 3. 计算 5/10/30/60 天涨跌百分比
            collector.update_multi_day_change_for_date_range(start_date, end_date)

            # 汇总结果
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "status": "completed",
                        "progress": 100,
                        "processed_stocks": indicator_result.get("total", 0),
                        "success_count": indicator_result.get("success", 0),
                        "failed_count": indicator_result.get("failed", 0),
                        "collected_count": result_sync.get("collected", 0),
                        "skipped_count": result_sync.get("skipped", 0),
                        "end_time": datetime.now(),
                        "failed_details": result_sync.get("failed_details", []),
                    })

            logger.info(f"实时行情表历史采集任务完成: {task_id}")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"实时行情表历史采集任务执行失败: {task_id}, 错误: {e}")
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error_message": str(e)
                })
    finally:
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")


@router.post("/realtime-historical", response_model=DataCollectionResponse)
async def start_realtime_historical_collection(
    request: RealtimeHistoricalCollectionRequest,
    background_tasks: BackgroundTasks,
):
    """启动从实时行情表同步 A 股历史数据的任务（支持指标生成）"""
    global current_task_id
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 检查是否有其他任务正在运行
        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail="已有采集任务正在运行，请等待完成后再启动新任务")

        # 生成任务ID
        task_id = f"realtime_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"

        # 初始化任务状态
        with task_lock:
            collection_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total_stocks": 0,
                "processed_stocks": 0,
                "success_count": 0,
                "failed_count": 0,
                "collected_count": 0,
                "skipped_count": 0,
                "start_time": datetime.now(),
                "end_time": None,
                "error_message": None,
                "warning_message": None,
                "failed_details": []
            }

        # 设置当前任务ID
        with task_execution_lock:
            current_task_id = task_id

        # 启动后台任务
        background_tasks.add_task(
            run_realtime_historical_collection_task,
            task_id,
            request.start_date,
            request.end_date,
            request.indicators,
        )

        logger.info(f"启动实时行情表历史采集任务: {task_id}")

        return DataCollectionResponse(
            task_id=task_id,
            status="started",
            message="实时行情表历史采集任务已启动",
            start_date=request.start_date,
            end_date=request.end_date,
            market="CN",
        )

    except Exception as e:
        logger.error(f"启动实时行情表历史采集任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动采集任务失败: {str(e)}")

def run_file_historical_collection_task(
    task_id: str,
    start_date: str,
    end_date: str,
    force_update: bool = False,
    indicators: Optional[List[str]] = None,
    file_type: str = 'txt',
):
    """从本地文件采集A股历史数据（后台任务）"""
    global current_task_id
    try:
        logger.info(f"开始执行历史数据采集-文件任务: {task_id}")
        
        from backend_core.data_collectors.tushare.historical_import_from_file import HistoricalQuoteImportFromFileCollector
        collector = HistoricalQuoteImportFromFileCollector()
        from backend_api.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 文件采集按天循环
            import pandas as pd
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            date_range = pd.date_range(start, end)
            
            total_dates = len(date_range)
            success_dates = 0
            has_indicators = bool(indicators)
            
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "total_stocks": total_dates,  # 文件导入阶段按天统计
                        "progress": 0,
                        "warning_message": "文件导入准备中",
                    })
            
            for i, current_date in enumerate(date_range):
                date_str = current_date.strftime('%Y%m%d')
                logger.info(f"[{i+1}/{total_dates}] 正在从文件同步A股历史数据: {date_str}")
                
                try:
                    if collector.collect_historical_quotes(date_str, file_type, force_update):
                        success_dates += 1
                except Exception as e:
                    logger.error(f"同步日期 {date_str} 失败: {e}")
                
                with task_lock:
                    if task_id in collection_tasks:
                        import_weight = 20 if has_indicators else 100
                        import_progress = int(((i + 1) / max(1, total_dates)) * import_weight)
                        collection_tasks[task_id].update({
                            "processed_stocks": i + 1,
                            "progress": min(import_weight, import_progress),
                            "warning_message": f"文件导入中（{i + 1}/{total_dates}）",
                        })
            
            # 生成技术指标
            indicator_result = {'total': 0, 'success': 0, 'failed': 0}
            if indicators:
                ak_collector = AkshareDataCollector(db)
                from pandas import date_range
                only_write_dates = [d.strftime("%Y-%m-%d") for d in date_range(start, end)]
                dynamic_lookback_days = ak_collector.compute_dynamic_indicator_lookback_days(indicators)
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id].update({
                            "progress": 20,
                            "warning_message": "文件导入完成，开始生成指标",
                        })
                logger.info(
                    f"历史数据(文件)采集完成，开始生成指标: {indicators}；"
                    f"动态前扩={dynamic_lookback_days}天；写入仅限区间 {start_date}~{end_date}"
                )
                indicator_result = ak_collector.generate_indicators_for_date_range(
                    start_date,
                    end_date,
                    indicators,
                    extended_start_days=dynamic_lookback_days,
                    only_write_dates=only_write_dates,
                    task_id=task_id,
                )
            
                # 计算 5/10/30/60 天涨跌百分比
                ak_collector.update_multi_day_change_for_date_range(start_date, end_date)
            
            # 汇总结果
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "status": "completed",
                        "progress": 100,
                        "success_count": success_dates,
                        "failed_count": total_dates - success_dates,
                        "end_time": datetime.now(),
                        "warning_message": None,
                    })
            
            logger.info(f"历史数据采集-文件任务完成: {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"历史数据采集-文件任务执行失败: {task_id}, 错误: {e}")
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error_message": str(e)
                })
    finally:
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")

def run_hk_file_historical_collection_task(
    task_id: str,
    start_date: str,
    end_date: str,
    force_update: bool = False,
    indicators: Optional[List[str]] = None,
    file_type: str = 'txt',
):
    """从本地文件采集港股历史数据（后台任务）"""
    global current_task_id
    try:
        logger.info(f"开始执行港股历史数据采集-文件任务: {task_id}")
        
        from backend_core.data_collectors.akshare.hk_historical_import_from_file import HKHistoricalQuoteImportFromFileCollector
        collector = HKHistoricalQuoteImportFromFileCollector()
        from backend_api.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 文件采集按天循环
            import pandas as pd
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            date_range = pd.date_range(start, end)
            
            total_dates = len(date_range)
            success_dates = 0
            imported_dates: List[str] = []  # 采集成功的交易日 YYYY-MM-DD，指标仅写入这些日期
            has_indicators = bool(indicators)
            
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "total_stocks": total_dates,  # 文件导入阶段按天统计
                        "progress": 0,
                        "warning_message": "文件导入准备中",
                    })
            
            for i, current_date in enumerate(date_range):
                date_str = current_date.strftime('%Y%m%d')
                logger.info(f"[{i+1}/{total_dates}] 正在从文件同步港股历史数据: {date_str}")
                
                try:
                    if collector.collect_historical_quotes(date_str, file_type, force_update):
                        success_dates += 1
                        imported_dates.append(current_date.strftime('%Y-%m-%d'))
                except Exception as e:
                    logger.error(f"同步日期 {date_str} 失败: {e}")
                
                with task_lock:
                    if task_id in collection_tasks:
                        import_weight = 20 if has_indicators else 100
                        import_progress = int(((i + 1) / max(1, total_dates)) * import_weight)
                        collection_tasks[task_id].update({
                            "processed_stocks": i + 1,
                            "progress": min(import_weight, import_progress),
                            "warning_message": f"文件导入中（{i + 1}/{total_dates}）",
                        })
            
            # 文件采集完成后生成指标：仅删除并写入「本次导入成功」的交易日，扩展历史仅用于计算（MA200 等）
            if indicators and imported_dates:
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id].update({
                            "progress": 20,
                            "warning_message": "文件导入完成，开始生成指标",
                        })
                logger.info(
                    f"正在为导入的港股历史数据生成指标: {', '.join(indicators)}；写入日期仅限: {imported_dates}"
                )
                hk_collector = AkshareDataCollector(db)
                ext_days = 300
                hk_collector.delete_indicator_rows_for_dates(imported_dates, indicators, market='HK')
                hk_collector.generate_indicators_for_date_range(
                    start_date,
                    end_date,
                    indicators,
                    extended_start_days=ext_days,
                    market='HK',
                    only_write_dates=imported_dates,
                    task_id=task_id,
                )
            
            # 汇总结果
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "status": "completed",
                        "progress": 100,
                        "success_count": success_dates,
                        "failed_count": total_dates - success_dates,
                        "end_time": datetime.now(),
                        "warning_message": None,
                    })
            
            logger.info(f"港股历史数据采集-文件任务完成: {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"港股历史数据采集-文件任务执行失败: {task_id}, 错误: {e}")
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error_message": str(e)
                })
    finally:
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")

@router.post("/file-historical", response_model=DataCollectionResponse)
async def start_file_historical_collection(
    request: FileHistoricalCollectionRequest,
    background_tasks: BackgroundTasks,
):
    """启动从本地文件读入A股历史数据的任务"""
    global current_task_id
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 检查是否有其他任务正在运行
        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail="已有采集任务正在运行，请等待完成后再启动新任务")

        # 生成任务ID
        task_id = f"file_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"

        # 初始化任务状态
        with task_lock:
            collection_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total_stocks": 0,
                "processed_stocks": 0,
                "success_count": 0,
                "failed_count": 0,
                "collected_count": 0,
                "skipped_count": 0,
                "start_time": datetime.now(),
                "end_time": None,
                "error_message": None,
                "warning_message": None,
                "failed_details": []
            }

        # 设置当前任务ID
        with task_execution_lock:
            current_task_id = task_id

        # 启动后台任务
        background_tasks.add_task(
            run_file_historical_collection_task,
            task_id,
            request.start_date,
            request.end_date,
            request.force_update,
            request.indicators,
            request.file_type,
        )

        logger.info(f"启动历史数据采集-文件任务: {task_id}")

        return DataCollectionResponse(
            task_id=task_id,
            status="started",
            message="历史数据采集-文件任务已启动",
            start_date=request.start_date,
            end_date=request.end_date,
            market="CN",
        )

    except Exception as e:
        logger.error(f"启动历史数据采集-文件任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

@router.post("/historical/hk-file", response_model=DataCollectionResponse)
async def start_hk_file_historical_collection(
    request: HKFileHistoricalCollectionRequest,
    background_tasks: BackgroundTasks
):
    """启动港股历史数据采集-文件后台任务"""
    global current_task_id
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 检查是否有其他任务正在运行
        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail="已有采集任务正在运行，请等待完成后再启动新任务")

        # 生成任务ID
        task_id = f"hk_file_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"

        # 初始化任务状态
        with task_lock:
            collection_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total_stocks": 0,
                "processed_stocks": 0,
                "success_count": 0,
                "failed_count": 0,
                "collected_count": 0,
                "skipped_count": 0,
                "start_time": datetime.now(),
                "end_time": None,
                "error_message": None,
                "warning_message": None,
                "failed_details": []
            }

        # 设置当前任务ID
        with task_execution_lock:
            current_task_id = task_id

        # 启动后台任务
        background_tasks.add_task(
            run_hk_file_historical_collection_task,
            task_id,
            request.start_date,
            request.end_date,
            request.force_update,
            request.indicators,
            request.file_type,
        )

        logger.info(f"启动港股历史数据采集-文件任务: {task_id}")

        return DataCollectionResponse(
            task_id=task_id,
            status="started",
            message="港股历史数据采集-文件任务已启动",
            start_date=request.start_date,
            end_date=request.end_date,
            market="HK",
        )

    except Exception as e:
        logger.error(f"启动港股历史数据采集-文件任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

@router.post("/upload-historical-file")
async def upload_historical_file(
    file: UploadFile = File(...)
):
    """上传历史行情数据文件（A股/港股「历史数据采集-文件」共用）"""
    try:
        # 确保目录存在
        upload_dir = os.path.join("backend_core", "data")
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        # 校验文件名格式（与 backend_core 下文件采集器查找规则一致）
        filename = file.filename or ""
        valid_prefixes = (
            "daily_", "historical_quotes_",
            "hk_daily_", "hk_historical_quotes_",
        )
        is_valid_prefix = filename.startswith(valid_prefixes)
        is_valid_ext = filename.endswith(".txt") or filename.endswith(".csv") or filename.endswith(".xlsx")
        
        if not (is_valid_prefix and is_valid_ext):
             # 虽然不做严格限制，但打印警告
             logger.warning(
                 f"上传的文件名 {filename} 不符合建议格式 "
                 f"（前缀可为 daily_、historical_quotes_、hk_daily_、hk_historical_quotes_ 之一，扩展名 txt/csv/xlsx）"
             )
             
        file_path = os.path.join(upload_dir, filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"文件上传成功: {filename} 到 {file_path}")
        
        return {
            "success": True,
            "message": f"文件 {filename} 上传成功",
            "filename": filename,
            "path": file_path
        }
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.post("/historical", response_model=DataCollectionResponse)
async def start_historical_collection(
    request: DataCollectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """启动历史数据采集任务"""
    global current_task_id
    try:
        # 验证日期格式
        try:
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 检查是否有其他任务正在运行
        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail="已有采集任务正在运行，请等待完成后再启动新任务")
        
        # 生成任务ID
        task_id = f"historical_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"
        
        # 初始化任务状态
        with task_lock:
            collection_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total_stocks": 0,
                "processed_stocks": 0,
                "success_count": 0,
                "failed_count": 0,
                "collected_count": 0,
                "skipped_count": 0,
                "start_time": datetime.now(),
                "end_time": None,
                "error_message": None,
                "warning_message": None,
                "failed_details": []
            }
        
        # 设置当前任务ID
        with task_execution_lock:
            current_task_id = task_id
        
        # 启动后台任务
        background_tasks.add_task(
            run_historical_collection_task,
            task_id,
            request.start_date,
            request.end_date,
            request.stock_codes,
            request.test_mode,
            request.full_collection_mode,
            request.market,
            request.force_update,
            request.indicators,
            request.sync_from_realtime,
            False  # stock_list_from_realtime 仅用于内部控制，不对外暴露
        )
        
        logger.info(f"启动历史数据采集任务: {task_id}")
        
        return DataCollectionResponse(
            task_id=task_id,
            status="started",
            message="历史数据采集任务已启动",
            start_date=request.start_date,
            end_date=request.end_date,
            stock_codes=request.stock_codes,
            test_mode=request.test_mode,
            full_collection_mode=request.full_collection_mode,
            market=request.market
        )
        
    except Exception as e:
        logger.error(f"启动历史数据采集任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动采集任务失败: {str(e)}")

def run_historical_collection_task(
    task_id: str,
    start_date: str,
    end_date: str,
    stock_codes: Optional[List[str]] = None,
    test_mode: bool = False,
    full_collection_mode: bool = False,
    market: str = 'CN',
    force_update: bool = False,
    indicators: Optional[List[str]] = None,
    sync_from_realtime: bool = False,
    stock_list_from_realtime: bool = False
):
    """运行历史数据采集任务（后台任务）"""
    global current_task_id
    try:
        logger.info(f"开始执行历史数据采集任务: {task_id}, 市场: {market}")
        
        # 创建数据库会话
        from backend_api.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 创建采集器
            collector = AkshareDataCollector(db)
            market_upper = (market or "CN").upper()

            # 节假日优先级最高：若整个区间剔除节假日后为空，直接跳过采集
            effective_dates = collector.get_non_holiday_date_range(market_upper, start_date, end_date)
            if not effective_dates:
                msg = (
                    f"{market_upper} 市场在区间 {start_date} ~ {end_date} 均为节假日（trading_calendar），"
                    "跳过历史采集。"
                )
                logger.info(msg)
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id].update({
                            "status": "completed",
                            "progress": 100,
                            "processed_stocks": 0,
                            "success_count": 0,
                            "failed_count": 0,
                            "collected_count": 0,
                            "skipped_count": 0,
                            "end_time": datetime.now(),
                            "warning_message": msg,
                            "failed_details": [],
                        })
                return

            # 获取股票列表
            if test_mode:
                logger.info("测试模式：只采集前5只股票")
                if market == 'HK':
                    stocks = collector.get_hk_stock_list()[:5]
                else:
                    stocks = collector.get_stock_list()[:5]
                stock_codes = [stock['code'] for stock in stocks]
            elif stock_list_from_realtime and market == 'CN':
                logger.info("A股历史采集：从实时行情表获取股票列表")
                stocks = collector.get_stock_list_from_realtime_quote()
                stock_codes = [s['code'] for s in stocks] if stocks else []

            # 更新任务状态
            with task_lock:
                if task_id in collection_tasks:
                    if stock_codes:
                        total = len(stock_codes)
                    else:
                        if full_collection_mode:
                            if market == 'HK':
                                total = len(collector.get_hk_stock_list(only_uncompleted=True))
                            else:
                                total = len(collector.get_stock_list(only_uncompleted=True))
                        else:
                            if market == 'HK':
                                total = len(collector.get_hk_stock_list())
                            else:
                                total = len(collector.get_stock_list())
                    collection_tasks[task_id]["total_stocks"] = total

            # 执行采集
            if sync_from_realtime and market == 'HK':
                result = collector.collect_hk_historical_from_realtime(start_date, end_date)
            else:
                # 从实时行情表获取列表时，使用该列表作为 stock_codes，不再按全量模式从 basic_info 取
                use_codes = stock_codes
                use_full = full_collection_mode and not (stock_list_from_realtime and market == 'CN')
                result = collector.collect_historical_data(start_date, end_date, use_codes, use_full, market, force_update, indicators)
            
            # 更新任务状态
            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        "status": "completed",
                        "progress": 100,
                        "processed_stocks": result["total"],
                        "success_count": result["success"],
                        "failed_count": result["failed"],
                        "collected_count": result["collected"],
                        "skipped_count": result["skipped"],
                        "end_time": datetime.now(),
                        "failed_details": result["failed_details"]
                    })
            
            logger.info(f"历史数据采集任务完成: {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"历史数据采集任务执行失败: {task_id}, 错误: {e}")
        
        # 更新任务状态为失败
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error_message": str(e)
                })
    finally:
        # 清除当前任务ID
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")

@router.get("/status/{task_id}", response_model=DataCollectionStatus)
async def get_collection_status(task_id: str):
    """获取采集任务状态"""
    try:
        with task_lock:
            if task_id not in collection_tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            task_info = collection_tasks[task_id]
            
            # 计算进度
            progress = task_info["progress"]
            if task_info["total_stocks"] > 0:
                progress = min(100, int((task_info["processed_stocks"] / task_info["total_stocks"]) * 100))
            
            return DataCollectionStatus(
                task_id=task_id,
                status=task_info["status"],
                progress=progress,
                total_stocks=task_info["total_stocks"],
                processed_stocks=task_info["processed_stocks"],
                success_count=task_info["success_count"],
                failed_count=task_info["failed_count"],
                collected_count=task_info["collected_count"],
                skipped_count=task_info["skipped_count"],
                start_time=task_info["start_time"],
                end_time=task_info["end_time"],
                error_message=task_info.get("error_message"),
                warning_message=task_info.get("warning_message"),
                failed_details=task_info["failed_details"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.get("/tasks", response_model=List[DataCollectionStatus])
async def list_collection_tasks():
    """获取所有采集任务列表"""
    try:
        with task_lock:
            tasks = []
            for task_id, task_info in collection_tasks.items():
                # 优先使用任务自身维护的阶段化进度，缺失时再按旧逻辑兜底
                progress = task_info.get("progress", 0)
                if progress <= 0 and task_info["total_stocks"] > 0:
                    progress = min(100, int((task_info["processed_stocks"] / task_info["total_stocks"]) * 100))
                
                tasks.append(DataCollectionStatus(
                    task_id=task_id,
                    status=task_info["status"],
                    progress=progress,
                    total_stocks=task_info["total_stocks"],
                    processed_stocks=task_info["processed_stocks"],
                    success_count=task_info["success_count"],
                    failed_count=task_info["failed_count"],
                    collected_count=task_info["collected_count"],
                    skipped_count=task_info["skipped_count"],
                    start_time=task_info["start_time"],
                    end_time=task_info["end_time"],
                    error_message=task_info.get("error_message"),
                    warning_message=task_info.get("warning_message"),
                    failed_details=task_info["failed_details"]
                ))
            
            # 按开始时间倒序排列
            tasks.sort(key=lambda x: x.start_time, reverse=True)
            
            return tasks
            
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

@router.delete("/tasks/{task_id}")
async def cancel_collection_task(task_id: str):
    """取消采集任务"""
    global current_task_id
    try:
        with task_lock:
            if task_id not in collection_tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            task_info = collection_tasks[task_id]
            if task_info["status"] in ["completed", "failed"]:
                raise HTTPException(status_code=400, detail="任务已完成或失败，无法取消")
            
            # 标记任务为取消状态
            collection_tasks[task_id]["status"] = "cancelled"
            collection_tasks[task_id]["end_time"] = datetime.now()
            
            # 如果是当前运行的任务，清除当前任务ID
            with task_execution_lock:
                if current_task_id == task_id:
                    current_task_id = None
            
            logger.info(f"取消历史数据采集任务: {task_id}")
            
            return {"message": "任务已取消", "task_id": task_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {task_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")

@router.get("/stock-list")
async def get_stock_list(db: Session = Depends(get_db), only_uncompleted: bool = False):
    """获取股票列表"""
    try:
        collector = AkshareDataCollector(db)
        stocks = collector.get_stock_list(only_uncompleted=only_uncompleted)
        
        return {
            "total": len(stocks),
            "stocks": stocks[:100],  # 只返回前100只股票用于显示
            "only_uncompleted": only_uncompleted
        }
        
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取股票列表失败: {str(e)}")

@router.get("/current-task")
async def get_current_task():
    """获取当前运行的任务信息"""
    try:
        with task_execution_lock:
            if current_task_id is None:
                return {"current_task": None}
            
            with task_lock:
                if current_task_id in collection_tasks:
                    task_info = collection_tasks[current_task_id]
                    return {
                        "current_task": {
                            "task_id": current_task_id,
                            "status": task_info["status"],
                            "start_time": task_info["start_time"]
                        }
                    }
                else:
                    return {"current_task": None}
                    
    except Exception as e:
        logger.error(f"获取当前任务信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取当前任务信息失败: {str(e)}")


def _normalize_code(raw_code: Any) -> str:
    if raw_code is None:
        return ''
    code = str(raw_code).strip()
    if '.' in code:
        code = code.split('.')[0]
    if len(code) > 2 and code[:2].isalpha() and code[2:].isdigit():
        # 兼容新浪数据源：SH600000 / SZ000001
        code = code[2:]
    return code


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, str) and val.strip() in ['', '-', 'None', 'nan']:
            return None
        return float(val)
    except Exception:
        return None


def _is_task_cancelled(task_id: str) -> bool:
    with task_lock:
        if task_id not in collection_tasks:
            return True
        return collection_tasks[task_id].get('status') == 'cancelled'


def _trigger_indicators_after_realtime(codes_snapshot: List[str], task_id: str):
    """A股实时采集成功且时间在15:30之后时，在后台线程中触发指标计算。
    采用增量方式：仅生成/更新当日 MA/MAVOL/KDJ/RSI/BOLL/MACD/PVFRS，不重算全量历史。"""
    if not codes_snapshot:
        return

    def _run():
        from backend_api.database import SessionLocal
        session = SessionLocal()
        try:
            collector = AkshareDataCollector(session)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')
            indicators = ['ma', 'mavol', 'kdj', 'rsi', 'boll', 'macd', 'pvfrs']
            incremental_dates = [end_date]  # 每日同步后只更新当日指标
            logger.info(f"[任务 {task_id}] 15:30 后触发指标计算(增量): 共 {len(codes_snapshot)} 只A股, 仅更新日期={incremental_dates}")
            for idx, code in enumerate(codes_snapshot):
                try:
                    collector._generate_indicators(code, start_date, end_date, indicators, do_commit=True, incremental_dates=incremental_dates)
                    session.commit()
                except Exception as e:
                    logger.error(f"[任务 {task_id}] 指标计算失败 {code}: {e}")
                    session.rollback()
                if (idx + 1) % 100 == 0:
                    logger.info(f"[任务 {task_id}] 指标计算进度: {idx + 1}/{len(codes_snapshot)}")
            logger.info(f"[任务 {task_id}] 指标计算完成(增量): {len(codes_snapshot)} 只A股")
        except Exception as e:
            logger.error(f"[任务 {task_id}] 指标计算任务异常: {e}")
        finally:
            session.close()

    threading.Thread(target=_run, daemon=True).start()


def run_realtime_collection_task(task_id: str, market: str, stock_code: Optional[str], full_collection_mode: bool):
    """运行实时数据采集任务（后台任务）"""
    global current_task_id
    try:
        logger.info(f"开始执行实时数据采集任务: {task_id}, market={market}, stock_code={stock_code}, full={full_collection_mode}")

        from backend_api.database import SessionLocal
        db = SessionLocal()
        try:
            trade_date = datetime.now().strftime('%Y-%m-%d')

            # --- 节假日检查 ---
            collector = AkshareDataCollector(db)
            if collector.is_holiday(market.upper(), trade_date):
                msg = f"{market}市场今天({trade_date})是节假日，跳过实时采集。"
                logger.info(msg)
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'end_time': datetime.now(),
                            'warning_message': msg
                        })
                return
            # ------------------

            if market == 'HK':
                df = None
                max_retries = 3
                retry_delay = 2
                
                # 尝试多个港股数据源，带重试机制
                for attempt in range(max_retries):
                    try:
                        logger.info(f"港股数据采集尝试 {attempt + 1}/{max_retries}")
                        
                        # 尝试第一个接口
                        try:
                            df = ak.stock_hk_spot_em()
                            logger.info(f"使用 stock_hk_spot_em 接口获取数据")
                            if df is not None and not df.empty:
                                break
                        except Exception as e:
                            logger.warning(f"港股实时接口 stock_hk_spot_em 调用失败: {e}")
                        
                        # 如果第一个接口失败，尝试第二个接口
                        if df is None or df.empty:
                            try:
                                df = ak.stock_hk_spot()
                                logger.info(f"使用 stock_hk_spot 接口获取数据")
                                if df is not None and not df.empty:
                                    break
                            except Exception as e:
                                logger.warning(f"港股实时接口 stock_hk_spot 调用失败: {e}")
                        
                        # 如果获取到数据，跳出重试循环
                        if df is not None and not df.empty:
                            break
                            
                        # 如果是最后一次尝试，不需要等待
                        if attempt < max_retries - 1:
                            logger.info(f"等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            
                    except Exception as e:
                        logger.error(f"港股数据采集第 {attempt + 1} 次尝试失败: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2

                # 检查最终是否获取到数据
                if df is None or df.empty:
                    error_msg = f'港股实时行情数据为空（已重试 {max_retries} 次）'
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                logger.info(f"成功获取港股数据，共 {len(df)} 条记录")

                if stock_code and str(stock_code).strip():
                    code = str(stock_code).strip()
                    # 兼容字段名
                    code_col = '代码' if '代码' in df.columns else ('symbol' if 'symbol' in df.columns else None)
                    if code_col:
                        df = df[df[code_col].astype(str).str.strip() == code]

                total = len(df)
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id]['total_stocks'] = total

                processed = 0
                success = 0
                failed_details: List[str] = []

                for _, row in df.iterrows():
                    if _is_task_cancelled(task_id):
                        logger.info(f"实时采集任务已取消: {task_id}")
                        return

                    processed += 1
                    try:
                        code_val = None
                        for k in ['代码', '股票代码', 'symbol', 'code']:
                            if k in df.columns:
                                v = row.get(k)
                                if v is not None and pd.notna(v):
                                    code_val = str(v).strip()
                                    if code_val:
                                        break
                        if not code_val:
                            continue

                        name_val = None
                        for k in ['中文名称', '名称', 'name', '股票名称']:
                            if k in df.columns:
                                v = row.get(k)
                                if v is not None and pd.notna(v):
                                    name_val = str(v).strip()
                                    if name_val:
                                        break

                        def safe_get(*keys):
                            for k in keys:
                                if k in df.columns:
                                    v = row.get(k)
                                    if v is not None and pd.notna(v):
                                        return v
                            return None

                        # 港股成交量统一按「手」存库；接口成交量为股，÷100 转为手
                        raw_vol = _safe_float(safe_get('成交量', 'volume'))
                        vol_hand = (raw_vol / 100) if raw_vol is not None else None
                        data = {
                            'code': code_val,
                            'trade_date': trade_date,
                            'name': name_val or code_val,
                            'english_name': str(safe_get('英文名称', '英文名', 'engname', 'english_name')).strip() if safe_get('英文名称', '英文名', 'engname', 'english_name') is not None else None,
                            'current_price': _safe_float(safe_get('最新价', '现价', 'lasttrade')),
                            'change_percent': _safe_float(safe_get('涨跌幅', '涨跌%', 'changepercent')),
                            'change_amount': _safe_float(safe_get('涨跌额', '涨跌', 'pricechange')),
                            'volume': vol_hand,
                            'amount': _safe_float(safe_get('成交额', 'amount')),
                            'high': _safe_float(safe_get('最高', 'high')),
                            'low': _safe_float(safe_get('最低', 'low')),
                            'open': _safe_float(safe_get('今开', '开盘', 'open')),
                            'pre_close': _safe_float(safe_get('昨收', '昨收价', 'prevclose')),
                            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        }

                        # 名称含「退」的股票（退市等）不再写入实时、历史行情表
                        if '退' in (str(data.get('name') or '')):
                            with task_lock:
                                if task_id in collection_tasks:
                                    collection_tasks[task_id]['skipped_count'] += 1
                            continue
                        # 检查数据是否有效（现价和成交量不能同时为空）
                        if data['current_price'] is None and data['volume'] is None:
                            logger.debug(f"跳过港股 {data['code']} ({data['name']}): 实时行情数据为空")
                            with task_lock:
                                if task_id in collection_tasks:
                                    collection_tasks[task_id]['skipped_count'] += 1
                            continue


                        # 基础信息
                        db.execute(text('''
                            INSERT INTO stock_basic_info_hk (code, name, create_date)
                            VALUES (:code, :name, :create_date)
                            ON CONFLICT (code) DO UPDATE SET
                                name = EXCLUDED.name,
                                create_date = EXCLUDED.create_date
                        '''), {'code': data['code'], 'name': data['name'], 'create_date': data['update_time']})

                        # 实时行情
                        db.execute(text('''
                            INSERT INTO stock_realtime_quote_hk
                            (code, trade_date, name, english_name, current_price, change_percent, change_amount, volume, amount,
                             high, low, open, pre_close, update_time)
                            VALUES
                            (:code, :trade_date, :name, :english_name, :current_price, :change_percent, :change_amount, :volume, :amount,
                             :high, :low, :open, :pre_close, :update_time)
                            ON CONFLICT (code, trade_date) DO UPDATE SET
                                name = EXCLUDED.name,
                                english_name = EXCLUDED.english_name,
                                current_price = EXCLUDED.current_price,
                                change_percent = EXCLUDED.change_percent,
                                change_amount = EXCLUDED.change_amount,
                                volume = EXCLUDED.volume,
                                amount = EXCLUDED.amount,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                open = EXCLUDED.open,
                                pre_close = EXCLUDED.pre_close,
                                update_time = EXCLUDED.update_time
                        '''), data)

                        db.commit()
                        success += 1
                    except Exception as e:
                        db.rollback()
                        failed_details.append(str(e))

                    with task_lock:
                        if task_id in collection_tasks:
                            total_stocks = max(1, collection_tasks[task_id].get('total_stocks') or total)
                            collection_tasks[task_id]['processed_stocks'] = processed
                            collection_tasks[task_id]['success_count'] = success
                            collection_tasks[task_id]['failed_count'] = len(failed_details)
                            collection_tasks[task_id]['collected_count'] = success
                            collection_tasks[task_id]['failed_details'] = failed_details[-200:]
                            collection_tasks[task_id]['progress'] = min(100, int((processed / total_stocks) * 100))

            else:
                df = None
                data_source = None
                max_retries = 3
                retry_delay = 2
                
                # 尝试多个A股数据源，带重试机制
                for attempt in range(max_retries):
                    try:
                        logger.info(f"A股数据采集尝试 {attempt + 1}/{max_retries}")
                        
                        # 尝试第一个接口
                        try:
                            df = ak.stock_zh_a_spot_em()
                            data_source = 'em'
                            logger.info(f"使用 stock_zh_a_spot_em 接口获取数据")
                            if df is not None and not df.empty:
                                break
                        except Exception as e:
                            logger.warning(f"A股实时接口 stock_zh_a_spot_em 调用失败: {e}")
                        
                        # 如果第一个接口失败，尝试第二个接口
                        if df is None or df.empty:
                            try:
                                df = ak.stock_zh_a_spot()
                                data_source = 'sina'
                                logger.info(f"使用 stock_zh_a_spot 接口获取数据")
                                if df is not None and not df.empty:
                                    break
                            except Exception as e:
                                logger.warning(f"A股实时接口 stock_zh_a_spot 调用失败: {e}")
                        
                        # 如果获取到数据，跳出重试循环
                        if df is not None and not df.empty:
                            break
                            
                        # 如果是最后一次尝试，不需要等待
                        if attempt < max_retries - 1:
                            logger.info(f"等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            
                    except Exception as e:
                        logger.error(f"A股数据采集第 {attempt + 1} 次尝试失败: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2

                # 检查最终是否获取到数据
                if df is None or df.empty:
                    error_msg = f'A股实时行情数据为空（已重试 {max_retries} 次）'
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                logger.info(f"成功获取A股数据，共 {len(df)} 条记录，数据源: {data_source}")

                if stock_code and str(stock_code).strip():
                    code = str(stock_code).strip()
                    if '代码' in df.columns:
                        if data_source == 'sina':
                            df = df[df['代码'].astype(str).apply(_normalize_code) == code]
                        else:
                            df = df[df['代码'].astype(str).str.strip() == code]

                total = len(df)
                with task_lock:
                    if task_id in collection_tasks:
                        collection_tasks[task_id]['total_stocks'] = total

                processed = 0
                success = 0
                failed_details: List[str] = []
                collected_codes: List[str] = []  # 采集成功的A股代码，用于 15:30 后触发指标计算

                for _, row in df.iterrows():
                    if _is_task_cancelled(task_id):
                        logger.info(f"实时采集任务已取消: {task_id}")
                        return

                    processed += 1
                    try:
                        code_val = _normalize_code(row.get('代码'))
                        if not code_val:
                            continue
                        if stock_code and code_val != str(stock_code).strip():
                            continue

                        trade_date = datetime.now().strftime('%Y-%m-%d')
                        # 成交量统一按「手」存库：东方财富=手(原样)，新浪=股(÷100 转为手)
                        raw_vol = _safe_float(row.get('成交量'))
                        volume = (raw_vol / 100) if (data_source == 'sina' and raw_vol is not None) else raw_vol
                        data = {
                            'code': code_val,
                            'trade_date': trade_date,
                            'name': str(row.get('名称') or code_val),
                            'current_price': _safe_float(row.get('最新价')),
                            'change_percent': _safe_float(row.get('涨跌幅')),
                            'volume': volume,
                            'amount': _safe_float(row.get('成交额')),
                            'high': _safe_float(row.get('最高')),
                            'low': _safe_float(row.get('最低')),
                            'open': _safe_float(row.get('今开')),
                            'pre_close': _safe_float(row.get('昨收')),
                            'turnover_rate': _safe_float(row.get('换手率')) if '换手率' in df.columns else None,
                            'pe_dynamic': _safe_float(row.get('市盈率-动态')) if '市盈率-动态' in df.columns else _safe_float(row.get('市盈率')),
                            'total_market_value': _safe_float(row.get('总市值')) if '总市值' in df.columns else None,
                            'pb_ratio': _safe_float(row.get('市净率')) if '市净率' in df.columns else None,
                            'circulating_market_value': _safe_float(row.get('流通市值')) if '流通市值' in df.columns else None,
                            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        }

                        # 名称含「退」的股票（退市等）不再写入实时、历史行情表
                        if '退' in (str(data.get('name') or '')):
                            with task_lock:
                                if task_id in collection_tasks:
                                    collection_tasks[task_id]['skipped_count'] += 1
                            continue
                        # 检查数据是否有效（现价和成交量不能同时为空）
                        if data['current_price'] is None and data['volume'] is None:
                            logger.debug(f"跳过A股 {data['code']} ({data['name']}): 实时行情数据为空")
                            with task_lock:
                                if task_id in collection_tasks:
                                    collection_tasks[task_id]['skipped_count'] += 1
                            continue


                        db.execute(text('''
                            INSERT INTO stock_basic_info (code, name, create_date)
                            VALUES (:code, :name, :create_date)
                            ON CONFLICT (code) DO UPDATE SET
                                name = EXCLUDED.name,
                                create_date = EXCLUDED.create_date
                        '''), {'code': data['code'], 'name': data['name'], 'create_date': data['update_time']})

                        db.execute(text('''
                            INSERT INTO stock_realtime_quote
                            (code, trade_date, name, current_price, change_percent, volume, amount,
                             high, low, open, pre_close, turnover_rate, pe_dynamic, total_market_value, pb_ratio,
                             circulating_market_value, update_time)
                            VALUES
                            (:code, :trade_date, :name, :current_price, :change_percent, :volume, :amount,
                             :high, :low, :open, :pre_close, :turnover_rate, :pe_dynamic, :total_market_value, :pb_ratio,
                             :circulating_market_value, :update_time)
                            ON CONFLICT (code, trade_date) DO UPDATE SET
                                name = EXCLUDED.name,
                                current_price = EXCLUDED.current_price,
                                change_percent = EXCLUDED.change_percent,
                                volume = EXCLUDED.volume,
                                amount = EXCLUDED.amount,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                open = EXCLUDED.open,
                                pre_close = EXCLUDED.pre_close,
                                turnover_rate = EXCLUDED.turnover_rate,
                                pe_dynamic = EXCLUDED.pe_dynamic,
                                total_market_value = EXCLUDED.total_market_value,
                                pb_ratio = EXCLUDED.pb_ratio,
                                circulating_market_value = EXCLUDED.circulating_market_value,
                                update_time = EXCLUDED.update_time
                        '''), data)

                        db.commit()
                        success += 1
                        collected_codes.append(code_val)
                    except Exception as e:
                        db.rollback()
                        failed_details.append(str(e))

                    with task_lock:
                        if task_id in collection_tasks:
                            total_stocks = max(1, collection_tasks[task_id].get('total_stocks') or total)
                            collection_tasks[task_id]['processed_stocks'] = processed
                            collection_tasks[task_id]['success_count'] = success
                            collection_tasks[task_id]['failed_count'] = len(failed_details)
                            collection_tasks[task_id]['collected_count'] = success
                            collection_tasks[task_id]['failed_details'] = failed_details[-200:]
                            collection_tasks[task_id]['progress'] = min(100, int((processed / total_stocks) * 100))

            # A股实时采集成功且当前时间在下午3点半之后，后台触发 MA/MAVOL/KDJ/RSI/BOLL/MACD/PVFRS(GMS) 指标计算
            if market != 'HK' and success > 0:
                now = datetime.now()
                if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
                    codes_snapshot = list(collected_codes)
                    _trigger_indicators_after_realtime(codes_snapshot, task_id)

            with task_lock:
                if task_id in collection_tasks:
                    collection_tasks[task_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'end_time': datetime.now(),
                    })

            logger.info(f"实时数据采集任务完成: {task_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"实时数据采集任务执行失败: {task_id}, 错误: {e}")
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    'status': 'failed',
                    'end_time': datetime.now(),
                    'error_message': str(e),
                })
    finally:
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")


@router.post('/realtime', response_model=RealtimeCollectionResponse)
async def start_realtime_collection(
    request: RealtimeCollectionRequest,
    background_tasks: BackgroundTasks,
):
    """启动实时数据采集任务（A股/港股，支持单个/全量）"""
    global current_task_id
    try:
        market = (request.market or 'CN').upper()
        if market not in ['CN', 'HK']:
            raise HTTPException(status_code=400, detail='market只支持CN/HK')

        single_code = (request.stock_code or '').strip() or None
        full_mode = bool(request.full_collection_mode)
        if single_code and full_mode:
            raise HTTPException(status_code=400, detail='单股采集与全量采集不可同时指定')

        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail='已有采集任务正在运行，请等待完成后再启动新任务')

        task_id = f"realtime_collection_{market}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"

        with task_lock:
            collection_tasks[task_id] = {
                'status': 'running',
                'progress': 0,
                'total_stocks': 0,
                'processed_stocks': 0,
                'success_count': 0,
                'failed_count': 0,
                'collected_count': 0,
                'skipped_count': 0,
                'start_time': datetime.now(),
                'end_time': None,
                'error_message': None,
                'failed_details': [],
            }

        with task_execution_lock:
            current_task_id = task_id

        background_tasks.add_task(run_realtime_collection_task, task_id, market, single_code, full_mode)

        return RealtimeCollectionResponse(
            task_id=task_id,
            status='started',
            message='实时数据采集任务已启动',
            market=market,
            stock_code=single_code,
            full_collection_mode=full_mode,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动实时数据采集任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动采集任务失败: {str(e)}")

class TushareDataCollector:
    """Tushare数据采集器"""
    
    def __init__(self, db_session: Session):
        self.session = db_session
        self.collected_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.failed_details = []
        
        # 导入tushare并设置token
        import tushare as ts
        from backend_core.config.config import TUSHARE_CONFIG
        ts.set_token(TUSHARE_CONFIG['token'])
        self.ts_pro = ts.pro_api()
    
    def collect_historical_data_for_date_range(
        self, 
        start_date: str, 
        end_date: str, 
        force_update: bool = False
    ) -> Dict[str, any]:
        """
        采集指定日期范围内的A股全量历史数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_update: 是否强制更新（先删除后插入）
        
        Returns:
            采集结果统计
        """
        try:
            logger.info(f"开始Tushare历史数据采集: {start_date} 到 {end_date}, 强制更新: {force_update}")
            
            # 重置计数器
            self.collected_count = 0
            self.skipped_count = 0
            self.failed_count = 0
            self.failed_details = []
            
            # 生成日期列表（交易日）
            from datetime import datetime, timedelta
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            current_date = start
            dates_to_collect = []
            while current_date <= end:
                date_str = current_date.strftime('%Y%m%d')  # tushare需要YYYYMMDD格式
                dates_to_collect.append((current_date.strftime('%Y-%m-%d'), date_str))
                current_date += timedelta(days=1)
            
            logger.info(f"需要采集 {len(dates_to_collect)} 天的数据")
            
            # 遍历每个日期进行采集
            for display_date, trade_date in dates_to_collect:
                try:
                    result = self.collect_historical_data_for_single_date(trade_date, display_date, force_update)
                    if result['success']:
                        self.collected_count += result['collected']
                        self.skipped_count += result['skipped']
                    else:
                        self.failed_count += 1
                        self.failed_details.append(f"{display_date}: {result['error']}")
                        
                except Exception as e:
                    logger.error(f"采集日期 {display_date} 失败: {e}")
                    self.failed_count += 1
                    self.failed_details.append(f"{display_date}: {str(e)}")
                    continue
            
            result = {
                'total_dates': len(dates_to_collect),
                'success_dates': len(dates_to_collect) - self.failed_count,
                'failed_dates': self.failed_count,
                'collected': self.collected_count,
                'skipped': self.skipped_count,
                'failed_details': self.failed_details
            }
            
            logger.info(f"Tushare采集完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Tushare历史数据采集失败: {e}")
            return {
                'total_dates': 0,
                'success_dates': 0,
                'failed_dates': 1,
                'collected': 0,
                'skipped': 0,
                'failed_details': [str(e)]
            }
    
    def collect_historical_data_for_single_date(
        self, 
        trade_date: str, 
        display_date: str,
        force_update: bool = False
    ) -> Dict[str, any]:
        """
        采集单个日期的历史数据
        
        Args:
            trade_date: 交易日期 (YYYYMMDD格式，tushare接口要求)
            display_date: 显示日期 (YYYY-MM-DD格式)
            force_update: 是否强制更新
        
        Returns:
            采集结果
        """
        try:
            import pandas as pd
            
            # 检查已存在的数据
            if not force_update:
                result = self.session.execute(text("""
                    SELECT COUNT(*) 
                    FROM historical_quotes 
                    WHERE date = :date
                """), {'date': display_date})
                existing_count = result.scalar()
                
                # 仅当当天数据量接近全量才跳过；否则继续采集并通过 upsert 补齐全量
                # 避免出现“当天先写入了少量残缺数据（如 56 条），后续永远跳过，导致指标也只生成 56 条”的问题
                try:
                    expected_total = self.session.execute(text("""
                        SELECT COUNT(*) FROM stock_basic_info
                        WHERE name IS NULL OR name NOT LIKE '%退%'
                    """)).scalar() or 0
                except Exception:
                    expected_total = 0

                # 经验阈值：A股全量通常 5k+；若 expected_total 异常则退回到 5000 作为阈值
                full_threshold = int(expected_total * 0.95) if expected_total >= 1000 else 5000

                if existing_count >= full_threshold:
                    logger.info(
                        f"日期 {display_date} 已存在 {existing_count} 条数据(阈值{full_threshold})，视为已全量，跳过采集"
                    )
                    return {
                        'success': True,
                        'collected': 0,
                        'skipped': existing_count,
                        'error': None
                    }
                if existing_count > 0:
                    logger.info(
                        f"日期 {display_date} 已存在 {existing_count} 条数据(<阈值{full_threshold})，将继续采集以补齐全量"
                    )
            
            # 如果需要强制更新，先删除该日期的数据
            if force_update:
                deleted_count = self.session.execute(text("""
                    DELETE FROM historical_quotes 
                    WHERE date = :date
                """), {'date': display_date}).rowcount
                self.session.commit()
                logger.info(f"强制更新模式：已删除日期 {display_date} 的 {deleted_count} 条数据")
            
            # 直接使用 Tushare Pro 接口采集并用当前 Session 写库，确保与指标生成使用同一连接/同一库
            df = self.ts_pro.daily(trade_date=trade_date)
            if df is None or (hasattr(df, "empty") and df.empty):
                return {'success': False, 'collected': 0, 'skipped': 0, 'error': 'tushare返回空数据'}

            # 规范字段
            # tushare daily: ts_code, open, high, low, close, pre_close, change, pct_chg, vol, amount
            df = df.copy()
            if "ts_code" not in df.columns:
                return {'success': False, 'collected': 0, 'skipped': 0, 'error': 'tushare返回缺少ts_code字段'}
            df["code"] = df["ts_code"].astype(str).str.split(".").str[0]

            # 读取名称（避免逐行查库）
            codes = df["code"].dropna().astype(str).unique().tolist()
            name_map = {}
            if codes:
                try:
                    from sqlalchemy import bindparam
                    name_rows = self.session.execute(
                        text("SELECT code, name FROM stock_basic_info WHERE code IN :codes").bindparams(
                            bindparam("codes", expanding=True)
                        ),
                        {"codes": codes},
                    ).fetchall()
                    name_map = {str(r[0]): (r[1] or "") for r in name_rows}
                except Exception:
                    # 名称非关键字段，失败则置空
                    name_map = {}

            # 组装批量 upsert
            rows = []
            for _, r in df.iterrows():
                code = str(r.get("code") or "").strip()
                if not code:
                    continue
                name = name_map.get(code, "")
                if "退" in (name or ""):
                    continue
                vol = r.get("vol")
                amount = r.get("amount")
                # 成交量单位：按手存（用户已确认 tushare 全量历史 vol 为手）
                vol_hand = float(vol) if vol is not None and not pd.isna(vol) else None
                # tushare amount 通常为千元，折算为元
                amt_yuan = (float(amount) * 1000) if amount is not None and not pd.isna(amount) else None
                rows.append({
                    "code": code,
                    "ts_code": str(r.get("ts_code") or ""),
                    "name": name,
                    "market": "",
                    "collected_source": "tushare",
                    "collected_date": datetime.now().isoformat(),
                    "date": display_date,
                    "open": float(r.get("open")) if r.get("open") is not None and not pd.isna(r.get("open")) else None,
                    "high": float(r.get("high")) if r.get("high") is not None and not pd.isna(r.get("high")) else None,
                    "low": float(r.get("low")) if r.get("low") is not None and not pd.isna(r.get("low")) else None,
                    "close": float(r.get("close")) if r.get("close") is not None and not pd.isna(r.get("close")) else None,
                    "volume": vol_hand,
                    "amount": amt_yuan,
                    "change_percent": float(r.get("pct_chg")) if r.get("pct_chg") is not None and not pd.isna(r.get("pct_chg")) else None,
                    "pre_close": float(r.get("pre_close")) if r.get("pre_close") is not None and not pd.isna(r.get("pre_close")) else None,
                    "change": float(r.get("change")) if r.get("change") is not None and not pd.isna(r.get("change")) else None,
                    "amplitude": None,
                    "turnover_rate": None,
                })

            if not rows:
                return {
                    'success': False,
                    'collected': 0,
                    'skipped': 0,
                    'error': 'tushare返回数据经筛选后无有效行（可能均为退市等）',
                }

            upsert_sql = text("""
                INSERT INTO historical_quotes
                (code, ts_code, name, market, collected_source, collected_date, date,
                 open, high, low, close, volume, amount, change_percent, pre_close, change, amplitude, turnover_rate)
                VALUES
                (:code, :ts_code, :name, :market, :collected_source, :collected_date, :date,
                 :open, :high, :low, :close, :volume, :amount, :change_percent, :pre_close, :change, :amplitude, :turnover_rate)
                ON CONFLICT (code, date) DO UPDATE SET
                    ts_code = EXCLUDED.ts_code,
                    name = EXCLUDED.name,
                    market = EXCLUDED.market,
                    collected_source = EXCLUDED.collected_source,
                    collected_date = EXCLUDED.collected_date,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    change_percent = EXCLUDED.change_percent,
                    pre_close = EXCLUDED.pre_close,
                    amplitude = EXCLUDED.amplitude,
                    turnover_rate = EXCLUDED.turnover_rate,
                    change = EXCLUDED.change
            """)

            self.session.execute(upsert_sql, rows)
            self.session.commit()
            return {'success': True, 'collected': len(rows), 'skipped': 0, 'error': None}
                
        except Exception as e:
            logger.error(f"采集日期 {display_date} 失败: {e}")
            return {
                'success': False,
                'collected': 0,
                'skipped': 0,
                'error': str(e)
            }

@router.post("/tushare-historical", response_model=DataCollectionResponse)
async def start_tushare_historical_collection(
    request: TushareHistoricalCollectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """启动Tushare历史数据采集任务"""
    global current_task_id
    try:
        # 验证日期格式
        try:
            from datetime import datetime
            datetime.strptime(request.start_date, '%Y-%m-%d')
            datetime.strptime(request.end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        
        # 检查是否有其他任务正在运行
        with task_execution_lock:
            if current_task_id is not None:
                raise HTTPException(status_code=400, detail="已有采集任务正在运行，请等待完成后再启动新任务")
        
        # 生成任务ID
        task_id = f"tushare_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{threading.get_ident()}"
        
        # 初始化任务状态
        with task_lock:
            collection_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "total_stocks": 0,  # Tushare是全量采集，不按股票统计
                "processed_stocks": 0,
                "total_dates": 0,
                "processed_dates": 0,
                "success_count": 0,
                "failed_count": 0,
                "collected_count": 0,
                "skipped_count": 0,
                "start_time": datetime.now(),
                "end_time": None,
                "error_message": None,
                "warning_message": None,
                "failed_details": []
            }
        
        # 设置当前任务ID
        with task_execution_lock:
            current_task_id = task_id
        
        # 启动后台任务
        background_tasks.add_task(
            run_tushare_historical_collection_task,
            task_id,
            request.start_date,
            request.end_date,
            request.force_update,
            request.indicators
        )
        
        logger.info(f"启动Tushare历史数据采集任务: {task_id}")
        
        return DataCollectionResponse(
            task_id=task_id,
            status="started",
            message="Tushare历史数据采集任务已启动",
            start_date=request.start_date,
            end_date=request.end_date,
            stock_codes=None,
            test_mode=False,
            full_collection_mode=True
        )
        
    except Exception as e:
        logger.error(f"启动Tushare历史数据采集任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动采集任务失败: {str(e)}")

def run_tushare_historical_collection_task(
    task_id: str,
    start_date: str,
    end_date: str,
    force_update: bool,
    indicators: Optional[List[str]] = None
):
    """运行Tushare历史数据采集任务（后台任务）"""
    global current_task_id
    try:
        logger.info(f"开始执行Tushare历史数据采集任务: {task_id}")
        
        # 创建数据库会话
        from backend_api.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 创建采集器
            collector = TushareDataCollector(db)
            
            # 执行采集
            result = collector.collect_historical_data_for_date_range(
                start_date, 
                end_date, 
                force_update
            )
            
            # 仅当至少有一个交易日从 tushare 成功落库（或视为成功跳过）时才生成指标；若全部为空/报错则跳过，避免用旧数据误算 MA 等
            indicator_result = None
            if result.get("success_dates", 0) > 0:
                indicators_to_run = list(set((indicators or []) + ['ma', 'mavol', 'pvfrs']))
                logger.info(f"开始为采集日期范围 [{start_date}, {end_date}] 生成指标: {indicators_to_run}")
                akshare_collector = AkshareDataCollector(db)
                indicator_result = akshare_collector.generate_indicators_for_date_range(
                    start_date, end_date, indicators_to_run, extended_start_days=300
                )
                logger.info(f"TuShare采集后指标生成完成: {indicator_result}")
            else:
                logger.warning(
                    "Tushare 历史采集无任何成功交易日（接口返回空或全部失败），跳过 MA/MAVOL/PVFRS 等指标计算。采集结果: %s",
                    result,
                )
            
            # 更新任务状态
            with task_lock:
                if task_id in collection_tasks:
                    # 计算进度（基于日期）
                    progress = 100
                    if result['total_dates'] > 0:
                        progress = min(100, int((result['success_dates'] / result['total_dates']) * 100))
                    
                    collection_tasks[task_id].update({
                        "status": "completed" if result['failed_dates'] == 0 else "partial_success",
                        "progress": progress,
                        "total_dates": result['total_dates'],
                        "processed_dates": result['success_dates'],
                        "success_count": result['success_dates'],
                        "failed_count": result['failed_dates'],
                        "collected_count": result['collected'],
                        "skipped_count": result['skipped'],
                        "end_time": datetime.now(),
                        "failed_details": result['failed_details']
                    })
            
            logger.info(f"Tushare历史数据采集任务完成: {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Tushare历史数据采集任务执行失败: {task_id}, 错误: {e}")
        
        # 更新任务状态为失败
        with task_lock:
            if task_id in collection_tasks:
                collection_tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error_message": str(e)
                })
    finally:
        # 清除当前任务ID
        with task_execution_lock:
            if current_task_id == task_id:
                current_task_id = None
                logger.info(f"已清除当前任务ID: {task_id}")
