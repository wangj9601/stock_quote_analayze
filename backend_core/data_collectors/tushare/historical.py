import tushare as ts
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from .base import TushareCollector
import datetime
from backend_core.database.db import SessionLocal
from sqlalchemy import text

class HistoricalQuoteCollector(TushareCollector):
    
    """历史行情数据采集器"""
    # def __init__(self, config: Optional[Dict[str, Any]] = None):
    #     super().__init__(config)
    #     #self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
    
    def _init_db(self):
        session = SessionLocal()
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                total_share REAL
            )
        '''))
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS historical_quotes (
                code TEXT,
                ts_code TEXT,
                name TEXT,
                market TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                volume REAL,
                amount REAL,    
                amplitude REAL,
                turnover_rate REAL,
                change_percent REAL,
                change REAL,
                collected_source TEXT,
                collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date)
            )
        '''))
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS historical_collect_operation_logs (
                id SERIAL PRIMARY KEY,
                operation_type TEXT NOT NULL,
                operation_desc TEXT NOT NULL,
                affected_rows INTEGER,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        session.commit()
        session.close()

    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    def extract_code_from_ts_code(self, ts_code: str) -> str:
        return ts_code.split(".")[0] if ts_code else ""
    
    def collect_historical_quotes(self, date_str: str) -> bool:
        self._init_db()  # 初始化表结构
        session = SessionLocal()  # 新建 session
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
            try:
                for _, row in df.iterrows():
                    pass  # 这里的 pass 只是占位，实际循环体在后面
            except Exception as e:
                self.logger.error(f"遍历历史行情数据时发生异常: {e}")
                import sys
                sys.exit(1)
            for _, row in df.iterrows():
                try:
                    code = self.extract_code_from_ts_code(row['ts_code'])
                    ts_code = row['ts_code']
                    # 从 stock_basic_info 表读取 name
                    result = session.execute(
                        text('SELECT name FROM stock_basic_info WHERE code = :code'),
                        {'code': code}
                    ).fetchone()
                    name = result[0] if result and result[0] else ''
                    market = row.get('market', '')
                    # 计算换手率和振幅
                    # 换手率 = 成交量 / 总股本 * 100
                    # 振幅 = (最高价 - 最低价) / 昨收盘价 * 100
                    # 注意：需要从 stock_basic_info 表获取总股本（total_share），如果没有则为 None
                    total_share = None
                    try:
                        result_share = session.execute(
                            text('SELECT total_share FROM stock_basic_info WHERE code = :code'),
                            {'code': code}
                        ).fetchone()
                        if result_share and result_share[0]:
                            total_share = float(result_share[0])
                    except Exception as e:
                        self.logger.warning(f"获取总股本失败: {e}")
                        total_share = None

                    volume = self._safe_value(row['vol'])
                    pre_close = self._safe_value(row['pre_close'])
                    high = self._safe_value(row['high'])
                    low = self._safe_value(row['low'])

                    turnover_rate = None
                    if total_share and volume is not None and total_share > 0:
                        turnover_rate = volume / total_share * 100

                    amplitude = None
                    if pre_close and pre_close > 0 and high is not None and low is not None:
                        amplitude = (high - low) / pre_close * 100
                    # 打印前面取得的参数
                    self.logger.info(f"参数: code={code}, ts_code={ts_code}, name={name}, market={market}, total_share={total_share}, volume={volume}, pre_close={pre_close}, high={high}, low={low}, turnover_rate={turnover_rate}, amplitude={amplitude}")

                    data = {
                        'code': code,
                        'ts_code': ts_code,
                        'name': name,
                        'market': market,
                        'date': datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                        'collected_source': 'tushare',
                        'collected_date': datetime.datetime.now().isoformat(),
                        'open': self._safe_value(row['open']),
                        'high': high,
                        'low': low,
                        'close': self._safe_value(row['close']),
                        'volume': volume,
                        # tushare返回的amount单位是千元，需折算为元
                        'amount': self._safe_value(row['amount']) * 1000 if self._safe_value(row['amount']) is not None else None,
                        'change_percent': self._safe_value(row['pct_chg']),
                        'pre_close': pre_close,
                        'change': self._safe_value(row['change']),
                        'turnover_rate': turnover_rate,
                        'amplitude': amplitude
                    }
                    
                    # 使用重试机制处理死锁
                    max_retries = 3
                    retry_count = 0
                    
                    while retry_count < max_retries:
                        try:
                            # 先尝试插入 stock_basic_info（如果不存在）
                            session.execute(text('''
                                INSERT INTO stock_basic_info (code, name)
                                VALUES (:code, :name)
                                ON CONFLICT (code) DO NOTHING
                            '''), {'code': data['code'], 'name': data['name']})
                            
                            # 然后插入 historical_quotes
                            session.execute(text('''
                                INSERT INTO historical_quotes
                                (code, ts_code, name, market, collected_source, collected_date, date, open, high, low, close, volume, amount, change_percent, pre_close, change, amplitude, turnover_rate)
                                VALUES (:code, :ts_code, :name, :market, :collected_source, :collected_date, :date, :open, :high, :low, :close, :volume, :amount, :change_percent, :pre_close, :change, :amplitude, :turnover_rate)
                                ON CONFLICT (code, date) DO UPDATE SET
                                    ts_code = EXCLUDED.ts_code,
                                    name = EXCLUDED.name,
                                    market = EXCLUDED.market,
                                    collected_source = EXCLUDED.collected_source,
                                    collected_date = EXCLUDED.collected_date,
                                    open = EXCLUDED.open,
                                    high = EXCLUDED.high,
                                    low = EXCLUDED.low,
                                    close = EXCLUDED.close,
                                    volume = EXCLUDED.volume,
                                    amount = EXCLUDED.amount,
                                    change_percent = EXCLUDED.change_percent,
                                    pre_close = EXCLUDED.pre_close,
                                    amplitude = EXCLUDED.amplitude,
                                    turnover_rate = EXCLUDED.turnover_rate,
                                    change = EXCLUDED.change
                            '''), data)
                            
                            # 每100条记录提交一次，减少事务数量
                            if success_count % 100 == 0:
                                session.commit()
                                self.logger.info(f"已处理 {success_count} 条记录，提交事务")
                            
                            success_count += 1
                            break  # 成功插入，跳出重试循环
                            
                        except Exception as insert_error:
                            # 如果是死锁错误，回滚并重试
                            if "DeadlockDetected" in str(insert_error):
                                retry_count += 1
                                self.logger.warning(f"检测到死锁，第 {retry_count} 次重试: {insert_error}")
                                session.rollback()
                                # 短暂等待后重试
                                import time
                                time.sleep(0.1 * retry_count)  # 递增等待时间
                                continue
                            else:
                                # 其他错误，直接抛出
                                raise insert_error
                    
                    # 如果重试次数用完仍然失败
                    if retry_count >= max_retries:
                        fail_count += 1
                        fail_detail.append(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                        self.logger.error(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                        continue
                        
                except Exception as row_e:
                    fail_count += 1
                    fail_detail.append(str(row_e))
                    self.logger.error(f"采集单条数据失败: {row_e}")
                    # 移除 sys.exit(1)，避免程序退出
                    continue
            # 记录采集日志（汇总信息）
            session.execute(text('''
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message)
            '''), {
                'operation_type': 'historical_quote_collect',
                'operation_desc': f'采集日期: {collect_date}\n输入参数: {input_params}\n成功记录数: {success_count}\n失败记录数: {fail_count}',
                'affected_rows': success_count,
                'status': 'success' if fail_count == 0 else 'partial_success',
                'error_message': '\n'.join(fail_detail) if fail_count > 0 else None
            })
            session.commit()
            self.logger.info(f"全部历史行情数据采集并入库完成，成功: {success_count}，失败: {fail_count}")
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            try:
                session.execute(text('''
                    INSERT INTO historical_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message)
                '''), {
                    'operation_type': 'historical_quote_collect',
                    'operation_desc': f'采集日期: {datetime.date.today().isoformat()}\n输入参数: {input_params if "input_params" in locals() else ""}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': error_msg
                })
                session.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            return False
        finally:
            session.close()
