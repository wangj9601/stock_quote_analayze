import tushare as ts
import pandas as pd
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from .base import TushareCollector
import datetime

class HistoricalQuoteCollector(TushareCollector):
    """历史行情数据采集器"""
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
                PRIMARY KEY (code, date)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_collect_operation_logs (
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
    def collect_historical_quotes(self, date_str: str) -> bool:
        conn = None
        cursor = None
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
            conn = self._init_db()
            cursor = conn.cursor()
            for _, row in df.iterrows():
                try:
                    code = row['ts_code']
                    name = row.get('name', '')
                    market = row.get('market', '')
                    data = {
                        'code': code,
                        'name': name,
                        'market': market,
                        'date': date_str,
                        'open': self._safe_value(row['open']),
                        'high': self._safe_value(row['high']),
                        'low': self._safe_value(row['low']),
                        'close': self._safe_value(row['close']),
                        'volume': self._safe_value(row['vol']),
                        'amount': self._safe_value(row['amount']),
                        'change_percent': self._safe_value(row['pct_chg'])
                    }
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_basic_info (code, name)
                        VALUES (?, ?)
                    ''', (data['code'], data['name']))
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_quotes
                        (code, name, market, date, open, high, low, close, volume, amount, change_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['code'], data['name'], data['market'], data['date'],
                        data['open'], data['high'], data['low'], data['close'],
                        data['volume'], data['amount'], data['change_percent']
                    ))
                    success_count += 1
                except Exception as row_e:
                    fail_count += 1
                    fail_detail.append(str(row_e))
                    self.logger.error(f"采集单条数据失败: {row_e}")
            # 记录采集日志（汇总信息）
            cursor.execute('''
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                'historical_quote_collect',
                f'采集日期: {collect_date}\n输入参数: {input_params}\n成功记录数: {success_count}\n失败记录数: {fail_count}',
                success_count,
                'success' if fail_count == 0 else 'partial_success',
                '\n'.join(fail_detail) if fail_count > 0 else None
            ))
            conn.commit()
            conn.close()
            self.logger.info(f"全部历史行情数据采集并入库完成，成功: {success_count}，失败: {fail_count}")
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            try:
                if cursor is not None:
                    cursor.execute('''
                        INSERT INTO historical_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        'historical_quote_collect',
                        f'采集日期: {datetime.date.today().isoformat()}\n输入参数: {input_params if "input_params" in locals() else ""}',
                        0,
                        'error',
                        error_msg
                    ))
                    conn.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            finally:
                if conn is not None:
                    conn.close()
            return False
