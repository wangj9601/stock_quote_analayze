import pandas as pd
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import datetime
import re
from backend_core.database.db import SessionLocal
from sqlalchemy import text
from .base import AKShareCollector


HK_HIST_DATA_DIR = Path("backend_core") / "data"
HK_HIST_FILE_PREFIX = "hk_historical_quotes_"


def load_hk_quote_file_dataframe(file_path: Path) -> pd.DataFrame:
    """读取港股行情文件；兼容同花顺伪 xls（GBK 制表符文本）。"""
    from io import BytesIO, StringIO

    path = Path(file_path)
    content = path.read_bytes()
    if not content:
        raise RuntimeError(f"文件为空: {path}")

    suffix = path.suffix.lower()
    parse_errors = []

    def _ok(trial):
        return trial is not None and not trial.empty and len(trial.columns) >= 2

    def _score_headers(trial) -> int:
        """已知中文/英列表头命中越多越优先（避免错误编码“伪成功”）。"""
        known = {
            "代码", "名称", "现价", "总手", "昨收", "开盘", "最高", "最低",
            "涨幅", "涨跌", "成交额", "成交量", "换手率",
            "code", "name", "open", "high", "low", "close", "vol", "amount",
        }
        hits = 0
        for c in trial.columns:
            s = str(c).strip().replace("%", "").replace("％", "")
            if s in known or s.lower() in known:
                hits += 1
        return hits

    def _pick_best(candidates):
        best = None
        best_score = -1
        for trial in candidates:
            if not _ok(trial):
                continue
            sc = _score_headers(trial)
            if sc > best_score:
                best, best_score = trial, sc
        return best

    # OLE Compound / ZIP(xlsx) 才优先走 Excel；同花顺伪 xls 实为文本
    is_ole = content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    is_zip = content[:2] == b"PK"
    looks_like_text = (b"\t" in content[:4096]) or (not is_ole and not is_zip)

    if suffix == ".csv":
        trials = []
        for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                trials.append(pd.read_csv(BytesIO(content), encoding=enc))
            except Exception as e:  # noqa: BLE001
                parse_errors.append(f"csv({enc}): {e}")
        picked = _pick_best(trials)
        if picked is not None:
            return picked

    text_trials = []
    if looks_like_text or suffix in (".xls", ".txt", ".csv"):
        for enc in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
            try:
                txt = content.decode(enc, errors="strict")
                if "\t" in txt:
                    text_trials.append(pd.read_csv(StringIO(txt), sep="\t"))
                else:
                    text_trials.append(pd.read_csv(StringIO(txt), sep=None, engine="python"))
            except Exception as e:  # noqa: BLE001
                parse_errors.append(f"text({enc}): {e}")
        picked = _pick_best(text_trials)
        if picked is not None and (_score_headers(picked) > 0 or looks_like_text):
            return picked

    if suffix in (".xlsx", ".xls") and (is_ole or is_zip or not looks_like_text):
        engines = ("openpyxl", "xlrd") if suffix == ".xlsx" else ("xlrd", "openpyxl")
        for engine in engines:
            try:
                trial = pd.read_excel(BytesIO(content), engine=engine)
                if _ok(trial):
                    return trial
            except Exception as e:  # noqa: BLE001
                parse_errors.append(f"excel({engine}): {e}")

    picked = _pick_best(text_trials)
    if picked is not None:
        return picked

    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            tables = pd.read_html(BytesIO(content), encoding=enc)
            if tables and _ok(tables[0]):
                return tables[0]
        except Exception as e:  # noqa: BLE001
            parse_errors.append(f"html({enc}): {e}")

    detail = "; ".join(parse_errors[-6:]) if parse_errors else "未知原因"
    raise RuntimeError(f"港股行情文件解析失败: {path.name} ({detail})")


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
        '总手': 'vol', '现价': 'close', '最新价': 'close',
        '涨幅': 'pct_chg', '涨跌幅%': 'pct_chg',
        'amount': 'amount', '成交额': 'amount', 'turnover': 'amount', 'amt': 'amount', '金额': 'amount',
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
                rows_loaded = None
                last_enc_err = None
                for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030'):
                    try:
                        with open(file_path, "r", encoding=enc) as f:
                            reader = csv.DictReader(f)
                            rows_loaded = list(reader)
                        break
                    except Exception as e:
                        last_enc_err = e
                        rows_loaded = None
                if rows_loaded is None:
                    self.logger.error(f"CSV 读取失败 {file_path}: {last_enc_err}")
                    return False
                for row in rows_loaded:
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
                try:
                    df = load_hk_quote_file_dataframe(file_path)
                except Exception as e:
                    self.logger.error(f"读取港股历史文件失败 {file_path}: {e}")
                    return False
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


