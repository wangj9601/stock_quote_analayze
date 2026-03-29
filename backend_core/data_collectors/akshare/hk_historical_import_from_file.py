import pandas as pd
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import datetime
import re
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from .base import AKShareCollector


def complete_hk_change_fields(
    pre_close: Optional[float],
    close_v: Optional[float],
    chg_amt: Optional[float],
    chg_pct: Optional[float],
) -> tuple:
    """在昨收、收盘、涨跌额、涨跌幅(%)之间互推，尽量填满（文件仅含部分列时）。返回 (pre_close, close, change_amount, change_percent)。"""
    pc = pre_close
    cl = close_v
    ca = chg_amt
    cp = chg_pct
    try:
        if ca is None and cl is not None and pc is not None:
            ca = float(cl) - float(pc)
        if pc is None and cl is not None and ca is not None:
            pc = float(cl) - float(ca)
        if cp is None and cl is not None and pc is not None and float(pc) != 0:
            cp = (float(cl) - float(pc)) / float(pc) * 100.0
        if pc is None and cl is not None and cp is not None and abs(float(cp) + 100.0) > 1e-6:
            pc = float(cl) / (1.0 + float(cp) / 100.0)
        if ca is None and cl is not None and pc is not None:
            ca = float(cl) - float(pc)
        if cp is None and cl is not None and pc is not None and float(pc) != 0:
            cp = (float(cl) - float(pc)) / float(pc) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return pc, cl, ca, cp


