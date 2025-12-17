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
                        except Exception as e:
                            self.logger.error(f"港股历史({insert_dict['code']}-{insert_dict['date']})同步失败: {e}")
                            session.rollback()
                            continue

            session.commit()
            self.logger.info(f"{target_date} 共有 {affected} 条港股实时数据同步到了历史行情表")
            
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
        

