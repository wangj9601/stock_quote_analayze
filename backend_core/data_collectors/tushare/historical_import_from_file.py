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
    
    def find_file_for_date(self, date_str: str, file_type: str) -> Optional[Path]:
        """寻找指定日期的历史行情数据文件，尝试多种命名称规范"""
        # date_str 格式通常为 YYYYMMDD
        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
        date_hyphen = date_obj.strftime("%Y-%m-%d")
        
        # 定义尝试的文件名格式
        patterns = [
            f"daily_{date_str}.{file_type}",
            f"daily_{date_hyphen}.{file_type}",
            f"historical_quotes_{date_str}.{file_type}",
            f"historical_quotes_{date_hyphen}.{file_type}"
        ]
        
        for p in patterns:
            file_path = Path(f'backend_core/data/{p}')
            if file_path.exists():
                return file_path
        return None
    
    def collect_historical_quotes(self, date_str: str, file_type: str, force_update: bool = False) -> bool:
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
            -- 每次同步前重建临时表，确保字段结构最新
            DROP TABLE IF EXISTS MKT_STK_BASICINFO;
            CREATE TABLE MKT_STK_BASICINFO (
                ts_code VARCHAR(32),
                trade_date VARCHAR(16),
                code VARCHAR(16),
                name VARCHAR(128),
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                pre_close FLOAT,
                change FLOAT,
                pct_chg FLOAT,
                vol FLOAT,
                amount FLOAT,
                turnover_rate FLOAT,
                UNIQUE(ts_code, trade_date)
            );
            """
            try:
                session.execute(text(create_table_sql))
                # 再次尝试添加唯一约束，防止重建时逻辑遗漏（虽然CREATE TABLE已有UNIQUE）
                try:
                    session.execute(text("ALTER TABLE MKT_STK_BASICINFO ADD CONSTRAINT uniq_ts_code_trade_date UNIQUE(ts_code, trade_date);"))
                except Exception as e:
                    pass # 忽略重建时的重复约束错误
                session.commit()
            except Exception as e:
                self.logger.error(f"重建表MKT_STK_BASICINFO失败: {e}")
                session.rollback()
                return False

            # 如果启用强制更新，在正式采集前清理 historical_quotes 对应日期的数据
            if force_update:
                try:
                    iso_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    # 删除 A 股历史行情表中该日期的存量数据，如果是跨多个日期同步则会依次循环执行删除
                    session.execute(text("DELETE FROM historical_quotes WHERE date = :t_date"), {"t_date": iso_date})
                    session.commit()
                    self.logger.info(f"强制更新模式已启用：已预先清理 historical_quotes 表中日期为 {iso_date} 的数据")
                except Exception as e:
                    self.logger.error(f"强制预清理 historical_quotes 数据报错: {e}")
                    session.rollback()

            # 2. 读取文件并插入数据
            if file_type == 'txt':
                file_path = self.find_file_for_date(date_str, 'txt')
                if not file_path:
                    import os
                    cwd = os.getcwd()
                    self.logger.error(f"未找到 {date_str} 的 TXT 文件。当前路径: {cwd}，查找路径: backend_core/data/，请确保文件名为 daily_{date_str}.txt 或 historical_quotes_{date_str}.txt (支持中划线日期)。")
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
                file_path = self.find_file_for_date(date_str, 'csv')
                if not file_path:
                    self.logger.error(f"历史行情数据文件不存在(尝试了多种命名称): daily_{date_str}.csv 或 historical_quotes_{date_str}.csv 等")
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
            elif file_type == 'xlsx':
                file_path = self.find_file_for_date(date_str, 'xlsx')
                if not file_path:
                    import os
                    cwd = os.getcwd()
                    self.logger.error(f"未找到 {date_str} 的 XLSX 文件。当前路径: {cwd}，查找路径: backend_core/data/，请确保文件名为 daily_{date_str}.xlsx 或 historical_quotes_{date_str}.xlsx (支持中划线日期)。")
                    return False
                try:
                    df = pd.read_excel(file_path)
                    
                    # 统一定义字段映射，将常见的中文和英文名映射到数据库字段
                    mapping = {
                        '代码': 'code', '名称': 'name', '日期': 'trade_date', 'date': 'trade_date',
                        '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close',
                        '前收': 'pre_close', 'pre_close': 'pre_close',
                        '涨跌': 'change', '漲跌': 'change',
                        '涨跌幅': 'pct_chg', 'pct_change': 'pct_chg', 'change_percent': 'pct_chg',
                        '成交量': 'vol', 'volume': 'vol',
                        '成交额': 'amount', 'amount': 'amount',
                        '换手率': 'turnover_rate', 'turnover_rate': 'turnover_rate'
                    }
                    df.columns = [mapping.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns]
                    
                    # 定义允许插入的列名列表
                    allowed_cols = ['ts_code', 'trade_date', 'code', 'name', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate']
                    
                    insert_count = 0
                    for index, row in df.iterrows():
                        try:
                            # 1. 基础字段处理
                            r_dict = row.to_dict()
                            
                            # 2. ts_code 处理：如果缺少 ts_code 但有 code
                            if 'ts_code' not in r_dict or pd.isna(r_dict['ts_code']):
                                c = str(r_dict.get('code', '')).strip()
                                # 补全为 6 位数字
                                if c.isdigit() and len(c) < 6:
                                    c = c.zfill(6)
                                    r_dict['code'] = c
                                
                                if c:
                                    if c.startswith('60') or c.startswith('68'):
                                        r_dict['ts_code'] = f"{c}.SH"
                                    elif c.startswith('00') or c.startswith('30'):
                                        r_dict['ts_code'] = f"{c}.SZ"
                                    elif c.startswith('43') or c.startswith('83') or c.startswith('87') or c.startswith('88') or c.startswith('92'):
                                        r_dict['ts_code'] = f"{c}.BJ"
                                    else:
                                        # 如果无法识别，可以加上通用的后缀，或者保持原样
                                        r_dict['ts_code'] = c
                            
                            # 3. trade_date 处理：确保格式正确 (YYYYMMDD)
                            if 'trade_date' in r_dict:
                                r_date = str(r_dict['trade_date'])
                                r_date = r_date.replace('-', '').replace('/', '').split(' ')[0] # 移除时间部分
                                r_dict['trade_date'] = r_date
                            
                            # 4. 只保留合法列
                            final_row = {k: v for k, v in r_dict.items() if k in allowed_cols}
                            if 'ts_code' not in final_row or 'trade_date' not in final_row:
                                continue
                                
                            field_list = list(final_row.keys())
                            fields = ', '.join(field_list)
                            values = []
                            for k in field_list:
                                v = final_row[k]
                                if v is None or pd.isna(v):
                                    values.append('NULL')
                                elif k in ('ts_code', 'trade_date', 'code', 'name', 'market') or not self._is_number(str(v)):
                                    clean_v = str(v).replace("'", "''")
                                    values.append(f"'{clean_v}'")
                                else:
                                    values.append(str(v))
                                    
                            values_str = ', '.join(values)
                            update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('ts_code', 'trade_date')])
                            sql_line = f"INSERT INTO MKT_STK_BASICINFO ({fields}) VALUES ({values_str}) ON CONFLICT (ts_code, trade_date) DO UPDATE SET {update_clause};"
                            session.execute(text(sql_line))
                            insert_count += 1
                        except Exception as inner_e:
                            session.rollback()
                            if index < 5: # 只打印前几行的错误
                                self.logger.error(f"Excel行插入失败: {inner_e}, 行号: {index}")
                            continue
                    session.commit()
                    self.logger.info(f"从Excel成功插入 {insert_count} 条数据到MKT_STK_BASICINFO")
                except Exception as e:
                    self.logger.error(f"读取或解析Excel文件失败: {e}")
                    return False
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
            # 预加载 stock_basic_info 以提升效率
            stock_info_map = {}
            try:
                basic_result = session.execute(text("SELECT code, name, total_shares FROM stock_basic_info"))
                for b_row in basic_result.fetchall():
                    # sqlalchemy row 索引：0-code, 1-name, 2-total_shares
                    stock_info_map[str(b_row[0])] = {'name': b_row[1] or '', 'total_share': b_row[2]}
            except Exception as e:
                self.logger.warning(f"预加载stock_basic_info失败，将使用行级查询: {e}")

            try:
                for row in row_iter:
                    if not row:
                        continue
                    # 移除调试日志
                    ts_code = row.get('ts_code') or row.get(' ts_code') or row.get('`ts_code`')
                    if not ts_code:
                        self.logger.error(f"row中找不到ts_code字段: {row}")
                        continue
                    code = self.extract_code_from_ts_code(ts_code)
                    try:
                        # 从内存 map 获取基础信息，减少 DB 查询压力
                        s_info = stock_info_map.get(code)
                        if s_info:
                            name = s_info['name']
                            total_share = s_info['total_share']
                        else:
                            # fallback: 内存没找到才查库
                            res = session.execute(
                                text('SELECT name, total_shares FROM stock_basic_info WHERE code = :code'),
                                {'code': code}
                            ).fetchone()
                            name = res[0] if res and res[0] else ''
                            total_share = float(res[1]) if res and res[1] else None
                        
                        market = row.get('market', '')
                        # 历史行情表成交量按「手」存；用户反馈文件 vol 已经是手，直接保存
                        vol_raw = self._safe_value(row.get('vol'))
                        volume = vol_raw
                        pre_close = self._safe_value(row.get('pre_close'))
                        high = self._safe_value(row.get('high'))
                        low = self._safe_value(row.get('low'))
                        
                        # 优先使用文件中的换手率，如果没有则计算
                        turnover_rate = self._safe_value(row.get('turnover_rate'))
                        if turnover_rate is None and total_share and vol_raw is not None and total_share > 0:
                            # 注意：total_share 通常为股，vol_raw 为手，需换算：(手*100)/股 * 100
                            turnover_rate = (vol_raw * 100) / total_share * 100
                        amplitude = None
                        if pre_close and pre_close > 0 and high is not None and low is not None:
                            amplitude = (high - low) / pre_close * 100
                        data = {
                            'code': code,
                            'ts_code': ts_code,
                            'name': name,
                            'market': market,
                            'date': datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                            'collected_source': 'file',
                            'collected_date': datetime.datetime.now().isoformat(),
                            'open': self._safe_value(row.get('open')),
                            'high': high,
                            'low': low,
                            'close': self._safe_value(row.get('close')),
                            'volume': volume,
                            'amount': self._safe_value(row.get('amount')),
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
                raise e
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

