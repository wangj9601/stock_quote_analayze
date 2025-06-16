"""
历史行情数据采集器
负责采集股票历史行情数据并存储到数据库
"""

import akshare as ak
import pandas as pd
import sqlite3
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import logging
from datetime import datetime
import time
import signal
from requests.exceptions import RequestException

# 直接导入base模块
from .base import AKShareCollector

class HistoricalQuoteCollector(AKShareCollector):
    """历史行情数据采集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
        self.should_stop = False
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info("接收到中断信号，正在安全退出...")
        self.should_stop = True
        
    def _init_db(self) -> sqlite3.Connection:
        """
        初始化数据库表结构
        
        Returns:
            sqlite3.Connection: 数据库连接
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_quotes (
                code TEXT,
                name TEXT,
                market TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                change_percent REAL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date)
            )
        ''')
        
        conn.commit()
        return conn
    
    def _safe_value(self, val: Any) -> Optional[float]:
        """
        安全地转换数值
        
        Args:
            val: 输入值
            
        Returns:
            Optional[float]: 转换后的浮点数，如果转换失败则返回None
        """
        if pd.isna(val):
            return None
            
        if isinstance(val, str):
            import re
            val = val.strip().replace('"', '').replace("'", '').replace(" ", '')
            val = re.sub(r'[^\d\.\-]', '', val)
            
        try:
            return float(val)
        except Exception:
            return None
    
    def _fetch_stock_data(self, code: str, date_str: str) -> pd.DataFrame:
        """
        获取单个股票的历史数据
        
        Args:
            code: 股票代码
            date_str: 日期字符串，格式：YYYYMMDD
            
        Returns:
            pd.DataFrame: 历史行情数据
        """
        return self._retry_on_failure(
            ak.stock_zh_a_hist,
            symbol=code,
            period="daily",
            start_date=date_str,
            end_date=date_str,
            adjust="qfq"
        )
    
    def collect_quotes(self, date_str: str) -> Tuple[int, int]:
        """
        采集指定日期的历史行情数据
        
        Args:
            date_str: 日期字符串，格式：YYYYMMDD
            
        Returns:
            Tuple[int, int]: (成功数量, 失败数量)
        """
        try:
            # 验证日期格式
            try:
                datetime.strptime(date_str, '%Y%m%d').date()
            except ValueError:
                self.logger.error("日期格式错误，请使用YYYYMMDD格式")
                return 0, 0
                
            # 获取股票列表
            stock_list = self._retry_on_failure(ak.stock_zh_a_spot_em)
            total_stocks = len(stock_list)
            
            success_count = 0
            error_count = 0
            connection_error_count = 0
            max_connection_errors = self.config.get('max_connection_errors', 10)
            
            self.logger.info(f"开始采集 {date_str} 的历史行情数据，共 {total_stocks} 只股票")
            
            # 连接数据库
            conn = self._init_db()
            cursor = conn.cursor()
            
            # 遍历股票列表
            for _, row in stock_list.iterrows():
                if self.should_stop:
                    self.logger.info("检测到中断信号，正在安全退出...")
                    break
                    
                try:
                    code = row['代码']
                    name = row['名称']
                    market = 'A股'
                    
                    # 获取历史数据
                    try:
                        df = self._fetch_stock_data(code, date_str)
                    except RequestException as e:
                        connection_error_count += 1
                        self.logger.error(f"网络连接错误 ({connection_error_count}/{max_connection_errors}): {str(e)}")
                        if connection_error_count >= max_connection_errors:
                            self.logger.error("连接错误次数过多，程序退出")
                            conn.close()
                            return success_count, error_count
                        time.sleep(5)
                        continue
                    except Exception as e:
                        self.logger.error(f"获取股票 {code} 数据时出错: {str(e)}")
                        error_count += 1
                        continue
                        
                    if df.empty:
                        self.logger.warning(f"股票 {code} 在 {date_str} 没有交易数据")
                        continue
                        
                    # 处理数据
                    daily_data = df.iloc[0]
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO historical_quotes
                            (code, name, market, date, open, high, low, close,
                             volume, amount, change_percent)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            code, name, market, date_str,
                            self._safe_value(daily_data['开盘']),
                            self._safe_value(daily_data['最高']),
                            self._safe_value(daily_data['最低']),
                            self._safe_value(daily_data['收盘']),
                            self._safe_value(daily_data['成交量']),
                            self._safe_value(daily_data['成交额']),
                            self._safe_value(daily_data['涨跌幅'])
                        ))
                        conn.commit()
                        success_count += 1
                        connection_error_count = 0
                        
                        if success_count % 100 == 0:
                            self.logger.info(f"已处理 {success_count}/{total_stocks} 只股票")
                            
                    except Exception as e:
                        error_count += 1
                        self.logger.error(f"保存股票 {code} 数据时出错: {str(e)}")
                        continue
                        
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"处理股票 {code} 时出错: {str(e)}")
                    continue
                    
            conn.close()
            self.logger.info(f"历史行情数据采集完成。成功: {success_count}, 失败: {error_count}")
            
            if self.should_stop:
                self.logger.info("程序被用户中断")
                
            return success_count, error_count
            
        except Exception as e:
            self.logger.error(f"采集历史行情数据时出错: {str(e)}", exc_info=True)
            return 0, 0 