def normalize_hk_historical_upload_df(df: pd.DataFrame, trade_date_ymd: str) -> pd.DataFrame:
    """
    将上传表规范为采集器 CSV 列：
    code,trade_date,name,open,high,low,close,pre_close,change,pct_chg,vol,amount,turnover_rate
    trade_date_ymd: YYYYMMDD
    """
    from backend_api.utils.equity_code import normalize_equity_code

    collector = HKHistoricalQuoteImportFromFileCollector()
    # 必须保留 DataFrame 原始列对象（同花顺表头常带尾部空格）
    col_norm = {}  # original_col -> canonical
    for c in df.columns:
        col_norm[c] = collector._normalize_hk_file_column(c)

    alias_extra = {
        "现价": "close",
        "最新价": "close",
        "收盘": "close",
        "收盘价": "close",
        "总手": "vol",
        "成交量": "vol",
        "金额": "amount",
        "成交额": "amount",
        "涨幅%": "pct_chg",
        "涨幅": "pct_chg",
        "涨跌幅": "pct_chg",
        "涨跌": "change",
        "昨收": "pre_close",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "换手率": "turnover_rate",
        "代码": "code",
        "名称": "name",
    }
    for orig in list(col_norm.keys()):
        raw = str(orig).strip()
        raw2 = raw.replace("%", "").replace("％", "").strip()
        if raw in alias_extra:
            col_norm[orig] = alias_extra[raw]
        elif raw2 in alias_extra:
            col_norm[orig] = alias_extra[raw2]

    rev = {}
    for orig, canon in col_norm.items():
        if canon and canon not in rev:
            rev[canon] = orig

    def series_of(*names):
        for n in names:
            orig = rev.get(n)
            if orig is not None:
                return df[orig]
        return None

    code_s = series_of("code")
    if code_s is None:
        raise RuntimeError(f"缺少代码列，实际列: {list(df.columns)}")

    out_rows = []
    for i in range(len(df)):
        raw_code = code_s.iloc[i]
        code = normalize_equity_code(raw_code)
        if not code or not str(code).isdigit():
            s = str(raw_code or "").strip().upper()
            if s.startswith("HK") and s[2:].isdigit():
                code = s[2:].zfill(5)
            else:
                continue
        if len(code) <= 5:
            code = code.zfill(5)

        def cell(*names):
            s = series_of(*names)
            if s is None:
                return None
            v = s.iloc[i]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            if isinstance(v, str):
                t = v.strip().replace(",", "").replace("%", "")
                if t in ("", "-", "--"):
                    return None
                return t
            return v

        name = cell("name")
        name = str(name).strip() if name is not None else ""
        if name in ("-", "--", "nan", "None"):
            name = ""

        out_rows.append(
            {
                "code": code,
                "trade_date": trade_date_ymd,
                "name": name,
                "open": cell("open"),
                "high": cell("high"),
                "low": cell("low"),
                "close": cell("close"),
                "pre_close": cell("pre_close"),
                "change": cell("change"),
                "pct_chg": cell("pct_chg"),
                "vol": cell("vol"),
                "amount": cell("amount"),
                "turnover_rate": cell("turnover_rate"),
            }
        )

    if not out_rows:
        raise RuntimeError("规范化后无有效港股行")
    return pd.DataFrame(out_rows)


def save_hk_historical_upload_as_csv(
    source_path: Path,
    trade_date: str,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """解析上传文件并保存为 hk_historical_quotes_YYYYMMDD.csv。"""
    ymd = str(trade_date).strip().replace("-", "").replace("/", "")
    if len(ymd) != 8 or not ymd.isdigit():
        raise ValueError(f"无效交易日: {trade_date}")
    root = Path(data_dir) if data_dir else HK_HIST_DATA_DIR
    root.mkdir(parents=True, exist_ok=True)

    df_raw = load_hk_quote_file_dataframe(Path(source_path))
    df_out = normalize_hk_historical_upload_df(df_raw, ymd)
    saved_name = f"{HK_HIST_FILE_PREFIX}{ymd}.csv"
    out_path = root / saved_name
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    return {
        "filename": saved_name,
        "path": str(out_path),
        "trade_date": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}",
        "rows": len(df_out),
        "file_type": "csv",
    }
