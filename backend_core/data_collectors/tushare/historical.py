import tushare as ts
import pandas as pd
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from .base import TushareCollector

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
        conn.commit()
        return conn
    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    def collect_historical_quotes(self, date_str: str) -> bool:
        try:
            pro = ts.pro_api()
            df = pro.daily(trade_date=date_str)  # 
            self.logger.info("采集到 %d 条历史行情数据", len(df))
            conn = self._init_db()
            cursor = conn.cursor()
            for _, row in df.iterrows():
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
            conn.commit()
            conn.close()
            self.logger.info("全部历史行情数据采集并入库完成")
            return True
        except Exception as e:
            self.logger.error("采集或入库时出错: %s", str(e), exc_info=True)
            if 'conn' in locals():
                conn.close()
            return False
