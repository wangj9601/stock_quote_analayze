"""
港股历史行情数据采集器
负责采集港股历史行情数据并存储到数据库
"""

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
    
    def collect_historical_quotes(self, date_str: str) -> bool:
        """
        采集指定日期的港股历史行情数据（从实时行情表读取并同步到历史行情表）
        
        Args:
            date_str: 日期字符串，格式：YYYYMMDD
        
        Returns:
            bool: 是否成功
        """
        self._init_db()  # 确保表结构存在
        session = SessionLocal()
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
            
            affected = 0
            # 对每只股票进行处理
            affected_stocks = set()  # 记录已处理的股票代码，用于后续MACD计算
            for stock_code, records in stocks_data.items():
                try:
                    # 获取该股票在历史行情表中的已有数据（用于计算涨跌幅）
                    historical_result = session.execute(text("""
                        SELECT date, close 
                        FROM historical_quotes_hk 
                        WHERE code = :code 
                        ORDER BY date ASC
                    """), {"code": stock_code})
                    historical_data = historical_result.fetchall()
                    
                    # 构建DataFrame用于计算涨跌幅
                    historical_df_data = []
                    for hist_row in historical_data:
                        historical_df_data.append({
                            'date': hist_row[0],
                            'close': hist_row[1]
                        })
                    
                    # 添加当前要插入的数据
                    for record in records:
                        close_price = record.get('current_price')
                        if close_price:
                            historical_df_data.append({
                                'date': record.get('trade_date'),
                                'close': float(close_price) if close_price else None
                            })
                    
                    # 如果有数据，计算涨跌幅
                    change_percents = {}
                    if historical_df_data:
                        df = pd.DataFrame(historical_df_data)
                        df = df.sort_values('date')
                        df = df.drop_duplicates(subset=['date'], keep='last')  # 去重，保留最新的
                        
                        if 'close' in df.columns and len(df) > 0:
                            # 计算涨跌幅（与A股逻辑相同）
                            # 使用 fill_method=None 避免 FutureWarning
                            df['five_day_change_percent'] = df['close'].pct_change(periods=5, fill_method=None) * 100
                            df['ten_day_change_percent'] = df['close'].pct_change(periods=10, fill_method=None) * 100
                            df['thirty_day_change_percent'] = df['close'].pct_change(periods=30, fill_method=None) * 100
                            df['sixty_day_change_percent'] = df['close'].pct_change(periods=60, fill_method=None) * 100
                            
                            # 将计算结果存储到字典中
                            for _, row in df.iterrows():
                                change_percents[row['date']] = {
                                    'five_day_change_percent': self._safe_value(row.get('five_day_change_percent')),
                                    'ten_day_change_percent': self._safe_value(row.get('ten_day_change_percent')),
                                    'thirty_day_change_percent': self._safe_value(row.get('thirty_day_change_percent')),
                                    'sixty_day_change_percent': self._safe_value(row.get('sixty_day_change_percent'))
                                }
                    
                    # 处理每条记录
                    for record in records:
                        # 如果现价、开盘、最高、最低中有为空的，跳过不采集
                        if not record.get('current_price') or not record.get('open') or \
                           not record.get('high') or not record.get('low'):
                            continue

                        trade_date = record.get('trade_date')
                        change_data = change_percents.get(trade_date, {})
                        
                        # 构造要插入/更新的字段
                        insert_dict = {
                            # 字段映射：如有不同需调整
                            'code': record.get('code'),
                            'name': record.get('name'),
                            'date': trade_date,  # 记得历史行情表日期字段为date
                            'english_name': record.get('english_name'),
                            'close': record.get('current_price'), # 实时行情表中，最后的当前价格，就相当于收盘价
                            'open': record.get('open'),
                            'high': record.get('high'),
                            'low': record.get('low'),
                            'pre_close': record.get('pre_close'),
                            'volume': record.get('volume'),
                            'amount': record.get('amount'),
                            #'amplitude': record.get('amplitude'),
                            #'turnover_rate': record.get('turnover_rate'),
                            'change_percent': record.get('change_percent'),
                            'change_amount': record.get('change_amount'),  # 可能字段名有差异
                            'collected_source': "akshare",
                            'collected_date': collect_date,
                            # 用当前时间替换有语法错误的行，赋值方式如下：
                            'create_date': datetime.now(),
                            # 使用计算出的涨跌幅
                            'five_day_change_percent': change_data.get('five_day_change_percent'),
                            'ten_day_change_percent': change_data.get('ten_day_change_percent'),
                            'thirty_day_change_percent': change_data.get('thirty_day_change_percent'),
                            'sixty_day_change_percent': change_data.get('sixty_day_change_percent')
                        }
                        
                        # upsert逻辑：如果已有则更新，否则插入
                        try:
                            # 先尝试更新
                            update_stmt = text("""
                                UPDATE historical_quotes_hk SET
                                    name = :name,
                                    english_name = :english_name,
                                    close = :close,
                                    open = :open,
                                    high = :high,
                                    low = :low,
                                    pre_close = :pre_close,
                                    volume = :volume,
                                    amount = :amount,
                                    change_percent = :change_percent,
                                    change_amount = :change_amount,
                                    five_day_change_percent = :five_day_change_percent,
                                    ten_day_change_percent = :ten_day_change_percent,
                                    sixty_day_change_percent = :sixty_day_change_percent,
                                    thirty_day_change_percent = :thirty_day_change_percent,
                                    collected_source = :collected_source,
                                    collected_date = :collected_date,
                                    create_date = :create_date
                                WHERE code = :code AND date = :date 
                            """)
                            result_update = session.execute(update_stmt, insert_dict)
                            if result_update.rowcount == 0:
                                # 没有更新任何行，执行插入
                                insert_stmt = text("""
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
                                """)
                                session.execute(insert_stmt, insert_dict)
                            affected += 1
                        except Exception as e:
                            self.logger.error(f"港股历史({insert_dict['code']}-{insert_dict['date']})同步失败: {e}")
                            session.rollback()
                            continue
                        
                except Exception as stock_error:
                    self.logger.error(f"处理股票 {stock_code} 的涨跌幅计算失败: {stock_error}")
                    # 即使计算失败，也尝试插入数据（不包含涨跌幅）
                    for record in records:
                        # 如果现价、开盘、最高、最低中有为空的，跳过不采集
                        if not record.get('current_price') or not record.get('open') or \
                           not record.get('high') or not record.get('low'):
                            continue

                        try:
                            insert_dict = {
                                'code': record.get('code'),
                                'name': record.get('name'),
                                'date': record.get('trade_date'),
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
                                'five_day_change_percent': None,
                                'ten_day_change_percent': None,
                                'thirty_day_change_percent': None,
                                'sixty_day_change_percent': None
                            }
                            
                            update_stmt = text("""
                                UPDATE historical_quotes_hk SET
                                    name = :name,
                                    english_name = :english_name,
                                    close = :close,
                                    open = :open,
                                    high = :high,
                                    low = :low,
                                    pre_close = :pre_close,
                                    volume = :volume,
                                    amount = :amount,
                                    change_percent = :change_percent,
                                    change_amount = :change_amount,
                                    five_day_change_percent = :five_day_change_percent,
                                    ten_day_change_percent = :ten_day_change_percent,
                                    sixty_day_change_percent = :sixty_day_change_percent,
                                    thirty_day_change_percent = :thirty_day_change_percent,
                                    collected_source = :collected_source,
                                    collected_date = :collected_date,
                                    create_date = :create_date
                                WHERE code = :code AND date = :date 
                            """)
                            result_update = session.execute(update_stmt, insert_dict)
                            if result_update.rowcount == 0:
                                insert_stmt = text("""
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
                                """)
                                session.execute(insert_stmt, insert_dict)
                            affected += 1
                            affected_stocks.add(stock_code)  # 记录已处理的股票
                        except Exception as e:
                            self.logger.error(f"港股历史({insert_dict['code']}-{insert_dict['date']})同步失败: {e}")
                            session.rollback()
                            continue

            session.commit()
            self.logger.info(f"{target_date} 共有 {affected} 条港股实时数据同步到了历史行情表")
            
            # 计算并保存MACD指标（对已处理的股票）
            if affected_stocks:
                try:
                    self._calculate_and_save_macd_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股MACD指标计算失败: {e}")
            
                try:
                    self._calculate_and_save_kdj_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股KDJ指标计算失败: {e}")

                try:
                    self._calculate_and_save_rsi_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股RSI指标计算失败: {e}")

                try:
                    self._calculate_and_save_ma_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股MA指标计算失败: {e}")

                try:
                    self._calculate_and_save_boll_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股BOLL指标计算失败: {e}")
                
                try:
                    self._calculate_and_save_mavol_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股MAVOL指标计算失败: {e}")
                
                try:
                    self._calculate_and_save_mean_frequency_hk(list(affected_stocks), target_date, session)
                except Exception as e:
                    self.logger.warning(f"港股均值频率共振指标计算失败: {e}")
            
            # 操作日志记录
            try:
                op_log_stmt = text("""
                    INSERT INTO historical_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, collect_source, created_at)
                    VALUES
                        (:operation_type, :operation_desc, :affected_rows, :status, :collect_source, CURRENT_TIMESTAMP)
                """)
                session.execute(op_log_stmt, {
                    "operation_type": "sync_from_realtime",
                    "operation_desc": f"同步{target_date}实时行情至历史行情",
                    "affected_rows": affected,
                    "status": "SUCCESS",
                    "collect_source": "akshare"
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
                    # 查询该股票最近至少26天的收盘价数据
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
                    if len(rows) < 26:
                        continue
                    
                    # 提取收盘价列表
                    closes = [float(row[1]) for row in rows]
                    dates = [str(row[0]) for row in rows]  # 港股date是String类型
                    
                    # 使用MACD计算器批量计算
                    macd_results = calculator.calculate_macd_batch(closes)
                    
                    if not macd_results:
                        continue
                    
                    # 保存MACD数据（只保存目标日期的数据）
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
                                'market_type': 'HK',
                                'dif': macd_data['dif'],
                                'dea': macd_data['dea'],
                                'macd': macd_data['macd'],
                                'ema12': macd_data['ema12'],
                                'ema26': macd_data['ema26'],
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
                    # 查询该股票最近至少20天的收盘价数据
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
                    
                    result = session.execute(text("""
                        SELECT date, close, high, low
                        FROM historical_quotes_hk 
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
                    if len(rows) < 9:
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    highs = [float(row[2]) for row in rows]
                    lows = [float(row[3]) for row in rows]
                    
                    # 使用KDJ计算器批量计算
                    kdj_results = calculator.calculate_kdj_batch(closes, highs, lows)
                    
                    if not kdj_results:
                        continue
                    
                    # 保存KDJ数据（只保存目标日期的数据）
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
                    # 查询该股票最近至少200天的收盘价数据（用于计算MA200）
                    query_start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=250)).strftime('%Y-%m-%d')
                    
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
                    if len(rows) < 20:
                        continue
                    
                    # 提取数据列表
                    dates = [str(row[0]) for row in rows]
                    closes = [float(row[1]) for row in rows]
                    volumes = [float(row[2]) for row in rows]
                    
                    # 计算
                    results = calculator.calculate(closes, volumes)
                    
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
                                (code, date, market_type, macro_displacement_delta, instant_deviation, rising_days_z, falling_days_f, efficiency_m20_minus_m, ma20_d, mavol20_m, bias, created_at)
                                VALUES (:code, :date, :market_type, :delta, :instant_deviation, :z, :f, :efficiency, :ma20, :mavol20, :bias, :created_at)
                                ON CONFLICT (code, date, market_type) DO UPDATE SET
                                    macro_displacement_delta = EXCLUDED.macro_displacement_delta,
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

