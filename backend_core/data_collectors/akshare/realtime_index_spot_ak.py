import akshare as ak
import sqlite3
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
from backend_core.config.config import DATA_COLLECTORS

class RealtimeIndexSpotAkCollector:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DATA_COLLECTORS['akshare']['db_file']
        self.db_file = Path(db_path)
        self.logger = logging.getLogger('RealtimeIndexSpotAkCollector')
        # 确保数据库目录存在
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        # 指数实时行情表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_realtime_quotes (
                code TEXT,
                name TEXT,
                price REAL,
                change REAL,
                pct_chg REAL,
                open REAL,
                pre_close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                amplitude REAL,
                turnover REAL,
                pe REAL,
                volume_ratio REAL,
                update_time TEXT,
                collect_time TEXT,
                index_spot_type INT,
                PRIMARY KEY (code, update_time, index_spot_type)
            )
        ''')
        # 操作日志表
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
        return conn, cursor

    def collect_quotes(self):
        conn = None
        cursor = None
        try:
            conn, cursor = self._init_db()
            # 1: 沪深重要指数
            df1 = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            df1['index_spot_type'] = 1
            # 2: 上证系列指数
            df2 = ak.stock_zh_index_spot_em(symbol="上证系列指数")
            df2['index_spot_type'] = 2
            # 3: 深证系列指数
            df3 = ak.stock_zh_index_spot_em(symbol="深证系列指数")
            df3['index_spot_type'] = 3
            df = pd.concat([df1, df2, df3], ignore_index=True)
            # 去重
            df = df.drop_duplicates(subset=['代码'], keep='first')
            df['collect_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            affected_rows = 0
            # 清空表
            cursor.execute('DELETE FROM index_realtime_quotes')
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO index_realtime_quotes (
                        code, name, price, change, pct_chg, open, pre_close, high, low, volume, amount, amplitude, volume_ratio, update_time, collect_time, index_spot_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['代码'], row['名称'], row['最新价'], row['涨跌额'], row['涨跌幅'], row['今开'], row['昨收'],
                    row['最高'], row['最低'], row['成交量'], row['成交额'], row['振幅'], 
                    row['量比'], row['update_time'], row['collect_time'], row['index_spot_type']
                ))
                affected_rows += 1
            # 记录操作日志
            cursor.execute('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                'index_realtime_quote_collect',
                f'采集并更新{len(df)}条指数实时行情数据',
                affected_rows,
                'success',
                None,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
            conn.close()
            self.logger.info("全部指数实时行情数据采集并入库完成")
            return df
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            # 记录错误日志
            try:
                if 'cursor' in locals() and cursor is not None:
                    cursor.execute('''
                        INSERT INTO realtime_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        'index_realtime_quote_collect',
                        '采集指数实时行情数据失败',
                        0,
                        'error',
                        error_msg,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    conn.commit()
            except Exception as log_error:
                self.logger.error(f"记录错误日志失败: {log_error}")
            finally:
                if 'conn' in locals() and conn is not None:
                    conn.close()
            return None 