class HKHistoricalQuoteImportFromFileCollector(AKShareCollector):
    """港股历史行情数据从文件采集器"""

    # 文件表头（中/英）-> 临时表 MKT_STK_BASICINFO_HK 列名；成交量在库内统一为 vol
    _HK_FILE_COL_MAP = {
        'ts_code': 'code', 'symbol': 'code', '股票代码': 'code', '代码': 'code', 'code': 'code',
        'name': 'name', '名称': 'name', '股票名称': 'name',
        'trade_date': 'trade_date', '日期': 'trade_date', 'date': 'trade_date',
        'open': 'open', '开盘': 'open',
        'high': 'high', '最高': 'high',
        'low': 'low', '最低': 'low',
        'close': 'close', '收盘': 'close', '收盘价': 'close',
        'pre_close': 'pre_close', '前收': 'pre_close', '昨收': 'pre_close',
        '前收盘价': 'pre_close', '昨收价': 'pre_close', 'previous_close': 'pre_close',
        'prev_close': 'pre_close', 'prior_close': 'pre_close', 'last_close': 'pre_close',
        'change': 'change', '涨跌': 'change', '涨跌额': 'change',
        # 涨跌额常见导出列名 -> 临时表 change（入库 historical_quotes_hk.change_amount）
        'change_amount': 'change', 'net_change': 'change', 'price_change': 'change',
        'chg': 'change', 'quote_change': 'change', 'delta': 'change',
        'pct_chg': 'pct_chg', 'pct_change': 'pct_chg', '涨跌幅': 'pct_chg', 'changepercent': 'pct_chg',
        # 常见导出列名 change_percent 与临时表 pct_chg 对齐
        'change_percent': 'pct_chg', 'chg_pct': 'pct_chg', 'quote_change_pct': 'pct_chg',
        '涨跌幅(%)': 'pct_chg', '涨跌幅％': 'pct_chg', '涨跌幅度': 'pct_chg',
        'vol': 'vol', 'volume': 'vol', 'qty': 'vol', '成交量': 'vol', 'vol.': 'vol',
        'amount': 'amount', '成交额': 'amount', 'turnover': 'amount', 'amt': 'amount',
        'turnover_rate': 'turnover_rate', '换手率': 'turnover_rate',
    }

    def _normalize_hk_file_column(self, col: Any) -> str:
        if col is None:
            return ''
        c = str(col).strip()
        # 去掉括号与百分号，便于匹配「涨跌幅(%)」等表头
        for noise in ('(%)', '(％)', '％', '%'):
            c = c.replace(noise, '')
        c = c.strip()
        cl = c.lower().replace(' ', '_')
        return (
            self._HK_FILE_COL_MAP.get(c)
            or self._HK_FILE_COL_MAP.get(cl)
            or self._HK_FILE_COL_MAP.get(c.lower())
            or cl
        )

    def _safe_value(self, val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            if isinstance(val, str):
                s = val.strip().replace(',', '').replace('，', '').replace('%', '').replace('％', '')
                if s == '' or s.lower() in ('nan', 'none', '-', '--'):
                    return None
                return float(s)
            if isinstance(val, (int, float)) and pd.isna(val):
                return None
            if pd.isna(val):
                return None
            return float(val)
        except (TypeError, ValueError):
            return None

    def _row_volume(self, row: Dict[str, Any]) -> Optional[float]:
        """临时表行中读取成交量：兼容 vol / volume 及大小写。"""
        for k in ('vol', 'volume'):
            if k in row and row[k] is not None:
                v = self._safe_value(row[k])
                if v is not None:
                    return v
        for rk, rv in row.items():
            if rk is not None and str(rk).lower() in ('vol', 'volume'):
                v = self._safe_value(rv)
                if v is not None:
                    return v
        return None

    def _row_pct_chg(self, row: Dict[str, Any]) -> Optional[float]:
        """涨跌幅：临时表列为 pct_chg，兼容 change_percent / pct_change 等别名。"""
        for k in ('pct_chg', 'change_percent', 'pct_change', 'chg_pct', 'quote_change_pct'):
            if k in row and row[k] is not None:
                v = self._safe_value(row[k])
                if v is not None:
                    return v
        for rk, rv in row.items():
            if rk is None:
                continue
            rkl = str(rk).lower()
            if rkl in ('pct_chg', 'change_percent', 'pct_change', 'chg_pct', 'quote_change_pct'):
                v = self._safe_value(rv)
                if v is not None:
                    return v
        return None

    def _row_change_amount(self, row: Dict[str, Any]) -> Optional[float]:
        """涨跌额：临时表列为 change，兼容 change_amount / chg 等别名。"""
        for k in ('change', 'change_amount', 'chg', 'net_change', 'price_change', 'quote_change', 'delta'):
            if k in row and row[k] is not None:
                v = self._safe_value(row[k])
                if v is not None:
                    return v
        for rk, rv in row.items():
            if rk is None:
                continue
            rkl = str(rk).lower()
            if rkl in ('change', 'change_amount', 'net_change', 'price_change', 'quote_change', 'chg', 'delta'):
                v = self._safe_value(rv)
                if v is not None:
                    return v
        return None

    def _normalize_sql_row_keys(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """查询结果列名统一为小写，避免驱动返回大小写不一致导致取不到 pct_chg。"""
        out: Dict[str, Any] = {}
        for k, v in row.items():
            key = str(k).lower()
            if '.' in key:
                key = key.split('.')[-1]
            out[key] = v
        return out
    
    def _is_number(self, s):
        try:
            float(s)
            return True
        except Exception:
            return False

    def _normalize_trade_date_key(self, raw: Any) -> str:
        """将单元格日期规范为 YYYYMMDD，便于与任务循环日比较。"""
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return ''
        s = str(raw).strip().replace('-', '').replace('/', '').split(' ')[0]
        digits = re.sub(r'[^0-9]', '', s)
        if len(digits) >= 8:
            return digits[:8]
        return ''

    def _date_in_filename_range(self, stem: str, date_str: str) -> bool:
        """文件名中含 _to_ 区间（支持 YYYY-MM-DD 或 YYYYMMDD）时，判断 date_str 是否落在区间内。"""
        m = re.search(r'(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})', stem, re.I)
        if m:
            s = m.group(1).replace('-', '')
            e = m.group(2).replace('-', '')
            return len(s) == 8 and len(e) == 8 and s <= date_str <= e
        m = re.search(r'(\d{8})_to_(\d{8})', stem)
        if m:
            return m.group(1) <= date_str <= m.group(2)
        return False

    def find_file_for_date(self, date_str: str, file_type: str) -> Optional[Path]:
        """寻找指定交易日对应的港股历史行情文件。

        支持：
        - 单日命名：hk_historical_quotes_20260205.xlsx
        - 区间命名：hk_historical_quotes_2026-02-10_to_2026-02-13.xlsx（任一日在区间内即命中同一文件）
        - 目录内仅有一个 hk_historical_quotes* / hk_daily* 时，按「多日期汇总文件」使用（行内 trade_date 再过滤）
        """
        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
        date_hyphen = date_obj.strftime("%Y-%m-%d")
        data_dir = Path('backend_core/data')

        # 1) 精确单日文件名
        patterns = [
            f"hk_daily_{date_str}.{file_type}",
            f"hk_daily_{date_hyphen}.{file_type}",
            f"hk_historical_quotes_{date_str}.{file_type}",
            f"hk_historical_quotes_{date_hyphen}.{file_type}",
            f"daily_{date_str}.{file_type}",
            f"daily_{date_hyphen}.{file_type}",
            f"historical_quotes_{date_str}.{file_type}",
            f"historical_quotes_{date_hyphen}.{file_type}",
        ]
        for p in patterns:
            file_path = data_dir / p
            if file_path.exists():
                return file_path

        # 2) 文件名带 _to_ 日期区间
        globs = [
            f"hk_historical_quotes*.{file_type}",
            f"hk_daily*.{file_type}",
            f"historical_quotes*.{file_type}",
        ]
        for pattern in globs:
            for path in sorted(data_dir.glob(pattern)):
                if pattern.startswith('historical_quotes') and path.name.startswith('hk_'):
                    continue
                if self._date_in_filename_range(path.stem, date_str):
                    self.logger.info(f"使用区间文件 {path.name} 导入交易日 {date_str}")
                    return path

        # 3) 仅有一个汇总文件时（无单日/区间匹配时），按多日期文件处理
        for pattern in (f"hk_historical_quotes*.{file_type}", f"hk_daily*.{file_type}"):
            cands = sorted(data_dir.glob(pattern))
            if len(cands) == 1:
                self.logger.info(f"使用唯一汇总文件 {cands[0].name} 导入交易日 {date_str}（请确认含 trade_date/日期 列）")
                return cands[0]

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

            iso_date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

            # 先解析文件：找不到文件或文件中无该日时，不得删除 historical_quotes_hk 当日数据
            file_path = self.find_file_for_date(date_str, file_type)
            if not file_path:
                self.logger.warning(
                    f"未找到交易日 {date_str} 对应的 {file_type} 文件，跳过该日"
                    f"（可将文件放入 backend_core/data，或使用 hk_historical_quotes*_日期区间*.xlsx 覆盖该日）"
                )
                return False

            # 2. 读取文件并插入数据到临时表
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
                    # 临时表涨跌幅列为 pct_chg（与 A 股导出 SQL 中 pct_change 对齐）
                    sql_line = sql_line.replace("pct_change", "pct_chg")
                    # 涨跌额列统一为 change（与部分导出中 change_amount 对齐）
                    sql_line = sql_line.replace("change_amount", "change")
                    try:
                        session.execute(text(sql_line))
                        insert_count += 1
                    except Exception as e:
                        session.rollback()
                        continue
                session.commit()
            elif file_type == 'csv':
                import csv
                allowed_hk = {'code', 'trade_date', 'name', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate'}
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            norm_row = {}
                            for k, v in row.items():
                                if k is None:
                                    continue
                                nk = self._normalize_hk_file_column(k)
                                if nk:
                                    norm_row[nk] = v
                            td_norm = self._normalize_trade_date_key(norm_row.get('trade_date'))
                            if td_norm and td_norm != date_str:
                                continue
                            field_list = [c for c in norm_row.keys() if c in allowed_hk]
                            if not field_list:
                                continue
                            fields = ', '.join(field_list)
                            values = []
                            for k in field_list:
                                v = norm_row.get(k, '')
                                if v is None or v == '':
                                    values.append('NULL')
                                elif k in ('code', 'trade_date', 'name'):
                                    values.append(f"'{v}'")
                                else:
                                    values.append(str(v))
                            values_str = ', '.join(values)
                            update_clause = ', '.join([f"{f}=EXCLUDED.{f}" for f in field_list if f not in ('code', 'trade_date')])
                            sql = f"INSERT INTO MKT_STK_BASICINFO_HK ({fields}) VALUES ({values_str}) ON CONFLICT (code, trade_date) DO UPDATE SET {update_clause};"
                            session.execute(text(sql))
                            insert_count += 1
                        except Exception:
                            session.rollback()
                            continue
                session.commit()
            elif file_type == 'xlsx':
                df = pd.read_excel(file_path)
                allowed_cols = ['code', 'trade_date', 'name', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate']
                df.columns = [self._normalize_hk_file_column(c) for c in df.columns]
                for index, row in df.iterrows():
                    try:
                        r_dict = row.to_dict()
                        if 'trade_date' in r_dict:
                            r_date = str(r_dict['trade_date']).replace('-', '').replace('/', '').split(' ')[0]
                            r_dict['trade_date'] = r_date
                        td_norm = self._normalize_trade_date_key(r_dict.get('trade_date'))
                        if td_norm and td_norm != date_str:
                            continue
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

            # 3. 从临时表同步到正式表 historical_quotes_hk（trade_date 兼容 20260205 / 2026-02-05）
            result = session.execute(text("""
                SELECT * FROM MKT_STK_BASICINFO_HK
                WHERE regexp_replace(coalesce(trade_date::text, ''), '[^0-9]', '', 'g') = :trade_date
            """), {"trade_date": date_str})
            rows = result.fetchall()
            if not rows:
                self.logger.warning(
                    f"文件 {file_path.name} 中未包含交易日 {date_str} 的行情行，跳过该日且保留库内已有数据"
                )
                return False

            # 确认临时表有该日数据后，再删除当日旧行情并写入（避免无文件/无行时误删）
            try:
                session.execute(text("DELETE FROM historical_quotes_hk WHERE date = :t_date"), {"t_date": iso_date})
                session.commit()
                self.logger.info(f"已清理 historical_quotes_hk 中日期 {iso_date} 的旧数据，准备写入文件行情")
            except Exception as e:
                self.logger.error(f"清理 historical_quotes_hk 当日旧数据失败: {e}")
                session.rollback()
                return False

            columns = result.keys()
            row_iter = (
                self._normalize_sql_row_keys(dict(zip(columns, row)))
                for row in rows
            )
            
            # 预加载 stock_basic_info_hk
            stock_info_map = {}
            try:
                basic_result = session.execute(text("SELECT code, name FROM stock_basic_info_hk"))
                for b_row in basic_result.fetchall():
                    stock_info_map[str(b_row[0])] = b_row[1] or ''
            except Exception:
                pass

            iso_date_str = iso_date

            for row in row_iter:
                code = str(row.get('code', '')).strip()
                if not code: continue
                # 港股代码补全为 5 位
                if code.isdigit() and len(code) < 5:
                    code = code.zfill(5)
                
                name = stock_info_map.get(code) or row.get('name') or ''
                
                vol_raw = self._row_volume(row)
                pre_close = self._safe_value(row.get('pre_close'))
                high = self._safe_value(row.get('high'))
                low = self._safe_value(row.get('low'))
                
                close_v = self._safe_value(row.get('close'))
                chg_pct = self._row_pct_chg(row)
                chg_amt = self._row_change_amount(row)
                pre_close, close_v, chg_amt, chg_pct = complete_hk_change_fields(
                    pre_close, close_v, chg_amt, chg_pct
                )

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
                    'close': close_v,
                    'volume': vol_raw, # 已是手
                    'amount': self._safe_value(row.get('amount')),
                    'change_percent': chg_pct,
                    'pre_close': pre_close,
                    'change_amount': chg_amt,
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
