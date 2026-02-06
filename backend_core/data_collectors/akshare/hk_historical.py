"""
港股历史行情数据采集器
负责采集港股历史行情数据并存储到数据库
"""

import time
import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime, timedelta

# 直接导入base模块
from .base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from backend_core.utils.macd_calculator import MACDCalculator
from backend_core.utils.kdj_calculator import KDJCalculator
from backend_core.utils.ma_calculator import MACalculator
from backend_core.utils.boll_calculator import BOLLCalculator
from backend_core.utils.mavol_calculator import MAVOLCalculator
from backend_core.utils.mean_frequency_calculator import MeanFrequencyResonanceCalculator
from backend_core.utils.rsi_calculator import RSICalculator

class HKHistoricalQuoteCollector(AKShareCollector):
    """港股历史行情数据采集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
        
    def _init_db(self) -> bool:
        """
        初始化数据库表结构
        
        Returns:
            bool: 是否成功
        """
        session = SessionLocal()
        try:
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS stock_basic_info_hk (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            session.commit()

            session.execute(text('''
                CREATE TABLE IF NOT EXISTS historical_quotes_hk (
                    code TEXT,
                    ts_code TEXT,
                    name TEXT,
                    english_name TEXT,
                    date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    pre_close REAL,
                    volume REAL,
                    amount REAL,
                    change_amount REAL,
                    amplitude REAL,
                    turnover_rate REAL,
                    change_percent REAL,
                    change_amount REAL,
                    five_day_change_percent REAL,
                    ten_day_change_percent REAL,
                    sixty_day_change_percent REAL,
                    thirty_day_change_percent REAL,
                    collected_source TEXT,
                    collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date)
                )
            '''))
            session.commit()
            
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
            session.commit()

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
            session.commit()

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

            return True
        except Exception as e:
            self.logger.error(f"初始化数据库表结构失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _safe_value(self, val: Any) -> Optional[float]:
        """
        安全地转换数值
        
        Args:
            val: 输入值
            
        Returns:
            Optional[float]: 转换后的浮点数，如果转换失败则返回None
        """
        return None if pd.isna(val) else float(val)
    
    def _get_watchlist_codes(self, session) -> set:
        """获取所有用户的自选股代码"""
        try:
            result = session.execute(text("SELECT DISTINCT stock_code FROM watchlist"))
            return {str(row[0]) for row in result.fetchall()}
        except Exception as e:
            self.logger.error(f"获取自选股列表失败: {e}")
            return set()
    
    def collect_historical_quotes(self, date_str: str, calculate_indicators: bool = True) -> bool:
        """
        采集指定日期的港股历史行情数据（从实时行情表读取并同步到历史行情表）
        
        Args:
            date_str: 日期字符串，格式：YYYYMMDD
            calculate_indicators: 是否计算指标
        
        Returns:
            bool: 是否成功
        """
        self._init_db()  # 确保表结构存在
        session = SessionLocal()
        start_time = time.time()
        try:
            # 将传入的日期字符串（YYYYMMDD）转为YYYY-MM-DD格式
            target_date = datetime.strptime(date_str, "%Y%m%d").strftime('%Y-%m-%d')
            collect_date = datetime.now().strftime('%Y-%m-%d')

            # 从stock_realtime_quote_hk表读取指定日期的全部数据
            try:
                result = session.execute(text(
                    "SELECT * FROM stock_realtime_quote_hk WHERE trade_date = :trade_date"
                ), {"trade_date": target_date})
                realtime_rows = result.fetchall()
                if not realtime_rows:
                    self.logger.warning(f"未找到港股实时行情表中 {target_date} 的数据，无需同步历史行情")
                    return False
                self.logger.info(f"发现 {len(realtime_rows)} 条 {target_date} 实时港股数据，准备同步至历史行情表")
            except Exception as e:
                self.logger.error(f"读取实时行情数据失败: {e}")
                session.close()
                return False
            
            read_time = time.time() - start_time
            self.logger.info(f"读取实时行情数据耗时: {read_time:.2f}s")

            # 获取字段名列表
            col_names = [col for col in result.keys()]
            
            # 按股票代码分组处理，以便计算涨跌幅
            stocks_data = {}
            for row in realtime_rows:
                record = dict(zip(col_names, row))
                stock_code = record.get('code')
                if stock_code not in stocks_data:
                    stocks_data[stock_code] = []
                stocks_data[stock_code].append(record)
            
            group_time = time.time() - (start_time + read_time)
            self.logger.info(f"汇总分组数据耗时: {group_time:.2f}s, 共 {len(stocks_data)} 只股票")

            loop_start = time.time()
            # 对每只股票进行处理
            affected = 0
            affected_stocks = set()
            insert_dicts = []
            
            # 定义 UPSERT 语句
            upsert_stmt = text("""
                INSERT INTO historical_quotes_hk (
                    code, name, date, english_name, close, open, high, low, pre_close, volume, amount,
                    change_percent, change_amount,
                    five_day_change_percent, ten_day_change_percent, sixty_day_change_percent, thirty_day_change_percent,
                    collected_source, collected_date, create_date
                ) VALUES (
                    :code, :name, :date, :english_name, :close, :open, :high, :low, :pre_close, :volume, :amount,
                    :change_percent, :change_amount,
                    :five_day_change_percent, :ten_day_change_percent, :sixty_day_change_percent, :thirty_day_change_percent,
                    :collected_source, :collected_date, :create_date
                )
                ON CONFLICT (code, date) DO UPDATE SET
                    name = EXCLUDED.name,
                    english_name = EXCLUDED.english_name,
                    close = EXCLUDED.close,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    pre_close = EXCLUDED.pre_close,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    change_percent = EXCLUDED.change_percent,
                    change_amount = EXCLUDED.change_amount,
                    five_day_change_percent = EXCLUDED.five_day_change_percent,
                    ten_day_change_percent = EXCLUDED.ten_day_change_percent,
                    sixty_day_change_percent = EXCLUDED.sixty_day_change_percent,
                    thirty_day_change_percent = EXCLUDED.thirty_day_change_percent,
                    collected_source = EXCLUDED.collected_source,
                    collected_date = EXCLUDED.collected_date,
                    create_date = EXCLUDED.create_date
            """)
            
            # 批量预加载历史数据
            all_codes = list(stocks_data.keys())
            min_hist_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
            self.logger.info(f"正在批量预加载 {len(all_codes)} 只股票的历史数据...")
            hist_fetch_start = time.time()
            hist_map = {}
            code_batches = [all_codes[i:i + 500] for i in range(0, len(all_codes), 500)]
            for code_batch in code_batches:
                hist_query = session.execute(text("""
                    SELECT code, date, close 
                    FROM historical_quotes_hk 
                    WHERE code IN :codes AND date >= :min_date
                    ORDER BY code, date ASC
                """), {"codes": tuple(code_batch), "min_date": min_hist_date})
                for h_code, h_date, h_close in hist_query.fetchall():
                    if h_code not in hist_map:
                        hist_map[h_code] = []
                    hist_map[h_code].append({'date': h_date, 'close': h_close})
            self.logger.info(f"批量预加载历史数据耗时: {time.time() - hist_fetch_start:.2f}s")

            for stock_code, records in stocks_data.items():
                try:
                    historical_data_list = hist_map.get(stock_code, [])
                    historical_df_data = [{'date': item['date'], 'close': item['close']} for item in historical_data_list]
                    
                    for record in records:
                        close_price = record.get('current_price')
                        if close_price:
                            historical_df_data.append({
                                'date': record.get('trade_date'),
                                'close': float(close_price)
                            })
                    
                    change_percents = {}
                    if historical_df_data:
                        df = pd.DataFrame(historical_df_data)
                        df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
                        
                        if 'close' in df.columns and len(df) > 0:
                            df['five_day_change_percent'] = df['close'].pct_change(periods=5, fill_method=None) * 100
                            df['ten_day_change_percent'] = df['close'].pct_change(periods=10, fill_method=None) * 100
                            df['thirty_day_change_percent'] = df['close'].pct_change(periods=30, fill_method=None) * 100
                            df['sixty_day_change_percent'] = df['close'].pct_change(periods=60, fill_method=None) * 100
                            
                            for _, row in df.iterrows():
                                change_percents[row['date']] = {
                                    'five_day_change_percent': self._safe_value(row.get('five_day_change_percent')),
                                    'ten_day_change_percent': self._safe_value(row.get('ten_day_change_percent')),
                                    'thirty_day_change_percent': self._safe_value(row.get('thirty_day_change_percent')),
                                    'sixty_day_change_percent': self._safe_value(row.get('sixty_day_change_percent'))
                                }
                    
                    for record in records:
                        if not record.get('current_price') or not record.get('open') or \
                           not record.get('high') or not record.get('low'):
                            continue

                        trade_date = record.get('trade_date')
                        change_data = change_percents.get(trade_date, {})
                        
                        insert_dicts.append({
                            'code': record.get('code'),
                            'name': record.get('name'),
                            'date': trade_date,
                            'english_name': record.get('english_name'),
                            'close': record.get('current_price'),
                            'open': record.get('open'),
                            'high': record.get('high'),
                            'low': record.get('low'),
                            'pre_close': record.get('pre_close'),
                            'volume': record.get('volume'),
                            'amount': record.get('amount'),
                            'change_percent': record.get('change_percent'),
                            'change_amount': record.get('change_amount'),
                            'collected_source': "akshare",
                            'collected_date': collect_date,
                            'create_date': datetime.now(),
                            'five_day_change_percent': change_data.get('five_day_change_percent'),
                            'ten_day_change_percent': change_data.get('ten_day_change_percent'),
                            'thirty_day_change_percent': change_data.get('thirty_day_change_percent'),
                            'sixty_day_change_percent': change_data.get('sixty_day_change_percent')
                        })
                        affected += 1
                        affected_stocks.add(stock_code)

                    if len(insert_dicts) >= 200:
                        session.execute(upsert_stmt, insert_dicts)
                        session.commit()
                        insert_dicts = []

                except Exception as e:
                    self.logger.error(f"处理股票 {stock_code} 出错: {e}")
                    continue

            if insert_dicts:
                session.execute(upsert_stmt, insert_dicts)
                session.commit()

            loop_time = time.time() - loop_start
            self.logger.info(f"主循环同步耗时: {loop_time:.2f}s, 共处理 {affected} 条记录")
            
            # 计算指标
            indicators_start = time.time()
            if calculate_indicators and affected_stocks:
                watchlist_codes = self._get_watchlist_codes(session)
                target_stocks = [s for s in affected_stocks if s in watchlist_codes]
                
                if target_stocks:
                    self.logger.info(f"开始为 {len(target_stocks)} 只自选股计算指标...")
                    funcs = [
                        self._calculate_and_save_macd_hk, self._calculate_and_save_kdj_hk,
                        self._calculate_and_save_rsi_hk, self._calculate_and_save_ma_hk,
                        self._calculate_and_save_boll_hk, self._calculate_and_save_mavol_hk,
                        self._calculate_and_save_mean_frequency_hk
                    ]
                    for func in funcs:
                        try:
                            item_start = time.time()
                            func(target_stocks, target_date, session)
                            self.logger.debug(f"{func.__name__} 耗时: {time.time() - item_start:.2f}s")
                        except Exception as e:
                            self.logger.warning(f"{func.__name__} 失败: {e}")
                    
                    self.logger.info(f"指标计算总耗时: {time.time() - indicators_start:.2f}s")

            # 操作日志记录
            try:
                session.execute(text("""
                    INSERT INTO historical_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, collect_source, created_at)
                    VALUES (:type, :desc, :rows, :status, :source, CURRENT_TIMESTAMP)
                """), {
                    "type": "sync_from_realtime", "desc": f"同步{target_date}实时行情至历史行情",
                    "rows": affected, "status": "SUCCESS", "source": "akshare"
                })
                session.commit()
            except Exception as log_e:
                self.logger.error(f"操作日志写入失败: {log_e}")
                session.rollback()

            return True
        except Exception as e:
            self.logger.error(f"港股历史行情同步异常: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _calculate_and_save_macd_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股MACD指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            calculator = MACDCalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的收盘价数据（用于计算MACD）
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, close
                        FROM historical_quotes_hk 
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
                    if len(rows) < 26: # macd至少需要26天数据
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    
                    # 使用MACD计算器计算指标
                    macd_results = calculator.calculate_macd_batch(closes)
                    
                    if not macd_results:
                        continue
                    
                    # 保存指标到数据库
                    for i, macd_data in enumerate(macd_results):
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                            
                        try:
                            if macd_data.get('dif') is None and macd_data.get('dea') is None and macd_data.get('macd') is None:
                                continue
                            session.execute(text("""
                                INSERT INTO macd_indicators
                                (code, date, market_type, dif, dea, macd, created_at)
                                VALUES (:code, :date, :market_type, :dif, :dea, :macd, :created_at)
                                ON CONFLICT (code, date, market_type) DO UPDATE SET
                                    dif = EXCLUDED.dif,
                                    dea = EXCLUDED.dea,
                                    macd = EXCLUDED.macd,
                                    created_at = EXCLUDED.created_at
                            """), {
                                'code': stock_code,
                                'date': date_str,
                                'market_type': 'HK',
                                'dif': macd_data.get('dif'),
                                'dea': macd_data.get('dea'),
                                'macd': macd_data.get('macd'),
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} MACD数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} MACD指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} MACD指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股MACD指标失败: {e}")
            session.rollback()

    def _calculate_and_save_kdj_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股KDJ指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            calculator = KDJCalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的最高、最低、收盘价数据（用于计算KDJ）
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, high, low, close
                        FROM historical_quotes_hk 
                        WHERE code = :stock_code 
                        AND date >= :query_start_date 
                        AND date <= :target_date
                        AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'query_start_date': query_start_date,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 9: # kdj至少需要9天数据
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    highs = [float(row[1]) for row in rows]
                    lows = [float(row[2]) for row in rows]
                    closes = [float(row[3]) for row in rows]
                    
                    # 使用KDJ计算器计算指标
                    kdj_results = calculator.calculate_kdj_batch(highs, lows, closes)
                    
                    if not kdj_results:
                        continue
                    
                    # 保存指标到数据库
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
                                'market_type': 'HK',
                                'k': kdj_data['k'],
                                'd': kdj_data['d'],
                                'j': kdj_data['j'],
                                'rsv': kdj_data['rsv'],
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} KDJ数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} KDJ指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} KDJ指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股KDJ指标失败: {e}")
            session.rollback()

    def _calculate_and_save_rsi_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股RSI指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            calculator = RSICalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的收盘价数据（用于计算RSI）
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, close
                        FROM historical_quotes_hk 
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
                    if len(rows) < 7: # rsi6至少需要7天数据
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    
                    # 使用RSI计算器批量计算
                    rsi_results = calculator.calculate_rsi_batch(closes)
                    
                    if not rsi_results:
                        continue
                    
                    # 保存RSI数据（只保存目标日期的数据）
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
                                'market_type': 'HK',
                                'rsi6': rsi_data.get('rsi6'),
                                'rsi12': rsi_data.get('rsi12'),
                                'rsi24': rsi_data.get('rsi24'),
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} RSI数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} RSI指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} RSI指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股RSI指标失败: {e}")
            session.rollback()

    def _calculate_and_save_ma_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股MA指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            for stock_code in stock_codes:
                try:
                    # 查询该股票所有历史收盘价数据（不限制日期范围，确保有足够数据计算MA200）
                    # 注意：MA200需要至少200个交易日，约300个日历天，但为了保险起见，查询所有历史数据
                    result = session.execute(text("""
                        SELECT date, close
                        FROM historical_quotes_hk 
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
                        continue
                    
                    # 构建DataFrame
                    df_data = []
                    dates = []
                    for row in rows:
                        dates.append(str(row[0]))
                        df_data.append({
                            'date': str(row[0]),
                            'close': float(row[1]) if row[1] else None
                        })
                    
                    df = pd.DataFrame(df_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
                    
                    if 'close' not in df.columns or len(df) == 0:
                        continue
                    
                    # 计算MA指标
                    ma_df = MACalculator.calculate_ma_for_dataframe(df, periods=[5, 10, 20, 30, 60, 120, 200])
                    
                    # 保存MA数据（只保存目标日期的数据）
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
                                'market_type': 'HK',
                                'ma5': self._safe_value(row.get('ma5')),
                                'ma10': self._safe_value(row.get('ma10')),
                                'ma20': self._safe_value(row.get('ma20')),
                                'ma30': self._safe_value(row.get('ma30')),
                                'ma60': self._safe_value(row.get('ma60')),
                                'ma120': self._safe_value(row.get('ma120')),
                                'ma200': self._safe_value(row.get('ma200')),
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} MA数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} MA指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} MA指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股MA指标失败: {e}")
            session.rollback()

    def _calculate_and_save_boll_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股BOLL指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            calculator = BOLLCalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的收盘价数据
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, close
                        FROM historical_quotes_hk 
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
                    if len(rows) < 20:
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    
                    # 使用BOLL计算器批量计算
                    boll_results = calculator.calculate_boll_batch(closes)
                    
                    if not boll_results:
                        continue
                    
                    # 保存BOLL数据（只保存目标日期的数据）
                    for i, boll_data in enumerate(boll_results):
                        if boll_data['mid'] is None:
                            continue
                            
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
                                INSERT INTO boll_indicators
                                (code, date, market_type, mid, upper, lower, created_at)
                                VALUES (:code, :date, :market_type, :mid, :upper, :lower, :created_at)
                                ON CONFLICT (code, date, market_type) DO UPDATE SET
                                    mid = EXCLUDED.mid,
                                    upper = EXCLUDED.upper,
                                    lower = EXCLUDED.lower,
                                    created_at = EXCLUDED.created_at
                            """), {
                                'code': stock_code,
                                'date': date_str,
                                'market_type': 'HK',
                                'mid': boll_data['mid'],
                                'upper': boll_data['upper'],
                                'lower': boll_data['lower'],
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} BOLL数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} BOLL指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} BOLL指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股BOLL指标失败: {e}")
            session.rollback()

    def _calculate_and_save_mavol_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股MAVOL指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            for stock_code in stock_codes:
                try:
                    # 查询该股票所有历史成交量数据（不限制日期范围，确保有足够数据计算MAVOL200）
                    # 注意：MAVOL200需要至少200个交易日，约300个日历天，但为了保险起见，查询所有历史数据
                    result = session.execute(text("""
                        SELECT date, volume
                        FROM historical_quotes_hk
                        WHERE code = :stock_code
                        AND date <= :target_date
                        AND volume IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 5:  # 至少需要5天数据才能计算MAVOL5
                        continue
                    
                    # 构建DataFrame
                    df_data = []
                    for row in rows:
                        df_data.append({
                            'date': str(row[0]),
                            'volume': float(row[1]) if row[1] else None
                        })
                    
                    df = pd.DataFrame(df_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
                    
                    if 'volume' not in df.columns or len(df) == 0:
                        continue
                    
                    # 计算MAVOL指标
                    mavol_df = MAVOLCalculator.calculate_mavol_for_dataframe(df, periods=[5, 10, 20, 30, 60, 120, 200])
                    
                    # 保存MAVOL数据（只保存目标日期的数据）
                    for _, row in mavol_df.iterrows():
                        date_str = row['date'].strftime('%Y-%m-%d') if isinstance(row['date'], pd.Timestamp) else str(row['date'])
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
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
                                'market_type': 'HK',
                                'mavol5': self._safe_value(row.get('mavol5')),
                                'mavol10': self._safe_value(row.get('mavol10')),
                                'mavol20': self._safe_value(row.get('mavol20')),
                                'mavol30': self._safe_value(row.get('mavol30')),
                                'mavol60': self._safe_value(row.get('mavol60')),
                                'mavol120': self._safe_value(row.get('mavol120')),
                                'mavol200': self._safe_value(row.get('mavol200')),
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} MAVOL数据失败: {e}")
                            continue
                    
                    session.commit()
                    self.logger.debug(f"股票 {stock_code} MAVOL指标计算完成")
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} MAVOL指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股MAVOL指标失败: {e}")
            session.rollback()

    def _calculate_and_save_mean_frequency_hk(self, stock_codes: list, target_date: str, session):
        """
        计算并保存港股均值频率共振指标
        
        Args:
            stock_codes: 股票代码列表
            target_date: 目标日期 (YYYY-MM-DD)
            session: 数据库会话
        """
        try:
            calculator = MeanFrequencyResonanceCalculator()
            
            for stock_code in stock_codes:
                try:
                    # 查询该股票最近至少30天的收盘价和成交量数据
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, close, volume
                        FROM historical_quotes_hk 
                        WHERE code = :stock_code 
                        AND date >= :query_start_date 
                        AND date <= :target_date
                        AND close IS NOT NULL
                        AND volume IS NOT NULL
                        ORDER BY date ASC
                    """), {
                        'stock_code': stock_code,
                        'query_start_date': query_start_date,
                        'target_date': target_date
                    })
                    
                    rows = result.fetchall()
                    if len(rows) < 21:
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    volumes = [float(row[2]) for row in rows]
                    
                    # 计算（传入 dates 以输出 d1_date、d20_date）
                    results = calculator.calculate(closes, volumes, dates=dates)
                    
                    if not results:
                        continue
                    
                    # 保存数据（只保存目标日期的数据）
                    for i, res in enumerate(results):
                        if res is None:
                            continue
                            
                        date_str = dates[i]
                        
                        # 只保存目标日期的数据
                        if date_str != target_date:
                            continue
                        
                        try:
                            session.execute(text("""
                                INSERT INTO mean_frequency_resonance_indicators
                                (code, date, market_type, macro_displacement_delta, amplitude, ratio_d20, ratio_d1, instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m, ma20_d, mavol20_m, bias, created_at)
                                VALUES (:code, :date, :market_type, :delta, :amplitude, :ratio_d20, :ratio_d1, :instant_deviation, :z, :f, :efficiency, :ma20, :mavol20, :bias, :created_at)
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
                                    bias = EXCLUDED.bias,
                                    created_at = EXCLUDED.created_at
                            """), {
                                'code': stock_code,
                                'date': date_str,
                                'market_type': 'HK',
                                'delta': res['macro_displacement_delta'],
                                'amplitude': res.get('amplitude'),
                                'ratio_d20': res.get('ratio_d20'),
                                'ratio_d1': res.get('ratio_d1'),
                                'instant_deviation': res['instant_deviation'],
                                'z': res['rising_days_z'],
                                'f': res['falling_days_f'],
                                'efficiency': res['efficiency_m20_minus_m'],
                                'ma20': res['ma20_d'],
                                'mavol20': res['mavol20_m'],
                                'bias': res['bias'],
                                'created_at': datetime.now()
                            })
                        except Exception as e:
                            self.logger.error(f"保存股票 {stock_code} 日期 {date_str} 均值频率共振数据失败: {e}")
                            continue
                            
                    session.commit()
                    
                except Exception as e:
                    self.logger.error(f"计算股票 {stock_code} 均值频率共振指标失败: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            self.logger.error(f"批量计算港股均值频率共振指标失败: {e}")
