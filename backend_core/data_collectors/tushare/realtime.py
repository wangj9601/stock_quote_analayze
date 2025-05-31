import tushare as ts
import pandas as pd
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from .base import TushareCollector
import datetime

class RealtimeQuoteCollector(TushareCollector):
    """实时行情数据采集器"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_realtime_quote (
                code TEXT PRIMARY KEY,
                current_price REAL,
                change_percent REAL,
                volume REAL,
                amount REAL,
                high REAL,
                low REAL,
                open REAL,
                pre_close REAL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(code) REFERENCES stock_basic_info(code)
            )
        ''')
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
        return None if pd.isna(val) else float(val)
   
    def collect_quotes(self) -> bool:
        try:
            input_params = {}  # 可根据实际采集参数填写
            collect_date = datetime.date.today().isoformat()
            success_count = 0
            fail_count = 0
            fail_detail = []

            # 获取实时行情数据
            df = ts.pro_bar()  # 这里需要根据tushare实际API替换
            self.logger.info("采集到 %d 条股票行情数据", len(df))
            conn = self._init_db()
            cursor = conn.cursor()
            for _, row in df.iterrows():
                try:
                    code = row['ts_code']
                    name = row.get('name', '')
                    data = {
                        'code': code,
                        'name': name,
                        'current_price': self._safe_value(row['close']),
                        'change_percent': self._safe_value(row['pct_chg']),
                        'volume': self._safe_value(row['vol']),
                        'amount': self._safe_value(row['amount']),
                        'high': self._safe_value(row['high']),
                        'low': self._safe_value(row['low']),
                        'open': self._safe_value(row['open']),
                        'pre_close': self._safe_value(row['pre_close'])
                    }
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_basic_info (code, name)
                        VALUES (?, ?)
                    ''', (data['code'], data['name']))
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_realtime_quote
                        (code, current_price, change_percent, volume, amount,
                        high, low, open, pre_close)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['code'], data['current_price'], data['change_percent'],
                        data['volume'], data['amount'], data['high'], data['low'],
                        data['open'], data['pre_close']
                    ))
                    success_count += 1
                except Exception as row_e:
                    fail_count += 1
                    fail_detail.append(str(row_e))
                    self.logger.error(f"采集单条数据失败: {row_e}")

            # 记录采集日志（汇总信息）
            cursor.execute('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                'realtime_quote_collect',
                f'采集日期: {collect_date}\n输入参数: {input_params}\n成功记录数: {success_count}\n失败记录数: {fail_count}',
                success_count,
                'success' if fail_count == 0 else 'partial_success',
                '\n'.join(fail_detail) if fail_count > 0 else None
            ))
            conn.commit()
            conn.close()
            self.logger.info(f"采集完成，成功: {success_count}，失败: {fail_count}")
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            try:
                cursor.execute('''
                    INSERT INTO realtime_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'realtime_quote_collect',
                    f'采集日期: {datetime.date.today().isoformat()}\n输入参数: {input_params if "input_params" in locals() else ""}',
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
