import akshare as ak
import os
import sys
import logging
import pandas as pd
from datetime import datetime
import time
import requests
from requests.exceptions import RequestException
import signal
import sqlite3
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..config import DB_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

should_stop = False

def signal_handler(signum, frame):
    global should_stop
    logging.info("接收到中断信号，正在安全退出...")
    should_stop = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def safe_value(val):
    import decimal
    import re
    if pd.isna(val):
        return None
    if isinstance(val, str):
        val = val.strip().replace('"', '').replace("'", '').replace(" ", '')
        val = re.sub(r'[^\d\.\-]', '', val)
    try:
        return float(val)
    except Exception:
        return None

def retry_on_exception(func, max_retries=3, delay=1):
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except (RequestException, Exception) as e:
                retries += 1
                if retries == max_retries:
                    raise
                logging.warning(f"操作失败，正在进行第{retries}次重试: {str(e)}")
                time.sleep(delay * retries)
        return None
    return wrapper

@retry_on_exception
def fetch_stock_data(code, date_str):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                               start_date=date_str, end_date=date_str, 
                               adjust="qfq")
        return df
    except Exception as e:
        logging.error(f"获取股票{code}数据失败: {str(e)}")
        raise

def init_db(db_file):
    conn = sqlite3.connect(db_file)
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
            PRIMARY KEY (code, date)
        )
    ''')
    conn.commit()
    return conn

def collect_historical_quotes(date_str, db_file=DB_PATH):
    global should_stop
    should_stop = False
    try:
        try:
            date = datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            logging.error("日期格式错误，请使用YYYYMMDD格式")
            return 0, 0
        try:
            stock_list = ak.stock_zh_a_spot_em()
        except Exception as e:
            logging.error(f"获取股票列表失败: {str(e)}")
            return 0, 0
        total_stocks = len(stock_list)
        success_count = 0
        error_count = 0
        connection_error_count = 0
        max_connection_errors = 10
        logging.info(f"开始采集 {date_str} 的历史行情数据，共 {total_stocks} 只股票")
        conn = init_db(db_file)
        cursor = conn.cursor()
        for _, row in stock_list.iterrows():
            if should_stop:
                logging.info("检测到中断信号，正在安全退出...")
                break
            try:
                code = row['代码']
                name = row['名称']
                market = 'A股'
                try:
                    df = fetch_stock_data(code, date_str)
                except RequestException as e:
                    connection_error_count += 1
                    logging.error(f"网络连接错误 ({connection_error_count}/{max_connection_errors}): {str(e)}")
                    if connection_error_count >= max_connection_errors:
                        logging.error("连接错误次数过多，程序退出")
                        conn.close()
                        return success_count, error_count
                    time.sleep(5)
                    continue
                except Exception as e:
                    logging.error(f"获取股票 {code} 数据时出错: {str(e)}")
                    error_count += 1
                    continue
                if df.empty:
                    logging.warning(f"股票 {code} 在 {date_str} 没有交易数据")
                    continue
                daily_data = df.iloc[0]
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_quotes
                        (code, name, market, date, open, high, low, close, volume, amount, change_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        code, name, market, date_str,
                        safe_value(daily_data['开盘']),
                        safe_value(daily_data['最高']),
                        safe_value(daily_data['最低']),
                        safe_value(daily_data['收盘']),
                        safe_value(daily_data['成交量']),
                        safe_value(daily_data['成交额']),
                        safe_value(daily_data['涨跌幅'])
                    ))
                    conn.commit()
                    success_count += 1
                    connection_error_count = 0
                    if success_count % 100 == 0:
                        logging.info(f"已处理 {success_count}/{total_stocks} 只股票")
                except Exception as e:
                    error_count += 1
                    logging.error(f"保存股票 {code} 数据时出错: {str(e)}")
                    continue
            except Exception as e:
                error_count += 1
                logging.error(f"处理股票 {code} 时出错: {str(e)}")
                continue
        conn.close()
        logging.info(f"历史行情数据采集完成。成功: {success_count}, 失败: {error_count}")
        if should_stop:
            logging.info("程序被用户中断")
        return success_count, error_count
    except Exception as e:
        logging.error(f"采集历史行情数据时出错: {str(e)}", exc_info=True)
        return 0, 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python stock_info_his_quotes_akshare.py YYYYMMDD [db_file]")
        sys.exit(1)
    date_str = sys.argv[1]
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'historical_quotes.db'
    try:
        success_count, error_count = collect_historical_quotes(date_str, db_file=db_file)
        if success_count is not None:
            print(f"数据采集完成。成功: {success_count}, 失败: {error_count}")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        sys.exit(1)
