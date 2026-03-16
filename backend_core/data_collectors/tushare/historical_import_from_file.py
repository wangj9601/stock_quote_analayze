import tushare as ts
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
# 日志配置建议：如主入口未配置请加如下代码
# logging.basicConfig(filename='your_log_file.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
from .base import TushareCollector
import datetime
from backend_core.database.db import SessionLocal
from sqlalchemy import text
import re

class HistoricalQuoteImportFromFileCollector(TushareCollector):
    """历史行情数据采集器"""
    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    def extract_code_from_ts_code(self, ts_code: str) -> str:
        return ts_code.split(".")[0] if ts_code else ""
    
    def collect_historical_quotes(self, date_str: str, file_type: str) -> bool:
        session = SessionLocal()  # 新建 session
        try:
            input_params = {'date': date_str}
            collect_date = datetime.date.today().isoformat()
            success_count = 0
            fail_count = 0
            fail_detail = []
            # 从本地文件采集历史行情数据（重写：直接执行SQL插入MKT_STK_BASICINFO表，若表不存在则创建）
            # 1. 先确保表存在
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS MKT_STK_BASICINFO (
                ts_code VARCHAR(32),
                trade_date VARCHAR(16),
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                pre_close FLOAT,
                change FLOAT,
                pct_chg FLOAT,
                vol FLOAT,
                amount FLOAT,
                UNIQUE(ts_code, trade_date)
            );
            """
            try:
                session.execute(text(create_table_sql))
                # 再次尝试添加唯一约束，防止表已存在但无唯一约束
                try:
                    session.execute(text("ALTER TABLE MKT_STK_BASICINFO ADD CONSTRAINT uniq_ts_code_trade_date UNIQUE(ts_code, trade_date);"))
                except Exception as e:
                    if 'already exists' not in str(e):
                        self.logger.error(f"添加唯一约束失败: {e}")
                session.commit()
            except Exception as e:
                self.logger.error(f"创建表MKT_STK_BASICINFO失败: {e}")
                session.rollback()
                return False

            # 2. 读取文件并插入数据
            if file_type == 'txt':
                file_path = Path(f'backend_core/data/daily_{date_str}.txt')
                if not file_path.exists():
                    self.logger.error(f"历史行情数据文件不存在: {file_path}")
                    return False
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                insert_count = 0
                for line in lines:
                    sql_line = line.strip()
                    if not sql_line:
                        continue
                    try:
                        # 自动转换REPLACE INTO为PostgreSQL兼容语法
                        if sql_line.lower().startswith("replace into"):
                            import re
                            sql_line = sql_line.replace('`pct_change`', '`pct_chg`').replace('pct_change', 'pct_chg')
                            m = re.match(r"replace into\s+(\w+)\s*\(([^)]*)\)\s*values\s*\(([^)]*)\);?", sql_line, re.IGNORECASE)
                            if m:
                                table = m.group(1)
                                fields = m.group(2).replace('`', '')
                                values = m.group(3)
                                field_list = [f.strip() for f in fields.split(',')]
                                update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('ts_code', 'trade_date')])
                                sql_line = f"INSERT INTO {table} ({fields}) VALUES ({values}) ON CONFLICT (ts_code, trade_date) DO UPDATE SET {update_clause};"
                        if (("insert" in sql_line.lower() or "replace" in sql_line.lower())
                            and "mkt_stk_basicinfo" in sql_line.lower()):
                            session.execute(text(sql_line))
                            insert_count += 1
                    except Exception as e:
                        self.logger.error(f"插入SQL失败: {e}, SQL: {sql_line}")
                        session.rollback()
                        continue
                session.commit()
                self.logger.info(f"成功插入 {insert_count} 条历史行情数据到MKT_STK_BASICINFO表")
            elif file_type == 'csv':
                import csv
                file_path = Path(f'backend_core/data/daily_{date_str}.csv')
                if not file_path.exists():
                    self.logger.error(f"历史行情数据文件不存在: {file_path}")
                    return False
                insert_count = 0
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    # 字段名兼容处理
                    field_list = [f.replace('pct_change', 'pct_chg') for f in reader.fieldnames]
                    if not field_list:
                        self.logger.error(f"CSV文件无表头: {file_path}")
                        return False
                    for row in reader:
                        try:
                            # 行数据兼容处理
                            row = {k.replace('pct_change', 'pct_chg'): v for k, v in row.items()}
                            fields = ', '.join(field_list)
                            values = []
                            for k in field_list:
                                v = row.get(k, '')
                                if v is None or v == '':
                                    values.append('NULL')
                                elif k in ('ts_code', 'trade_date', 'name', 'market') or not self._is_number(v):
                                    values.append(f"'{v}'")
                                else:
                                    values.append(v)
                            values_str = ', '.join(values)
                            update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('ts_code', 'trade_date')])
                            sql_line = f"INSERT INTO MKT_STK_BASICINFO ({fields}) VALUES ({values_str}) ON CONFLICT (ts_code, trade_date) DO UPDATE SET {update_clause};"
                            session.execute(text(sql_line))
                            insert_count += 1
                        except Exception as e:
                            self.logger.error(f"CSV插入SQL失败: {e}, 行: {row}")
                            session.rollback()
                            continue
                session.commit()
                self.logger.info(f"成功插入 {insert_count} 条历史行情数据到MKT_STK_BASICINFO表")
            else:
                self.logger.error(f"不支持的 file_type: {file_type}")
                return False
            # 直接从MKT_STK_BASICINFO表取数据，去除文件读取和解析逻辑
            try:
                result = session.execute(
                    text("SELECT * FROM MKT_STK_BASICINFO WHERE trade_date = :trade_date"),
                    {"trade_date": date_str}
                )
                rows = result.fetchall()
                if not rows:
                    self.logger.error(f"MKT_STK_BASICINFO表中未找到日期为{date_str}的历史行情数据")
                    return False
                # 获取字段名
                columns = result.keys()
                row_iter = (dict(zip(columns, row)) for row in rows)
                self.logger.info(f"从MKT_STK_BASICINFO表采集到 {len(rows)} 条历史行情数据")
            except Exception as e:
                self.logger.error(f"查询MKT_STK_BASICINFO表失败: {e}")
                return False
            try:
                for row in row_iter:
                    if not row:
                        continue
                    print(f"row keys: {list(row.keys())}")
                    self.logger.warning(f"row keys: {list(row.keys())}")
                    print(f"row: {row}")
                    self.logger.warning(f"row: {row}")
                    ts_code = row.get('ts_code') or row.get(' ts_code') or row.get('`ts_code`')
                    if not ts_code:
                        self.logger.error(f"row中找不到ts_code字段: {row}")
                        continue
                    code = self.extract_code_from_ts_code(ts_code)
                    try:
                        ts_code = ts_code
                        result = session.execute(
                            text('SELECT name FROM stock_basic_info WHERE code = :code'),
                            {'code': code}
                        ).fetchone()
                        name = result[0] if result and result[0] else ''
                        market = row.get('market', '')
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
                        # 历史行情表成交量按「手」存；文件 vol 一般为股，÷100 转为手
                        vol_raw = self._safe_value(row.get('vol'))
                        volume = (vol_raw / 100) if vol_raw is not None else None
                        pre_close = self._safe_value(row.get('pre_close'))
                        high = self._safe_value(row.get('high'))
                        low = self._safe_value(row.get('low'))
                        turnover_rate = None
                        if total_share and vol_raw is not None and total_share > 0:
                            turnover_rate = vol_raw / total_share * 100
                        amplitude = None
                        if pre_close and pre_close > 0 and high is not None and low is not None:
                            amplitude = (high - low) / pre_close * 100
                        data = {
                            'code': code,
                            'ts_code': ts_code,
                            'name': name,
                            'market': market,
                            'date': datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                            'collected_source': 'tushare',
                            'collected_date': datetime.datetime.now().isoformat(),
                            'open': self._safe_value(row.get('open')),
                            'high': high,
                            'low': low,
                            'close': self._safe_value(row.get('close')),
                            'volume': volume,
                            'amount': self._safe_value(row.get('amount')) * 1000 if self._safe_value(row.get('amount')) is not None else None,
                            'change_percent': self._safe_value(row.get('pct_chg')),
                            'pre_close': pre_close,
                            'change': self._safe_value(row.get('change')),
                            'turnover_rate': turnover_rate,
                            'amplitude': amplitude
                        }
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                session.execute(text('''
                                    INSERT INTO stock_basic_info (code, name)
                                    VALUES (:code, :name)
                                    ON CONFLICT (code) DO NOTHING
                                '''), {'code': data['code'], 'name': data['name']})
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
                                if success_count % 100 == 0:
                                    session.commit()
                                    self.logger.info(f"已处理 {success_count} 条记录，提交事务")
                                success_count += 1
                                break
                            except Exception as insert_error:
                                if "DeadlockDetected" in str(insert_error):
                                    retry_count += 1
                                    self.logger.warning(f"检测到死锁，第 {retry_count} 次重试: {insert_error}")
                                    session.rollback()
                                    import time
                                    time.sleep(0.1 * retry_count)
                                    continue
                                else:
                                    raise insert_error
                        if retry_count >= max_retries:
                            fail_count += 1
                            fail_detail.append(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                            self.logger.error(f"股票 {code} 插入失败，重试 {max_retries} 次后仍然死锁")
                            continue
                    except Exception as row_e:
                        fail_count += 1
                        fail_detail.append(str(row_e))
                        self.logger.error(f"采集单条数据失败: {row_e}")
                        continue
            except Exception as e:
                self.logger.error(f"遍历历史行情数据时发生异常: {e}")
                import sys
                sys.exit(1)
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

    # 新增辅助方法
    def _is_number(self, s):
        try:
            float(s)
            return True
        except Exception:
            return False

