import tushare as ts
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from .base import TushareCollector
import datetime
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from .five_day_change_calculator import FiveDayChangeCalculator
from .extended_change_calculator import ExtendedChangeCalculator
from .thirty_day_change_calculator import ThirtyDayChangeCalculator
from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.rsi_calculator import RSICalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
from datetime import timedelta

class HistoricalQuoteCollector(TushareCollector):
    
    """历史行情数据采集器"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
    
    def _init_db(self):
        session = SessionLocal()
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                total_share REAL
            )
        '''))
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS historical_quotes (
                code TEXT,
                ts_code TEXT,
                name TEXT,
                market TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                volume REAL,
                amount REAL,    
                amplitude REAL,
                turnover_rate REAL,
                change_percent REAL,
                change REAL,
                five_day_change_percent REAL,
                ten_day_change_percent REAL,
                sixty_day_change_percent REAL,
                thirty_day_change_percent REAL,
                collected_source TEXT,
                collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date)
            )
        '''))
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS historical_collect_operation_logs (
                id SERIAL PRIMARY KEY,
                operation_type TEXT NOT NULL,
                operation_desc TEXT NOT NULL,
                affected_rows INTEGER,
                status TEXT NOT NULL,
                error_message TEXT,
                collect_source TEXT DEFAULT 'tushare',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # 添加 collect_source 字段（如果表已存在但字段不存在）
        session.execute(text('''
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='historical_collect_operation_logs' 
                               AND column_name='collect_source') THEN
                    ALTER TABLE historical_collect_operation_logs ADD COLUMN collect_source TEXT DEFAULT 'tushare';
                END IF;
            END
            $$;
        '''))
        # 初始化MA指标表结构
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS ma_indicators (
                code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                market_type VARCHAR(10) NOT NULL,
                ma5 REAL,
                ma10 REAL,
                ma20 REAL,
                ma30 REAL,
                ma60 REAL,
                ma120 REAL,
                ma200 REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date, market_type)
            )
        '''))
        # 初始化KDJ指标表结构
        session.execute(text('''
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
        # 初始化RSI指标表结构
        session.execute(text('''
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
        # 初始化BOLL指标表结构
        session.execute(text('''
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
        # 初始化MAVOL指标表结构
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS mavol_indicators (
                code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                market_type VARCHAR(10) NOT NULL,
                mavol5 REAL,
                mavol10 REAL,
                mavol20 REAL,
                mavol30 REAL,
                mavol60 REAL,
                mavol120 REAL,
                mavol200 REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date, market_type)
            )
        '''))
        # 初始化均值频率共振指标表结构
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS mean_frequency_resonance_indicators (
                code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                market_type VARCHAR(10) NOT NULL,
                macro_displacement_delta REAL,
                ratio_d20 REAL,
                ratio_d1 REAL,
                instant_deviation REAL,
                rising_days_z INTEGER,
                falling_days_f INTEGER,
                efficiency_m20_minus_m REAL,
                ma20_d REAL,
                mavol20_m REAL,
                bias REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date, market_type)
            )
        '''))
        session.commit()
        session.close()

    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    
    def extract_code_from_ts_code(self, ts_code: str) -> str:
        return ts_code.split(".")[0] if ts_code else ""
    
    def _get_watchlist_codes(self, session) -> set:
        """获取所有用户的自选股代码"""
        try:
            result = session.execute(text("SELECT DISTINCT stock_code FROM watchlist"))
            return {str(row[0]) for row in result.fetchall()}
        except Exception as e:
            self.logger.error(f"获取自选股列表失败: {e}")
            return set()

    def _calculate_and_save_macd_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """
        计算并保存指定日期的MACD指标
        
        Args:
            session: 数据库会话
            target_date: 目标日期 (YYYY-MM-DD)
            
        Returns:
            dict: 计算结果统计
        """
        try:
            calculator = MACDCalculator()
            
            # 获取该日期所有有数据的股票代码
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            
            stock_codes = [row[0] for row in result.fetchall()]
            
            # 如果提供了自选股列表，则只计算自选股
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
                self.logger.info(f"限制为 {len(stock_codes)} 只自选股计算MACD")

            if not stock_codes:
                self.logger.warning(f"日期 {target_date} 没有股票数据")
                return {
                    'total': 0,
                    'success': 0,
                    'skipped': 0,
                    'failed': 0,
                    'details': []
                }
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            
            # 查询开始日期（需要至少26天历史数据）
            query_start_date = (datetime.datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少26天的收盘价数据
                    result = session.execute(text("""
                        SELECT date, close 
                        FROM historical_quotes 
                        WHERE code = :stock_code 
                        AND date >= :query_start_date 
                        AND date <= :target_date
                        AND close IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'query_start_date': query_start_date,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 26:
                        skipped_count += 1
                        continue
                    
                    # 提取收盘价和日期
                    dates = []
                    closes = []
                    for row in rows:
                        date_val = row[0]
                        if isinstance(date_val, datetime.datetime):
                            date_str = date_val.strftime('%Y-%m-%d')
                        elif isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = str(date_val)
                        dates.append(date_str)
                        closes.append(float(row[1]))
                    
                    # 批量计算MACD
                    macd_results = calculator.calculate_macd_batch(closes)
                    
                    if not macd_results:
                        failed_count += 1
                        failed_details.append(f"{stock_code}: MACD计算失败")
                        continue
                    
                    # 保存MACD数据（只保存目标日期的数据）
                    saved = False
                    for i, macd_data in enumerate(macd_results):
                        if macd_data['dif'] is None:
                            continue
                        
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
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
                                'created_at': datetime.datetime.now()
                            })
                            saved = True
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} MACD数据失败: {e}")
                            continue
                    
                    if saved:
                        success_count += 1
                    else:
                        skipped_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
                    self.logger.error(f"计算股票 {stock_code} MACD指标失败: {e}")
                    continue
            
            # 提交事务
            session.commit()
            
            return {
                'total': len(stock_codes),
                'success': success_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'details': failed_details
            }
            
        except Exception as e:
            self.logger.error(f"批量计算MACD指标失败: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': 0,
                'skipped': 0,
                'failed': 0,
                'details': [str(e)]
            }
    
    def _calculate_and_save_ma_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """
        计算并保存指定日期的MA指标
        
        Args:
            session: 数据库会话
            target_date: 目标日期 (YYYY-MM-DD)
            
        Returns:
            dict: 计算结果统计
        """
        try:
            # 获取该日期所有有数据的股票代码
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            
            stock_codes = [row[0] for row in result.fetchall()]
            
            # 如果提供了自选股列表，则只计算自选股
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
                self.logger.info(f"限制为 {len(stock_codes)} 只自选股计算MA")

            if not stock_codes:
                self.logger.warning(f"日期 {target_date} 没有股票数据")
                return {
                    'total': 0,
                    'success': 0,
                    'skipped': 0,
                    'failed': 0,
                    'details': []
                }
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            
            # 查询所有历史数据（不限制日期范围，确保有足够数据计算MA200）
            # 注意：MA200需要至少200个交易日，约300个日历天，但为了保险起见，查询所有历史数据
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票所有历史收盘价数据（不限制日期范围）
                    result = session.execute(text("""
                        SELECT date, close 
                        FROM historical_quotes 
                        WHERE code = :stock_code 
                        AND date <= :target_date
                        AND close IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 5:  # 至少需要5天数据才能计算MA5
                        skipped_count += 1
                        continue
                    
                    # 构建DataFrame
                    df_data = []
                    dates = []
                    for row in rows:
                        date_val = row[0]
                        if isinstance(date_val, datetime.datetime):
                            date_str = date_val.strftime('%Y-%m-%d')
                        elif isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = str(date_val)
                        dates.append(date_str)
                        df_data.append({
                            'date': date_str,
                            'close': float(row[1]) if row[1] else None
                        })
                    
                    df = pd.DataFrame(df_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
                    
                    if 'close' not in df.columns or len(df) == 0:
                        skipped_count += 1
                        continue
                    
                    # 计算MA指标
                    ma_df = MACalculator.calculate_ma_for_dataframe(df, periods=[5, 10, 20, 30, 60, 120, 200])
                    
                    # 保存MA数据（只保存目标日期的数据）
                    saved = False
                    for _, row in ma_df.iterrows():
                        date_str = row['date'].strftime('%Y-%m-%d') if isinstance(row['date'], pd.Timestamp) else str(row['date'])
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
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
                                'market_type': 'CN',
                                'ma5': self._safe_value(row.get('ma5')),
                                'ma10': self._safe_value(row.get('ma10')),
                                'ma20': self._safe_value(row.get('ma20')),
                                'ma30': self._safe_value(row.get('ma30')),
                                'ma60': self._safe_value(row.get('ma60')),
                                'ma120': self._safe_value(row.get('ma120')),
                                'ma200': self._safe_value(row.get('ma200')),
                                'created_at': datetime.datetime.now()
                            })
                            saved = True
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} MA数据失败: {e}")
                            continue
                    
                    if saved:
                        success_count += 1
                    else:
                        skipped_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
                    self.logger.error(f"计算股票 {stock_code} MA指标失败: {e}")
                    continue
            
            # 提交事务
            session.commit()
            
            return {
                'total': len(stock_codes),
                'success': success_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'details': failed_details
            }
            
        except Exception as e:
            self.logger.error(f"批量计算MA指标失败: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': 0,
                'skipped': 0,
                'failed': 0,
                'details': [str(e)]
            }
    
    def _calculate_and_save_kdj_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """
        计算并保存指定日期的KDJ指标
        
        Args:
            session: 数据库会话
            target_date: 目标日期 (YYYY-MM-DD)
            
        Returns:
            dict: 计算结果统计
        """
        try:
            # 获取该日期所有有数据的股票代码
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            
            stock_codes = [row[0] for row in result.fetchall()]
            
            # 如果提供了自选股列表，则只计算自选股
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
                self.logger.info(f"限制为 {len(stock_codes)} 只自选股计算KDJ")

            if not stock_codes:
                self.logger.warning(f"日期 {target_date} 没有股票数据")
                return {
                    'total': 0,
                    'success': 0,
                    'skipped': 0,
                    'failed': 0,
                    'details': []
                }
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            
            # 查询开始日期（需要至少9天历史数据用于KDJ）
            query_start_date = (datetime.datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            
            calculator = KDJCalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少9天的收盘价、最高价、最低价数据
                    result = session.execute(text("""
                        SELECT date, close, high, low 
                        FROM historical_quotes 
                        WHERE code = :stock_code 
                        AND date >= :query_start_date 
                        AND date <= :target_date
                        AND close IS NOT NULL 
                        AND high IS NOT NULL 
                        AND low IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'query_start_date': query_start_date,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 9:  # 至少需要9天数据才能计算KDJ
                        skipped_count += 1
                        continue
                    
                    # 提取数据列表
                    dates = []
                    closes = []
                    highs = []
                    lows = []
                    for row in rows:
                        date_val = row[0]
                        if isinstance(date_val, datetime.datetime):
                            date_str = date_val.strftime('%Y-%m-%d')
                        elif isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = str(date_val)
                        dates.append(date_str)
                        closes.append(float(row[1]))
                        highs.append(float(row[2]))
                        lows.append(float(row[3]))
                    
                    # 批量计算KDJ
                    kdj_results = calculator.calculate_kdj_batch(closes, highs, lows)
                    
                    if not kdj_results:
                        failed_count += 1
                        failed_details.append(f"{stock_code}: KDJ计算失败")
                        continue
                    
                    # 保存KDJ数据（只保存目标日期的数据）
                    saved = False
                    for i, kdj_data in enumerate(kdj_results):
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
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
                                'created_at': datetime.datetime.now()
                            })
                            saved = True
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} KDJ数据失败: {e}")
                            continue
                    
                    if saved:
                        success_count += 1
                    else:
                        skipped_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
                    self.logger.error(f"计算股票 {stock_code} KDJ指标失败: {e}")
                    continue
            
            # 提交事务
            session.commit()
            
            return {
                'total': len(stock_codes),
                'success': success_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'details': failed_details
            }
            
        except Exception as e:
            self.logger.error(f"批量计算KDJ指标失败: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': 0,
                'skipped': 0,
                'failed': 0,
                'details': [str(e)]
            }
    
    def _calculate_and_save_rsi_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """
        计算并保存指定日期的RSI指标
        
        Args:
            session: 数据库会话
            target_date: 目标日期 (YYYY-MM-DD)
            
        Returns:
            dict: 计算结果统计
        """
        try:
            # 获取该日期所有有数据的股票代码
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            
            stock_codes = [row[0] for row in result.fetchall()]
            
            # 如果提供了自选股列表，则只计算自选股
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
                self.logger.info(f"限制为 {len(stock_codes)} 只自选股计算RSI")

            if not stock_codes:
                self.logger.warning(f"日期 {target_date} 没有股票数据")
                return {
                    'total': 0,
                    'success': 0,
                    'skipped': 0,
                    'failed': 0,
                    'details': []
                }
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            
            # 查询开始日期（需要至少30天历史数据用于RSI24）
            query_start_date = (datetime.datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
            
            calculator = RSICalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的收盘价数据
                    result = session.execute(text("""
                        SELECT date, close 
                        FROM historical_quotes 
                        WHERE code = :stock_code 
                        AND date >= :query_start_date 
                        AND date <= :target_date
                        AND close IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'query_start_date': query_start_date,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 7:  # rsi6至少需要7天数据
                        skipped_count += 1
                        continue
                    
                    # 提取数据列表
                    dates = []
                    closes = []
                    for row in rows:
                        date_val = row[0]
                        if isinstance(date_val, datetime.datetime):
                            date_str = date_val.strftime('%Y-%m-%d')
                        elif isinstance(date_val, str):
                            date_str = date_val
                        else:
                            date_str = str(date_val)
                        dates.append(date_str)
                        closes.append(float(row[1]))
                    
                    # 批量计算RSI
                    rsi_results = calculator.calculate_rsi_batch(closes)
                    
                    if not rsi_results:
                        failed_count += 1
                        failed_details.append(f"{stock_code}: RSI计算失败")
                        continue
                    
                    # 保存RSI数据（只保存目标日期的数据）
                    saved = False
                    for i, rsi_data in enumerate(rsi_results):
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
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
                                'created_at': datetime.datetime.now()
                            })
                            saved = True
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} RSI数据失败: {e}")
                            continue
                    
                    if saved:
                        success_count += 1
                    else:
                        skipped_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
                    self.logger.error(f"计算股票 {stock_code} RSI指标失败: {e}")
                    continue
            
            # 提交事务
            session.commit()
            
            return {
                'total': len(stock_codes),
                'success': success_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'details': failed_details
            }
            
        except Exception as e:
            self.logger.error(f"批量计算RSI指标失败: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': 0,
                'skipped': 0,
                'failed': 0,
                'details': [str(e)]
            }

    def _calculate_and_save_boll_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """计算并保存指定日期的BOLL指标"""
        try:
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            stock_codes = [row[0] for row in result.fetchall()]
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
            if not stock_codes:
                return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': []}
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            query_start_date = (datetime.datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            calculator = BOLLCalculator()
            for stock_code in stock_codes:
                try:
                    result = session.execute(text("""
                        SELECT date, close FROM historical_quotes 
                        WHERE code = :stock_code AND date >= :query_start_date AND date <= :target_date
                        AND close IS NOT NULL ORDER BY date ASC
                    """), {'stock_code': stock_code, 'query_start_date': query_start_date, 'target_date': target_date})
                    rows = result.fetchall()
                    if len(rows) < 20:
                        skipped_count += 1
                        continue
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    boll_results = calculator.calculate_boll_batch(closes)
                    if not boll_results:
                        failed_count += 1
                        continue
                    saved = False
                    for i, boll_data in enumerate(boll_results):
                        # 处理日期格式，确保与 target_date 一致
                        date_val = dates[i]
                        if isinstance(date_val, datetime.datetime):
                           date_str = date_val.strftime('%Y-%m-%d')
                        else:
                           date_str = str(date_val)
                           
                        if date_str != target_date: continue
                        session.execute(text("""
                            INSERT INTO boll_indicators (code, date, market_type, mid, upper, lower, created_at)
                            VALUES (:code, :date, :market_type, :mid, :upper, :lower, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                mid = EXCLUDED.mid, upper = EXCLUDED.upper, lower = EXCLUDED.lower, created_at = EXCLUDED.created_at
                        """), {
                            'code': stock_code, 'date': date_str, 'market_type': 'CN',
                            'mid': boll_data.get('mid'), 'upper': boll_data.get('upper'), 'lower': boll_data.get('lower'),
                            'created_at': datetime.datetime.now()
                        })
                        saved = True
                    if saved: success_count += 1
                    else: skipped_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
            session.commit()
            return {'total': len(stock_codes), 'success': success_count, 'skipped': skipped_count, 'failed': failed_count, 'details': failed_details}
        except Exception as e:
            session.rollback()
            return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': [str(e)]}

    def _calculate_and_save_mavol_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """计算并保存指定日期的MAVOL指标"""
        try:
            result = session.execute(text("""
                SELECT DISTINCT code 
                FROM historical_quotes 
                WHERE date = :target_date
            """), {'target_date': target_date})
            stock_codes = [row[0] for row in result.fetchall()]
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
            if not stock_codes:
                return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': []}
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            # 查询所有历史数据（不限制日期范围，确保有足够数据计算MAVOL200）
            # 注意：MAVOL200需要至少200个交易日，约300个日历天，但为了保险起见，查询所有历史数据
            calculator = MAVOLCalculator()
            for stock_code in stock_codes:
                try:
                    result = session.execute(text("""
                        SELECT date, volume FROM historical_quotes 
                        WHERE code = :stock_code AND date <= :target_date
                        AND volume IS NOT NULL ORDER BY date ASC
                    """), {'stock_code': stock_code, 'target_date': target_date})
                    rows = result.fetchall()
                    if len(rows) < 5:
                        skipped_count += 1
                        continue
                    dates = [str(row[0]) for row in rows]
                    volumes = [float(row[1]) for row in rows]
                    mavol_results = calculator.calculate_mavol_batch(volumes)
                    if not mavol_results:
                        failed_count += 1
                        continue
                    saved = False
                    for i, mavol_data in enumerate(mavol_results):
                        # 处理日期格式
                        date_val = dates[i]
                        if isinstance(date_val, datetime.datetime):
                           date_str = date_val.strftime('%Y-%m-%d')
                        else:
                           date_str = str(date_val)
                           
                        if date_str != target_date: continue
                        session.execute(text("""
                            INSERT INTO mavol_indicators (code, date, market_type, mavol5, mavol10, mavol20, mavol30, mavol60, mavol120, mavol200, created_at)
                            VALUES (:code, :date, :market_type, :m5, :m10, :m20, :m30, :m60, :m120, :m200, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                mavol5 = EXCLUDED.mavol5, mavol10 = EXCLUDED.mavol10, mavol20 = EXCLUDED.mavol20,
                                mavol30 = EXCLUDED.mavol30, mavol60 = EXCLUDED.mavol60, mavol120 = EXCLUDED.mavol120,
                                mavol200 = EXCLUDED.mavol200, created_at = EXCLUDED.created_at
                        """), {
                            'code': stock_code, 'date': date_str, 'market_type': 'CN',
                            'm5': mavol_data.get('mavol5'), 'm10': mavol_data.get('mavol10'), 'm20': mavol_data.get('mavol20'),
                            'm30': mavol_data.get('mavol30'), 'm60': mavol_data.get('mavol60'), 'm120': mavol_data.get('mavol120'),
                            'm200': mavol_data.get('mavol200'), 'created_at': datetime.datetime.now()
                        })
                        saved = True
                    if saved: success_count += 1
                    else: skipped_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
            session.commit()
            return {'total': len(stock_codes), 'success': success_count, 'skipped': skipped_count, 'failed': failed_count, 'details': failed_details}
        except Exception as e:
            session.rollback()
            return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': [str(e)]}

    def _calculate_and_save_mean_frequency_for_date(self, session, target_date: str, watchlist_codes: Optional[set] = None) -> dict:
        """计算并保存指定日期的均值频率共振指标"""
        try:
            result = session.execute(text("""
                SELECT DISTINCT code FROM historical_quotes WHERE date = :target_date
            """), {'target_date': target_date})
            stock_codes = [row[0] for row in result.fetchall()]
            if watchlist_codes is not None:
                stock_codes = [code for code in stock_codes if code in watchlist_codes]
            if not stock_codes:
                return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': []}
            
            success_count = 0
            skipped_count = 0
            failed_count = 0
            failed_details = []
            query_start_date = (datetime.datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
            calculator = MeanFrequencyResonanceCalculator()
            for stock_code in stock_codes:
                try:
                    result = session.execute(text("""
                        SELECT date, close, volume FROM historical_quotes 
                        WHERE code = :stock_code AND date >= :query_start_date AND date <= :target_date
                        AND close IS NOT NULL AND volume IS NOT NULL ORDER BY date ASC
                    """), {'stock_code': stock_code, 'query_start_date': query_start_date, 'target_date': target_date})
                    rows = result.fetchall()
                    if len(rows) < 20:
                        skipped_count += 1
                        continue
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    volumes = [float(row[2]) for row in rows]
                    mf_results = calculator.calculate(closes, volumes)
                    if not mf_results:
                        failed_count += 1
                        continue
                    saved = False
                    for i, res in enumerate(mf_results):
                        if res is None: continue
                        
                        # 处理日期格式
                        date_val = dates[i]
                        if isinstance(date_val, datetime.datetime):
                           date_str = date_val.strftime('%Y-%m-%d')
                        else:
                           date_str = str(date_val)
                           
                        if date_str != target_date: continue
                        
                        session.execute(text("""
                            INSERT INTO mean_frequency_resonance_indicators
                            (code, date, market_type, macro_displacement_delta, ratio_d20, ratio_d1, instant_deviation, rising_days_z, falling_days_f,
                             efficiency_m20_minus_m, ma20_d, mavol20_m, bias, created_at)
                            VALUES (:code, :date, :market_type, :delta, :ratio_d20, :ratio_d1, :instant_deviation, :z, :f, :efficiency, :ma20, :mavol20, :bias, :created_at)
                            ON CONFLICT (code, date, market_type) DO UPDATE SET
                                macro_displacement_delta = EXCLUDED.macro_displacement_delta,
                                ratio_d20 = EXCLUDED.ratio_d20,
                                ratio_d1 = EXCLUDED.ratio_d1,
                                instant_deviation = EXCLUDED.instant_deviation,
                                rising_days_z = EXCLUDED.rising_days_z,
                                falling_days_f = EXCLUDED.falling_days_f,
                                efficiency_m20_minus_m = EXCLUDED.efficiency_m20_minus_m,
                                ma20_d = EXCLUDED.ma20_d,
                                mavol20_m = EXCLUDED.mavol20_m,
                                bias = EXCLUDED.bias,
                                created_at = EXCLUDED.created_at
                        """), {
                            'code': stock_code, 'date': date_str, 'market_type': 'CN',
                            'delta': res['macro_displacement_delta'],
                            'ratio_d20': res.get('ratio_d20'), 'ratio_d1': res.get('ratio_d1'),
                            'instant_deviation': res['instant_deviation'],
                            'z': res['rising_days_z'], 'f': res['falling_days_f'], 'efficiency': res['efficiency_m20_minus_m'],
                            'ma20': res['ma20_d'], 'mavol20': res['mavol20_m'], 'bias': res['bias'],
                            'created_at': datetime.datetime.now()
                        })
                        saved = True
                    if saved: success_count += 1
                    else: skipped_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{stock_code}: {str(e)}")
            session.commit()
            return {'total': len(stock_codes), 'success': success_count, 'skipped': skipped_count, 'failed': failed_count, 'details': failed_details}
        except Exception as e:
            session.rollback()
            return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0, 'details': [str(e)]}

    def collect_historical_quotes(self, date_str: str) -> bool:
        self._init_db()  # 初始化表结构
        session = SessionLocal()  # 新建 session
        try:
            input_params = {'date': date_str}
            collect_date = datetime.date.today().isoformat()
            success_count = 0
            fail_count = 0
            fail_detail = []
            # 设置 tushare token
            ts.set_token(self.config['token'])
            pro = ts.pro_api()
            df = pro.daily(trade_date=date_str)  # 这里需要根据tushare实际API替换
            self.logger.info("采集到 %d 条历史行情数据", len(df))
            try:
                for _, row in df.iterrows():
                    pass  # 这里的 pass 只是占位，实际循环体在后面
            except Exception as e:
                self.logger.error(f"遍历历史行情数据时发生异常: {e}")
                import sys
                sys.exit(1)
            for _, row in df.iterrows():
                try:
                    code = self.extract_code_from_ts_code(row['ts_code'])
                    ts_code = row['ts_code']
                    # 从 stock_basic_info 表读取 name
                    result = session.execute(
                        text('SELECT name FROM stock_basic_info WHERE code = :code'),
                        {'code': code}
                    ).fetchone()
                    name = result[0] if result and result[0] else ''
                    market = row.get('market', '')
                    # 计算振幅
                    # 振幅 = (最高价 - 最低价) / 昨收盘价 * 100
                    pre_close = self._safe_value(row['pre_close'])
                    high = self._safe_value(row['high'])
                    low = self._safe_value(row['low'])

                    amplitude = None
                    if pre_close and pre_close > 0 and high is not None and low is not None:
                        amplitude = (high - low) / pre_close * 100

                    # 从实时行情表获取换手率数据
                    turnover_rate = None
                    try:
                        # 查询实时行情表中的换手率
                        result_turnover = session.execute(text('''
                            SELECT turnover_rate 
                            FROM stock_realtime_quote 
                            WHERE code = :code AND trade_date = :trade_date
                        '''), {
                            'code': code, 
                            'trade_date': datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        })
                        
                        row_turnover = result_turnover.fetchone()
                        if row_turnover and row_turnover[0] is not None:
                            turnover_rate = float(row_turnover[0])
                            self.logger.debug(f"从实时行情表获取股票 {code} 换手率: {turnover_rate}")
                        else:
                            self.logger.debug(f"实时行情表中未找到股票 {code} 的换手率数据")
                            
                    except Exception as e:
                        self.logger.warning(f"从实时行情表获取换手率失败: {e}")
                        turnover_rate = None
                    # 打印前面取得的参数
                    #self.logger.info(f"参数: code={code}, ts_code={ts_code}, name={name}, market={market}, pre_close={pre_close}, high={high}, low={low}, turnover_rate={turnover_rate}, amplitude={amplitude}")

                    data = {
                        'code': code,
                        'ts_code': ts_code,
                        'name': name,
                        'market': market,
                        'date': datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                        'collected_source': 'tushare',
                        'collected_date': datetime.datetime.now().isoformat(),
                        'open': self._safe_value(row['open']),
                        'high': high,
                        'low': low,
                        'close': self._safe_value(row['close']),
                        'volume': self._safe_value(row['vol']),
                        # tushare返回的amount单位是千元，需折算为元
                        'amount': self._safe_value(row['amount']) * 1000 if self._safe_value(row['amount']) is not None else None,
                        'change_percent': self._safe_value(row['pct_chg']),
                        'pre_close': pre_close,
                        'change': self._safe_value(row['change']),
                        'turnover_rate': turnover_rate,
                        'amplitude': amplitude
                    }
                    
                    # 使用重试机制处理死锁
                    max_retries = 3
                    retry_count = 0
                    
                    while retry_count < max_retries:
                        try:
                            # 先尝试插入 stock_basic_info（如果不存在）
                            session.execute(text('''
                                INSERT INTO stock_basic_info (code, name)
                                VALUES (:code, :name)
                                ON CONFLICT (code) DO NOTHING
                            '''), {'code': data['code'], 'name': data['name']})
                            
                            # 然后插入 historical_quotes
                            session.execute(text('''
                                INSERT INTO historical_quotes
                                (code, ts_code, name, market, collected_source, collected_date, date, open, high, low, close, volume, amount, change_percent, pre_close, change, amplitude, turnover_rate)
                                VALUES (:code, :ts_code, :name, :market, :collected_source, :collected_date, :date, :open, :high, :low, :close, :volume, :amount, :change_percent, :pre_close, :change, :amplitude, :turnover_rate)
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
                            '''), data)
                            
                            # 每100条记录提交一次，减少事务数量
                            if success_count % 100 == 0:
                                session.commit()
                                self.logger.info(f"已处理 {success_count} 条记录，提交事务")
                            
                            success_count += 1
                            break  # 成功插入，跳出重试循环
                            
                        except Exception as insert_error:
                            # 如果是死锁错误，回滚并重试
                            if "DeadlockDetected" in str(insert_error):
                                retry_count += 1
                                self.logger.warning(f"检测到死锁，第 {retry_count} 次重试: {insert_error}")
                                session.rollback()
                                # 短暂等待后重试
                                import time
                                time.sleep(0.1 * retry_count)  # 递增等待时间
                                continue
                            else:
                                # 其他错误，直接抛出
                                raise insert_error
                    
                    # 如果重试次数用完仍然失败
                    if retry_count >= max_retries:
                        fail_count += 1
                        fail_detail.append(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                        self.logger.error(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                        continue
                        
                except Exception as row_e:
                    fail_count += 1
                    fail_detail.append(str(row_e))
                    self.logger.error(f"采集单条数据失败: {row_e}")
                    # 移除 sys.exit(1)，避免程序退出
                    continue
            # 记录采集日志（汇总信息）
            session.execute(text('''
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message)
            '''), {
                'operation_type': 'historical_quote_collect',
                'operation_desc': f'采集日期: {collect_date}\n输入参数: {input_params}\n成功记录数: {success_count}\n失败记录数: {fail_count}',
                'affected_rows': success_count,
                'status': 'success' if fail_count == 0 else 'partial_success',
                'error_message': '\n'.join(fail_detail) if fail_count > 0 else None
            })
            session.commit()
            self.logger.info(f"全部历史行情数据采集并入库完成，成功: {success_count}，失败: {fail_count}")
            
            # 数据采集完成后，自动计算扩展涨跌幅（5日、10日、60日）
            if success_count > 0:
                try:
                    self.logger.info("开始自动计算扩展涨跌幅（5日、10日、60日）...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    calculator = ExtendedChangeCalculator(session)
                    calc_result = calculator.calculate_for_date(target_date)
                    
                    self.logger.info(f"扩展涨跌幅计算完成: 总计 {calc_result['total']}, 成功 {calc_result['success']}, 失败 {calc_result['failed']}")
                    
                    # 记录扩展涨跌幅计算日志
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'extended_change_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {calc_result["total"]}\n成功计算: {calc_result["success"]}\n失败计算: {calc_result["failed"]}',
                        'affected_rows': calc_result['success'],
                        'status': 'success' if calc_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(calc_result['details']) if calc_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                    
                except Exception as calc_error:
                    self.logger.error(f"自动计算扩展涨跌幅失败: {calc_error}")
                    # 记录计算失败日志
                    try:
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'extended_change_calculation',
                            'operation_desc': f'计算日期: {datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(calc_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录扩展涨跌幅计算失败日志时出错: {log_error}")
                
                # 扩展涨跌幅计算完成后，再计算30日涨跌幅
                try:
                    self.logger.info("开始自动计算30日涨跌幅...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    thirty_calculator = ThirtyDayChangeCalculator(session)
                    thirty_result = thirty_calculator.calculate_for_date(target_date)

                    self.logger.info(
                        "30日涨跌幅计算完成: 总计 %d, 成功 %d, 失败 %d",
                        thirty_result['total'],
                        thirty_result['success'],
                        thirty_result['failed']
                    )

                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'thirty_day_change_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {thirty_result["total"]}\n成功计算: {thirty_result["success"]}\n失败计算: {thirty_result["failed"]}',
                        'affected_rows': thirty_result['success'],
                        'status': 'success' if thirty_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(thirty_result['details']) if thirty_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()

                except Exception as calc_error:
                    self.logger.error(f"自动计算30日涨跌幅失败: {calc_error}")
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'thirty_day_change_calculation',
                            'operation_desc': f'计算日期: {target_date}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(calc_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录30日涨跌幅计算失败日志时出错: {log_error}")
                
                # 30日涨跌幅计算完成后，再计算MACD等指标（仅针对自选股）
                try:
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    
                    # 获取自选股列表
                    watchlist_codes = self._get_watchlist_codes(session)
                    self.logger.info(f"获取到 {len(watchlist_codes)} 只自选股")

                    self.logger.info("开始自动计算MACD指标...")
                    macd_result = self._calculate_and_save_macd_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    
                    self.logger.info(
                        "MACD指标计算完成: 总计 %d, 成功 %d, 跳过 %d, 失败 %d",
                        macd_result['total'],
                        macd_result['success'],
                        macd_result['skipped'],
                        macd_result['failed']
                    )
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'macd_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {macd_result["total"]}\n成功计算: {macd_result["success"]}\n跳过: {macd_result["skipped"]}\n失败计算: {macd_result["failed"]}',
                        'affected_rows': macd_result['success'],
                        'status': 'success' if macd_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(macd_result['details']) if macd_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                    
                except Exception as macd_error:
                    self.logger.error(f"自动计算MACD指标失败: {macd_error}")
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'macd_calculation',
                            'operation_desc': f'计算日期: {target_date}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(macd_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录MACD计算失败日志时出错: {log_error}")
                
                # MACD指标计算完成后，再计算MA指标
                try:
                    self.logger.info("开始自动计算MA指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    ma_result = self._calculate_and_save_ma_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    
                    self.logger.info(
                        "MA指标计算完成: 总计 %d, 成功 %d, 跳过 %d, 失败 %d",
                        ma_result['total'],
                        ma_result['success'],
                        ma_result['skipped'],
                        ma_result['failed']
                    )
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'ma_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {ma_result["total"]}\n成功计算: {ma_result["success"]}\n跳过: {ma_result["skipped"]}\n失败计算: {ma_result["failed"]}',
                        'affected_rows': ma_result['success'],
                        'status': 'success' if ma_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(ma_result['details']) if ma_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                    
                except Exception as ma_error:
                    self.logger.error(f"自动计算MA指标失败: {ma_error}")
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'ma_calculation',
                            'operation_desc': f'计算日期: {target_date}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(ma_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录MA计算失败日志时出错: {log_error}")
                
                # MA指标计算完成后，再计算KDJ指标
                try:
                    self.logger.info("开始自动计算KDJ指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    kdj_result = self._calculate_and_save_kdj_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    
                    self.logger.info(
                        "KDJ指标计算完成: 总计 %d, 成功 %d, 跳过 %d, 失败 %d",
                        kdj_result['total'],
                        kdj_result['success'],
                        kdj_result['skipped'],
                        kdj_result['failed']
                    )
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'kdj_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {kdj_result["total"]}\n成功计算: {kdj_result["success"]}\n跳过: {kdj_result["skipped"]}\n失败计算: {kdj_result["failed"]}',
                        'affected_rows': kdj_result['success'],
                        'status': 'success' if kdj_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(kdj_result['details']) if kdj_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                    
                except Exception as kdj_error:
                    self.logger.error(f"自动计算KDJ指标失败: {kdj_error}")
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'kdj_calculation',
                            'operation_desc': f'计算日期: {target_date}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(kdj_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录KDJ计算失败日志时出错: {log_error}")
                
                # KDJ指标计算完成后，再计算RSI指标
                try:
                    self.logger.info("开始自动计算RSI指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    rsi_result = self._calculate_and_save_rsi_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    
                    self.logger.info(
                        "RSI指标计算完成: 总计 %d, 成功 %d, 跳过 %d, 失败 %d",
                        rsi_result['total'],
                        rsi_result['success'],
                        rsi_result['skipped'],
                        rsi_result['failed']
                    )
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'rsi_calculation',
                        'operation_desc': f'计算日期: {target_date}\n总计股票: {rsi_result["total"]}\n成功计算: {rsi_result["success"]}\n跳过: {rsi_result["skipped"]}\n失败计算: {rsi_result["failed"]}',
                        'affected_rows': rsi_result['success'],
                        'status': 'success' if rsi_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(rsi_result['details']) if rsi_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                    
                except Exception as rsi_error:
                    self.logger.error(f"自动计算RSI指标失败: {rsi_error}")
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                        session.execute(text('''
                            INSERT INTO historical_collect_operation_logs 
                            (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                            VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                        '''), {
                            'operation_type': 'rsi_calculation',
                            'operation_desc': f'计算日期: {target_date}',
                            'affected_rows': 0,
                            'status': 'error',
                            'error_message': str(rsi_error),
                            'collect_source': 'tushare'
                        })
                        session.commit()
                    except Exception as log_error:
                        self.logger.error(f"记录RSI计算失败日志时出错: {log_error}")

                # RSI指标计算完成后，计算BOLL指标
                try:
                    self.logger.info("开始自动计算BOLL指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    boll_result = self._calculate_and_save_boll_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    self.logger.info(f"BOLL指标计算完成: 成功 {boll_result['success']}, 失败 {boll_result['failed']}")
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'boll_calculation',
                        'operation_desc': f'计算日期: {target_date}',
                        'affected_rows': boll_result['success'],
                        'status': 'success' if boll_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(boll_result['details']) if boll_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                except Exception as boll_error:
                    self.logger.error(f"自动计算BOLL指标失败: {boll_error}")

                # 计算MAVOL指标
                try:
                    self.logger.info("开始自动计算MAVOL指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    mavol_result = self._calculate_and_save_mavol_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    self.logger.info(f"MAVOL指标计算完成: 成功 {mavol_result['success']}, 失败 {mavol_result['failed']}")
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'mavol_calculation',
                        'operation_desc': f'计算日期: {target_date}',
                        'affected_rows': mavol_result['success'],
                        'status': 'success' if mavol_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(mavol_result['details']) if mavol_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                except Exception as mavol_error:
                    self.logger.error(f"自动计算MAVOL指标失败: {mavol_error}")

                # 计算均值频率共振 (PVFRS) 指标
                try:
                    self.logger.info("开始自动计算均值频率共振指标...")
                    target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    mf_result = self._calculate_and_save_mean_frequency_for_date(session, target_date, watchlist_codes=watchlist_codes)
                    self.logger.info(f"均值频率共振指标计算完成: 成功 {mf_result['success']}, 失败 {mf_result['failed']}")
                    
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'mean_frequency_resonance_calculation',
                        'operation_desc': f'计算日期: {target_date}',
                        'affected_rows': mf_result['success'],
                        'status': 'success' if mf_result['failed'] == 0 else 'partial_success',
                        'error_message': '\n'.join(mf_result['details']) if mf_result['failed'] > 0 else None,
                        'collect_source': 'tushare'
                    })
                    session.commit()
                except Exception as mf_error:
                    self.logger.error(f"自动计算均值频率共振指标失败: {mf_error}")
            
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            try:
                session.execute(text('''
                    INSERT INTO historical_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                '''), {
                    'operation_type': 'historical_quote_collect',
                    'operation_desc': f'采集日期: {datetime.date.today().isoformat()}\n输入参数: {input_params if "input_params" in locals() else ""}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': error_msg,
                    'collect_source': 'tushare'
                })
                session.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            return False
        finally:
            session.close()
