"""
实时行情数据采集器
负责采集股票实时行情数据并存储到数据库
"""

import akshare as ak
import pandas as pd
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

# 直接导入base模块
from base import AKShareCollector

class RealtimeQuoteCollector(AKShareCollector):
    """实时行情数据采集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
        
    def _init_db(self) -> sqlite3.Connection:
        """
        初始化数据库表结构
        
        Returns:
            sqlite3.Connection: 数据库连接
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 创建股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建实时行情表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_realtime_quote (
                code TEXT PRIMARY KEY,
                name TEXT,
                current_price REAL,
                change_percent REAL,
                volume REAL,
                amount REAL,
                high REAL,
                low REAL,
                open REAL,
                pre_close REAL,
                turnover_rate REAL,
                pe_dynamic REAL,
                total_market_value REAL,
                pb_ratio REAL,
                circulating_market_value REAL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(code) REFERENCES stock_basic_info(code)
            )
        ''')
        
        # 创建操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realtime_collect_operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                operation_desc TEXT NOT NULL,
                affected_rows INTEGER,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        return None if pd.isna(val) else float(val)
    
    def collect_quotes(self) -> bool:
        """
        采集实时行情数据
        
        Returns:
            bool: 是否成功
        """
        try:
            # 获取实时行情数据
            df = self._retry_on_failure(ak.stock_zh_a_spot_em)
            self.logger.info("采集到 %d 条股票行情数据", len(df))
            
            # 连接数据库
            conn = self._init_db()
            cursor = conn.cursor()
            
            # 批量处理数据
            affected_rows = 0
            for _, row in df.iterrows():
                code = row['代码']
                name = row['名称']
                #print(row)

                # 准备数据
                data = {
                    'code': code,
                    'name': name,
                    'current_price': self._safe_value(row['最新价']),
                    'change_percent': self._safe_value(row['涨跌幅']),
                    'volume': self._safe_value(row['成交量']),
                    'amount': self._safe_value(row['成交额']),
                    'high': self._safe_value(row['最高']),
                    'low': self._safe_value(row['最低']),
                    'open': self._safe_value(row['今开']),
                    'pre_close': self._safe_value(row['昨收']),
                    'turnover_rate': self._safe_value(row['换手率']),
                    'pe_dynamic': self._safe_value(row['市盈率-动态']),
                    'total_market_value': self._safe_value(row['总市值']),
                    'pb_ratio': self._safe_value(row['市净率']),
                    'circulating_market_value': self._safe_value(row['流通市值']),
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 更新基础信息
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_basic_info (code, name, create_date)
                    VALUES (?, ?, ?)
                ''', (data['code'], data['name'], data['update_time']))
                
                # 更新实时行情
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_realtime_quote
                    (code, name, current_price, change_percent, volume, amount,
                     high, low, open, pre_close, turnover_rate, pe_dynamic,
                     total_market_value, pb_ratio, circulating_market_value,
                     update_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['code'], data['name'], data['current_price'], data['change_percent'],
                    data['volume'], data['amount'], data['high'], data['low'],
                    data['open'], data['pre_close'], data['turnover_rate'],
                    data['pe_dynamic'], data['total_market_value'], data['pb_ratio'],
                    data['circulating_market_value'], data['update_time']
                ))
                affected_rows += 1
            
            # 记录操作日志
            cursor.execute('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                'realtime_quote_collect',
                f'采集并更新{len(df)}条股票实时行情数据',
                affected_rows,
                'success',
                None,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info("全部股票行情数据采集并入库完成")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            
            # 记录错误日志
            try:
                cursor.execute('''
                    INSERT INTO realtime_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'realtime_quote_collect',
                    '采集股票实时行情数据失败',
                    0,
                    'error',
                    error_msg
                ))
                conn.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            finally:
                if 'conn' in locals():
                    conn.close()
            
            return False 