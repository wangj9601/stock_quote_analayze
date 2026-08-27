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
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.rsi_calculator import RSICalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from backend_core.data_collectors.batch_ma_mavol import calculate_and_save_ma_mavol_for_date
from backend_core.data_collectors.batch_mean_frequency import calculate_and_save_mean_frequency_for_date
from datetime import timedelta


def _format_exception_cause(exc: BaseException, max_len: int = 8000) -> str:
    """格式化异常及其链式原因，便于打印问题具体原因。"""
    parts = []
    current = exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = type(current).__name__
        msg = str(current).strip()
        if msg:
            parts.append(f"[{name}] {msg}")
        else:
            parts.append(f"[{name}]")
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    out = "\n根本原因(链): ".join(parts) if len(parts) > 1 else (parts[0] if parts else str(exc))
    return out[:max_len] + ("..." if len(out) > max_len else "")


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
                amplitude REAL,
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
        
        # 确保列存在（迁移逻辑）
        try:
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS amplitude REAL"))
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS ratio_d20 REAL"))
            session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS ratio_d1 REAL"))
        except Exception as e:
            self.logger.debug(f"通过ALTER TABLE添加列失败（可能列已存在）: {e}")
            
        session.commit()
        session.close()

    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    
    def extract_code_from_ts_code(self, ts_code: str) -> str:
        return ts_code.split(".")[0] if ts_code else ""

    def _code_to_ts_code(self, code: str) -> str:
        """根据 A 股代码推断 ts_code（如 000001 -> 000001.SZ）。"""
        if not code or len(code) < 6:
            return f"{code}.SZ"
        if code[0] == '6':
            return f"{code}.SH"
        if code[0] in ('0', '3'):
            return f"{code}.SZ"
        if code[0] in ('4', '8'):
            return f"{code}.BJ"
        return f"{code}.SZ"
    
    def _get_watchlist_codes(self, session) -> set:
        """获取所有用户的自选股代码"""
        try:
            result = session.execute(text("SELECT DISTINCT stock_code FROM watchlist"))
            return {str(row[0]) for row in result.fetchall()}
        except Exception as e:
            self.logger.error(f"获取自选股列表失败: {e}")
            return set()

    def _stock_codes_for_indicator_date(
        self,
        session,
        target_date: str,
        watchlist_codes: Optional[set] = None,
    ) -> Optional[list]:
        """全市场返回 None；自选股模式返回当日有 K 线的自选代码列表。"""
        if watchlist_codes is None:
            return None
        result = session.execute(
            text(
                """
                SELECT DISTINCT code
                FROM historical_quotes
                WHERE date = :target_date
                """
            ),
            {"target_date": target_date},
        )
        codes = [row[0] for row in result.fetchall() if row and row[0]]
        filtered = [code for code in codes if code in watchlist_codes]
        self.logger.info("限制为 %s 只自选股计算指标", len(filtered))
        return filtered

    def _calculate_and_save_ma_and_mavol_for_date(
        self,
        session,
        target_date: str,
        watchlist_codes: Optional[set] = None,
    ) -> dict:
        """一次预加载、并行计算、批量写入 MA + MAVOL。"""
        stock_codes = self._stock_codes_for_indicator_date(session, target_date, watchlist_codes)
        return calculate_and_save_ma_mavol_for_date(
            session,
            target_date,
            quotes_table="historical_quotes",
            market_type="CN",
            stock_codes=stock_codes,
            compute_ma=True,
            compute_mavol=True,
            log=self.logger,
        )

    def _calculate_and_save_ma_for_date(
        self, session, target_date: str, watchlist_codes: Optional[set] = None
    ) -> dict:
        stock_codes = self._stock_codes_for_indicator_date(session, target_date, watchlist_codes)
        result = calculate_and_save_ma_mavol_for_date(
            session,
            target_date,
            quotes_table="historical_quotes",
            market_type="CN",
            stock_codes=stock_codes,
            compute_ma=True,
            compute_mavol=False,
            log=self.logger,
        )
        return {
            "total": result.get("total", 0),
            "success": result.get("success", 0),
            "skipped": result.get("skipped", 0),
            "failed": result.get("failed", 0),
            "details": result.get("details", []),
        }

    def _calculate_and_save_mavol_for_date(
        self, session, target_date: str, watchlist_codes: Optional[set] = None
    ) -> dict:
        stock_codes = self._stock_codes_for_indicator_date(session, target_date, watchlist_codes)
        result = calculate_and_save_ma_mavol_for_date(
            session,
            target_date,
            quotes_table="historical_quotes",
            market_type="CN",
            stock_codes=stock_codes,
            compute_ma=False,
            compute_mavol=True,
            log=self.logger,
        )
        return {
            "total": result.get("total", 0),
            "success": result.get("success", 0),
            "skipped": result.get("skipped", 0),
            "failed": result.get("failed", 0),
            "details": result.get("details", []),
        }

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

    def _calculate_and_save_mean_frequency_for_date(
        self, session, target_date: str, watchlist_codes: Optional[set] = None
    ) -> dict:
        """批量预加载 + 内存计算 + 批量写入 PVFRS（GMS 上游指标）。"""
        stock_codes = self._stock_codes_for_indicator_date(session, target_date, watchlist_codes)
        return calculate_and_save_mean_frequency_for_date(
            session,
            target_date,
            quotes_table="historical_quotes",
            market_type="CN",
            stock_codes=stock_codes,
            include_ma60=True,
            log=self.logger,
        )

    def collect_historical_quotes(self, date_str: str) -> bool:
        self._init_db()  # 初始化表结构
        session = SessionLocal()  # 新建 session
        try:
            # 清除可能从连接池继承的失败事务状态，避免首条就报 InFailedSqlTransaction
            session.rollback()
            input_params = {'date': date_str}
            collect_date = datetime.date.today().isoformat()
            success_count = 0
            fail_count = 0
            fail_detail = []
            # 设置 tushare token
            ts.set_token(self.config['token'])
            pro = ts.pro_api()
            df = pro.daily(trade_date=date_str)  # 这里需要根据tushare实际API替换
            if df is None or (hasattr(df, "empty") and df.empty):
                self.logger.warning(
                    "tushare daily 返回空数据 (trade_date=%s)，不写入历史表，不执行 MA 等指标计算",
                    date_str,
                )
                try:
                    session.execute(text('''
                        INSERT INTO historical_collect_operation_logs
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                    '''), {
                        'operation_type': 'historical_quote_collect',
                        'operation_desc': f'采集日期: {collect_date}\n输入参数: {input_params}\ntushare daily 返回空',
                        'affected_rows': 0,
                        'status': 'error',
                        'error_message': 'tushare返回空数据',
                        'collect_source': 'tushare'
                    })
                    session.commit()
                except Exception as log_e:
                    self.logger.error("记录空数据日志失败: %s", log_e)
                return False
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
                        # Level 1: 查询实时行情表中的换手率
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
                            # Level 2: 从 stock_basic_info.free_float_shares 计算（tushare vol 为手，换手率需股/流通股：手*100）
                            vol_hand = self._safe_value(row['vol'])
                            if vol_hand and vol_hand > 0:
                                try:
                                    result_shares = session.execute(text('''
                                        SELECT free_float_shares FROM stock_basic_info WHERE code = :code
                                    '''), {'code': code})
                                    shares_row = result_shares.fetchone()
                                    if shares_row and shares_row[0] is not None and float(shares_row[0]) > 0:
                                        free_float_shares = float(shares_row[0])
                                        turnover_rate = round((vol_hand * 100) / free_float_shares * 100, 4)
                                        self.logger.debug(f"通过流通股本计算股票 {code} 换手率: {turnover_rate}")
                                    else:
                                        self.logger.debug(f"股票 {code} 无流通股本数据，无法计算换手率")
                                except Exception as e2:
                                    session.rollback()
                                    self.logger.debug(f"从流通股本计算换手率失败: {e2}")
                            
                    except Exception as e:
                        session.rollback()
                        self.logger.warning(f"从实时行情表获取换手率失败: {e}")
                        turnover_rate = None

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
                        # 历史行情表成交量按「手」存；tushare vol 单位已是手，直接写入
                        'volume': self._safe_value(row['vol']),
                        # tushare返回的amount单位是千元，需折算为元
                        'amount': self._safe_value(row['amount']) * 1000 if self._safe_value(row['amount']) is not None else None,
                        'change_percent': self._safe_value(row['pct_chg']),
                        'pre_close': pre_close,
                        'change': self._safe_value(row['change']),
                        'turnover_rate': turnover_rate,
                        'amplitude': amplitude
                    }
                    # 名称含「退」的股票（退市等）不再写入历史行情表
                    if '退' in (name or ''):
                        continue
                    
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
                                # 其他错误：先回滚再抛出，便于外层写日志
                                session.rollback()
                                raise insert_error
                    
                    # 如果重试次数用完仍然失败，视为数据库错误并退出本次运行
                    if retry_count >= max_retries:
                        session.rollback()
                        self.logger.error("股票 %s 插入失败，重试 %s 次后仍然死锁，退出本次运行", code, max_retries)
                        raise RuntimeError(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                        
                except Exception as row_e:
                    # 出现一次数据库错误即回滚并退出本次运行，避免事务进入失败状态后继续执行报 InFailedSqlTransaction
                    session.rollback()
                    cause_str = _format_exception_cause(row_e)
                    self.logger.error("采集单条数据失败，退出本次运行。问题具体原因: %s", cause_str, exc_info=True)
                    raise
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
            
            # 数据采集完成后，自动计算扩展涨跌幅与各类指标
            if success_count > 0:
                self._run_indicators_for_date(session, date_str)
                self._run_full_market_supplement_indicators(session, date_str)
            
            return True
        except Exception as e:
            error_msg = str(e)
            cause_str = _format_exception_cause(e)
            self.logger.error("采集或入库时出错。问题具体原因: %s", cause_str, exc_info=True)
            try:
                # 事务已失败时必须先 rollback，否则后续任何 execute 都会报 InFailedSqlTransaction
                session.rollback()
                # 错误信息过长时截断，避免日志表字段或网络限制；写入库的日志包含完整异常链
                log_error_msg = cause_str if len(cause_str) <= 10000 else cause_str[:10000] + "\n...(truncated)"
                session.execute(text('''
                    INSERT INTO historical_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                '''), {
                    'operation_type': 'historical_quote_collect',
                    'operation_desc': f'采集日期: {datetime.date.today().isoformat()}\n输入参数: {input_params if "input_params" in locals() else ""}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': log_error_msg,
                    'collect_source': 'tushare'
                })
                session.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            return False
        finally:
            try:
                session.rollback()
            except Exception:
                pass
            session.close()

    def collect_historical_quotes_from_realtime(self, date_str: str) -> bool:
        """
        当 A 股实时行情表存在对应交易日期的数据时，从实时表同步到历史表。
        调用方应在返回 False 时改用 tushare 接口采集。

        Args:
            date_str: 交易日期，格式 YYYYMMDD

        Returns:
            True 表示已从实时表同步并完成；False 表示实时表无该日数据，应走 tushare。
        """
        self._init_db()
        session = SessionLocal()
        try:
            trade_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
            # 检查实时表是否有该交易日数据
            count_result = session.execute(
                text("SELECT COUNT(1) FROM stock_realtime_quote WHERE trade_date = :trade_date"),
                {'trade_date': trade_date}
            )
            row = count_result.fetchone()
            count = row[0] if row else 0
            if count == 0:
                self.logger.info(f"实时行情表无日期 {trade_date} 的数据，将走 tushare 采集")
                return False

            self.logger.info(f"从实时行情表同步历史数据，日期: {trade_date}，约 {count} 条")
            rows = session.execute(text("""
                SELECT code, name, current_price, change_percent, volume, amount, high, low, open, pre_close, turnover_rate
                FROM stock_realtime_quote
                WHERE trade_date = :trade_date
            """), {'trade_date': trade_date}).fetchall()

            success_count = 0
            fail_count = 0
            fail_detail = []
            for row in rows:
                code = row[0]
                name = row[1] or ''
                current_price = self._safe_value(row[2])
                change_percent = self._safe_value(row[3])
                # 历史行情表成交量按「手」存；实时表 volume 已为手，直接写入
                volume = self._safe_value(row[4])
                amount = self._safe_value(row[5])
                high = self._safe_value(row[6])
                low = self._safe_value(row[7])
                open_ = self._safe_value(row[8])
                pre_close = self._safe_value(row[9])
                turnover_rate = self._safe_value(row[10])

                if current_price is None:
                    fail_count += 1
                    fail_detail.append(f"{code}: 无收盘价")
                    continue

                amplitude = None
                if pre_close and pre_close > 0 and high is not None and low is not None:
                    amplitude = (high - low) / pre_close * 100
                change = (current_price - pre_close) if (current_price is not None and pre_close is not None) else None

                ts_code = self._code_to_ts_code(code)
                data = {
                    'code': code,
                    'ts_code': ts_code,
                    'name': name,
                    'market': '',
                    'date': trade_date,
                    'open': open_,
                    'high': high,
                    'low': low,
                    'close': current_price,
                    'pre_close': pre_close,
                    'volume': volume,
                    'amount': amount,
                    'amplitude': amplitude,
                    'turnover_rate': turnover_rate,
                    'change_percent': change_percent,
                    'change': change,
                    'collected_source': 'akshare_realtime',
                    'collected_date': datetime.datetime.now().isoformat(),
                }
                try:
                    session.execute(text('''
                        INSERT INTO stock_basic_info (code, name)
                        VALUES (:code, :name)
                        ON CONFLICT (code) DO NOTHING
                    '''), {'code': code, 'name': name})
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
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    fail_detail.append(f"{code}: {e}")
                    self.logger.debug(f"同步实时到历史失败 {code}: {e}")

            session.execute(text('''
                INSERT INTO historical_collect_operation_logs
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
            '''), {
                'operation_type': 'historical_quote_collect',
                'operation_desc': f'从实时表同步 日期: {trade_date}\n成功: {success_count}\n失败: {fail_count}',
                'affected_rows': success_count,
                'status': 'success' if fail_count == 0 else 'partial_success',
                'error_message': '\n'.join(fail_detail[:50]) if fail_detail else None,
                'collect_source': 'akshare_realtime'
            })
            session.commit()
            self.logger.info(f"从实时表同步历史行情完成，成功: {success_count}，失败: {fail_count}")

            if success_count > 0:
                self._run_indicators_for_date(session, date_str)
                self._run_full_market_supplement_indicators(session, date_str)
            return True
        except Exception as e:
            self.logger.error("从实时表同步历史行情失败: %s", e, exc_info=True)
            try:
                session.rollback()
                session.execute(text('''
                    INSERT INTO historical_collect_operation_logs
                    (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                '''), {
                    'operation_type': 'historical_quote_collect',
                    'operation_desc': f'从实时表同步 日期: {date_str}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': str(e),
                    'collect_source': 'akshare_realtime'
                })
                session.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            return False
        finally:
            session.close()

    def _run_full_market_supplement_indicators(self, session, date_str: str) -> None:
        """日 K 入库后补充全市场 MA / MAVOL / PVFRS（GMS）指标（不限于自选股）。"""
        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        for label, method in (
            ("MA+MAVOL", lambda: self._calculate_and_save_ma_and_mavol_for_date(session, target_date, watchlist_codes=None)),
            (
                "PVFRS（GMS）",
                lambda: self._calculate_and_save_mean_frequency_for_date(
                    session, target_date, watchlist_codes=None
                ),
            ),
        ):
            try:
                self.logger.info("开始全市场 %s 指标计算...", label)
                result = method()
                if isinstance(result, dict):
                    self.logger.info(
                        "全市场 %s 指标计算完成: 成功 %s, 失败 %s",
                        label,
                        result.get("success", 0),
                        result.get("failed", 0),
                    )
                session.commit()
            except Exception as e:
                self.logger.error("全市场 %s 指标计算失败: %s", label, e)
                try:
                    session.rollback()
                except Exception:
                    pass

    def _run_indicators_for_date(self, session, date_str: str) -> None:
        """采集写入 historical_quotes 后，为指定日期运行扩展涨跌幅与各类指标。date_str 格式 YYYYMMDD。"""
        target_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        watchlist_codes = self._get_watchlist_codes(session)
        try:
            self.logger.info("开始自动计算扩展涨跌幅（5日、10日、60日）...")
            calculator = ExtendedChangeCalculator(session)
            calc_result = calculator.calculate_for_date(target_date)
            self.logger.info(f"扩展涨跌幅计算完成: 总计 {calc_result['total']}, 成功 {calc_result['success']}, 失败 {calc_result['failed']}")
            session.execute(text('''
                INSERT INTO historical_collect_operation_logs
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
            '''), {
                'operation_type': 'extended_change_calculation',
                'operation_desc': f'计算日期: {target_date}\n总计: {calc_result["total"]}\n成功: {calc_result["success"]}\n失败: {calc_result["failed"]}',
                'affected_rows': calc_result['success'],
                'status': 'success' if calc_result['failed'] == 0 else 'partial_success',
                'error_message': '\n'.join(calc_result['details']) if calc_result['failed'] > 0 else None,
                'collect_source': 'tushare'
            })
            session.commit()
        except Exception as calc_error:
            self.logger.error("自动计算扩展涨跌幅失败: %s", calc_error)
            try:
                session.rollback()
                session.execute(text('''
                    INSERT INTO historical_collect_operation_logs
                    (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
                '''), {
                    'operation_type': 'extended_change_calculation',
                    'operation_desc': f'计算日期: {target_date}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': str(calc_error),
                    'collect_source': 'tushare'
                })
                session.commit()
            except Exception as log_error:
                self.logger.error("记录扩展涨跌幅计算失败日志时出错: %s", log_error)

        try:
            self.logger.info("开始自动计算30日涨跌幅...")
            thirty_calculator = ThirtyDayChangeCalculator(session)
            thirty_result = thirty_calculator.calculate_for_date(target_date)
            self.logger.info("30日涨跌幅计算完成: 总计 %d, 成功 %d, 失败 %d", thirty_result['total'], thirty_result['success'], thirty_result['failed'])
            session.execute(text('''
                INSERT INTO historical_collect_operation_logs
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source)
            '''), {
                'operation_type': 'thirty_day_change_calculation',
                'operation_desc': f'计算日期: {target_date}\n总计: {thirty_result["total"]}\n成功: {thirty_result["success"]}\n失败: {thirty_result["failed"]}',
                'affected_rows': thirty_result['success'],
                'status': 'success' if thirty_result['failed'] == 0 else 'partial_success',
                'error_message': '\n'.join(thirty_result['details']) if thirty_result['failed'] > 0 else None,
                'collect_source': 'tushare'
            })
            session.commit()
        except Exception as calc_error:
            self.logger.error("自动计算30日涨跌幅失败: %s", calc_error)
            try:
                session.rollback()
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
                self.logger.error("记录30日涨跌幅计算失败日志时出错: %s", log_error)

        for calc_name, calc_method in [
            ('MACD', lambda: self._calculate_and_save_macd_for_date(session, target_date, watchlist_codes=watchlist_codes)),
            ('MA+MAVOL', lambda: self._calculate_and_save_ma_and_mavol_for_date(session, target_date, watchlist_codes=watchlist_codes)),
            ('KDJ', lambda: self._calculate_and_save_kdj_for_date(session, target_date, watchlist_codes=watchlist_codes)),
            ('RSI', lambda: self._calculate_and_save_rsi_for_date(session, target_date, watchlist_codes=watchlist_codes)),
            ('BOLL', lambda: self._calculate_and_save_boll_for_date(session, target_date, watchlist_codes=watchlist_codes)),
            ('mean_frequency_resonance', lambda: self._calculate_and_save_mean_frequency_for_date(session, target_date, watchlist_codes=watchlist_codes)),
        ]:
            try:
                self.logger.info("开始自动计算%s指标...", calc_name)
                result = calc_method()
                if isinstance(result, dict):
                    self.logger.info("%s指标计算完成: 成功 %s, 失败 %s", calc_name, result.get('success', 0), result.get('failed', 0))
                session.commit()
            except Exception as err:
                self.logger.error("自动计算%s指标失败: %s", calc_name, err)
