import pd
import pandas as pd
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import datetime
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from .base import AKShareCollector

class HKHistoricalQuoteImportFromFileCollector(AKShareCollector):
    """港股历史行情数据从文件采集器"""
    
    def _safe_value(self, val: Any) -> Optional[float]:
        return None if pd.isna(val) else float(val)
    
    def _is_number(self, s):
        try:
            float(s)
            return True
        except Exception:
            return False

    def find_file_for_date(self, date_str: str, file_type: str) -> Optional[Path]:
        """寻找指定日期的港股历史行情数据文件"""
        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
        date_hyphen = date_obj.strftime("%Y-%m-%d")
        
        # 优先查找 hk_ 前缀的文件，代表明确的港股数据
        patterns = [
            f"hk_daily_{date_str}.{file_type}",
            f"hk_daily_{date_hyphen}.{file_type}",
            f"hk_historical_quotes_{date_str}.{file_type}",
            f"hk_historical_quotes_{date_hyphen}.{file_type}",
            # 兼容普通命名的文件
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
        session = SessionLocal()
        try:
            input_params = {'date': date_str, 'market': 'HK'}
            collect_date = datetime.date.today().isoformat()
            success_count = 0
            fail_count = 0
            fail_detail = []
            
            # 1. 确保临时表存在
            create_table_sql = """
            DROP TABLE IF EXISTS MKT_STK_BASICINFO_HK;
            CREATE TABLE MKT_STK_BASICINFO_HK (
                code VARCHAR(16),
                name VARCHAR(128),
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
                turnover_rate FLOAT,
                UNIQUE(code, trade_date)
            );
            """
            try:
                session.execute(text(create_table_sql))
                session.commit()
            except Exception as e:
                self.logger.error(f"重建表MKT_STK_BASICINFO_HK失败: {e}")
                session.rollback()
                return False

            # 强制更新清理
            if force_update:
                try:
                    iso_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
                    session.execute(text("DELETE FROM historical_quotes_hk WHERE date = :t_date"), {"t_date": iso_date})
                    session.commit()
                    self.logger.info(f"强制更新模式：已预先清理 historical_quotes_hk 表中日期为 {iso_date} 的数据")
                except Exception as e:
                    self.logger.error(f"强制预清理 historical_quotes_hk 数据报错: {e}")
                    session.rollback()

            # 2. 读取文件并插入数据到临时表
            file_path = self.find_file_for_date(date_str, file_type)
            if not file_path:
                self.logger.error(f"未找到 {date_str} 的 {file_type} 文件")
                return False

            insert_count = 0
            if file_type == 'txt':
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines:
                    sql_line = line.strip()
                    if not sql_line: continue
                    # 转换 SQL 以适配港股临时表
                    sql_line = sql_line.replace("MKT_STK_BASICINFO", "MKT_STK_BASICINFO_HK")
                    sql_line = sql_line.replace("ts_code", "code") # 港股通常直接用 code
                    try:
                        session.execute(text(sql_line))
                        insert_count += 1
                    except Exception as e:
                        session.rollback()
                        continue
                session.commit()
            elif file_type == 'csv':
                import csv
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    field_list = [f.replace('pct_change', 'pct_chg').replace('ts_code', 'code') for f in reader.fieldnames]
                    for row in reader:
                        try:
                            row = {k.replace('pct_change', 'pct_chg').replace('ts_code', 'code'): v for k, v in row.items()}
                            fields = ', '.join(field_list)
                            values = []
                            for k in field_list:
                                v = row.get(k, '')
                                if v is None or v == '': values.append('NULL')
                                elif k in ('code', 'trade_date', 'name'): values.append(f"'{v}'")
                                else: values.append(str(v))
                            values_str = ', '.join(values)
                            update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('code', 'trade_date')])
                            sql = f"INSERT INTO MKT_STK_BASICINFO_HK ({fields}) VALUES ({values_str}) ON CONFLICT (code, trade_date) DO UPDATE SET {update_clause};"
                            session.execute(text(sql))
                            insert_count += 1
                        except Exception as e:
                            session.rollback()
                            continue
                session.commit()
            elif file_type == 'xlsx':
                df = pd.read_excel(file_path)
                mapping = {
                    '代码': 'code', '名称': 'name', '日期': 'trade_date', 'date': 'trade_date',
                    '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close',
                    '前收': 'pre_close', 'pre_close': 'pre_close',
                    '涨跌': 'change', '涨跌幅': 'pct_chg', '成交量': 'vol', '成交额': 'amount', '换手率': 'turnover_rate'
                }
                df.columns = [mapping.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns]
                allowed_cols = ['code', 'trade_date', 'name', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate']
                for index, row in df.iterrows():
                    try:
                        r_dict = row.to_dict()
                        if 'trade_date' in r_dict:
                            r_date = str(r_dict['trade_date']).replace('-', '').replace('/', '').split(' ')[0]
                            r_dict['trade_date'] = r_date
                        final_row = {k: v for k, v in r_dict.items() if k in allowed_cols}
                        if 'code' not in final_row or 'trade_date' not in final_row: continue
                        
                        field_list = list(final_row.keys())
                        fields = ', '.join(field_list)
                        values = []
                        for k in field_list:
                            v = final_row[k]
                            if v is None or pd.isna(v): values.append('NULL')
                            elif k in ('code', 'trade_date', 'name'): values.append(f"'{str(v).replace('\'', '\'\'')}'")
                            else: values.append(str(v))
                        values_str = ', '.join(values)
                        update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('code', 'trade_date')])
                        sql = f"INSERT INTO MKT_STK_BASICINFO_HK ({fields}) VALUES ({values_str}) ON CONFLICT (code, trade_date) DO UPDATE SET {update_clause};"
                        session.execute(text(sql))
                        insert_count += 1
                    except Exception:
                        session.rollback()
                        continue
                session.commit()

            # 3. 从临时表同步到正式表 historical_quotes_hk
            result = session.execute(text("SELECT * FROM MKT_STK_BASICINFO_HK WHERE trade_date = :trade_date"), {"trade_date": date_str})
            rows = result.fetchall()
            if not rows:
                self.logger.error(f"临时表中未找到日期为 {date_str} 的港股数据")
                return False

            columns = result.keys()
            row_iter = (dict(zip(columns, row)) for row in rows)
            
            # 预加载 stock_basic_info_hk
            stock_info_map = {}
            try:
                basic_result = session.execute(text("SELECT code, name FROM stock_basic_info_hk"))
                for b_row in basic_result.fetchall():
                    stock_info_map[str(b_row[0])] = b_row[1] or ''
            except Exception:
                pass

            iso_date_str = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

            for row in row_iter:
                code = str(row.get('code', '')).strip()
                if not code: continue
                # 港股代码补全为 5 位
                if code.isdigit() and len(code) < 5:
                    code = code.zfill(5)
                
                name = stock_info_map.get(code) or row.get('name') or ''
                
                vol_raw = self._safe_value(row.get('vol'))
                pre_close = self._safe_value(row.get('pre_close'))
                high = self._safe_value(row.get('high'))
                low = self._safe_value(row.get('low'))
                
                amplitude = None
                if pre_close and pre_close > 0 and high is not None and low is not None:
                    amplitude = (high - low) / pre_close * 100
                
                data = {
                    'code': code,
                    'ts_code': code, # 港股 ts_code 暂存 code
                    'name': name,
                    'date': iso_date_str,
                    'collected_source': 'file',
                    'collected_date': datetime.datetime.now(),
                    'open': self._safe_value(row.get('open')),
                    'high': high,
                    'low': low,
                    'close': self._safe_value(row.get('close')),
                    'volume': vol_raw, # 已是手
                    'amount': self._safe_value(row.get('amount')),
                    'change_percent': self._safe_value(row.get('pct_chg')),
                    'pre_close': pre_close,
                    'change_amount': self._safe_value(row.get('change')), # A股列名是 change
                    'turnover_rate': self._safe_value(row.get('turnover_rate')),
                    'amplitude': amplitude
                }
                
                try:
                    # 插入基础信息
                    session.execute(text('''
                        INSERT INTO stock_basic_info_hk (code, name)
                        VALUES (:code, :name)
                        ON CONFLICT (code) DO NOTHING
                    '''), {'code': data['code'], 'name': data['name']})
                    
                    # 插入历史行情
                    session.execute(text('''
                        INSERT INTO historical_quotes_hk
                        (code, ts_code, name, date, open, high, low, close, volume, amount, change_percent, pre_close, change_amount, amplitude, turnover_rate, collected_source, collected_date)
                        VALUES (:code, :ts_code, :name, :date, :open, :high, :low, :close, :volume, :amount, :change_percent, :pre_close, :change_amount, :amplitude, :turnover_rate, :collected_source, :collected_date)
                        ON CONFLICT (code, date) DO UPDATE SET
                            name = EXCLUDED.name,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            amount = EXCLUDED.amount,
                            change_percent = EXCLUDED.change_percent,
                            pre_close = EXCLUDED.pre_close,
                            change_amount = EXCLUDED.change_amount,
                            amplitude = EXCLUDED.amplitude,
                            turnover_rate = EXCLUDED.turnover_rate,
                            collected_source = EXCLUDED.collected_source,
                            collected_date = EXCLUDED.collected_date
                    '''), data)
                    
                    success_count += 1
                    if success_count % 100 == 0:
                        session.commit()
                except Exception as e:
                    session.rollback()
                    fail_count += 1
                    fail_detail.append(f"{code}: {str(e)}")
            
            # 4. 记录日志
            session.execute(text('''
                INSERT INTO historical_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source)
                VALUES (:type, :desc, :rows, :status, :err, :source)
                '''), {
                    'type': 'hk_historical_file_collect',
                    'desc': f'从文件采集港股历史行情: {date_str}',
                    'rows': success_count,
                    'status': 'success' if fail_count == 0 else 'partial',
                    'err': '\n'.join(fail_detail[:10]) if fail_count > 0 else None,
                    'source': 'file'
                })
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"港股文件同步失败: {e}")
            return False
        finally:
            session.close()
