# -*- coding: utf-8 -*-
"""港股资金流向文件采集：hk_fund_flow_YYYYMMDD → stock_fund_flow_daily_hk。

口径（1A）：流入 = 外盘/(外盘+内盘)×金额，流出 = 内盘/(外盘+内盘)×金额，净额 = 流入−流出。
外盘+内盘为 0 或无效时，流入/流出/净额置空。

另：港股实时接口全量不足 100 条时，可从当日 hk_fund_flow_YYYYMMDD 文件补写
stock_realtime_quote_hk；当日文件不存在则视为采集失败（不再回退历史文件）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text

from backend_api.utils.equity_code import normalize_equity_code
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FILE_PREFIX = "hk_fund_flow_"
SUPPORTED_EXTS = (".xlsx", ".xls", ".csv")
HK_REALTIME_FILE_MIN_ROWS = 100


def parse_numeric(val: Any) -> Optional[float]:
    """解析数值；支持科学计数法；`--` / 空视为 None。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    s = str(val).strip().replace(",", "").replace("，", "").replace("%", "")
    if not s or s in ("-", "--", "None", "nan", "NaN", "无"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_percent(val: Any) -> Optional[float]:
    return parse_numeric(val)


def normalize_hk_fund_flow_code(val: Any) -> Optional[str]:
    """HK0001 / 0001 / 1 → 00001。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s or s in ("-", "--"):
        return None
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        s = s[:-2]
    code = normalize_equity_code(s)
    if code and code.isdigit() and len(code) == 5:
        return code
    # 去掉 HK 后仍可能非纯数字（极少见），原样返回归一化结果若为数字
    if code and code.isdigit():
        return code.zfill(5) if len(code) <= 5 else code
    return None


def compute_flow_from_outer_inner(
    amount: Optional[float],
    outer: Optional[float],
    inner: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """1A：按内外盘占比分摊成交额。返回 (inflow, outflow, net)。"""
    if amount is None:
        return None, None, None
    o = outer if outer is not None else None
    i = inner if inner is not None else None
    if o is None and i is None:
        return None, None, None
    o_v = float(o or 0.0)
    i_v = float(i or 0.0)
    total = o_v + i_v
    if total <= 0:
        return None, None, None
    inflow = amount * (o_v / total)
    outflow = amount * (i_v / total)
    net = inflow - outflow
    return inflow, outflow, net


def resolve_trade_date_str(trade_date: Optional[str] = None) -> str:
    if trade_date:
        s = trade_date.strip().replace("/", "-")
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return s
    return datetime.now().strftime("%Y-%m-%d")


def trade_date_to_yyyymmdd(trade_date: str) -> str:
    s = trade_date.strip().replace("-", "").replace("/", "")
    if len(s) == 8 and s.isdigit():
        return s
    raise ValueError(f"无效交易日: {trade_date}")


def parse_fund_flow_filename_date(path: Path) -> Optional[str]:
    """从 hk_fund_flow_YYYYMMDD / YYYY-MM-DD 文件名解析交易日。"""
    stem = path.stem
    if not stem.startswith(FILE_PREFIX):
        return None
    suffix = stem[len(FILE_PREFIX) :]
    try:
        ymd = trade_date_to_yyyymmdd(suffix)
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
    except ValueError:
        return None


def find_hk_fund_flow_file(trade_date: str, data_dir: Optional[Path] = None) -> Optional[Path]:
    """按交易日查找 hk_fund_flow_YYYYMMDD / YYYY-MM-DD 文件。"""
    root = data_dir or DATA_DIR
    if not root.is_dir():
        return None
    ymd = trade_date_to_yyyymmdd(trade_date)
    hyphen = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
    candidates = []
    for stem in (f"{FILE_PREFIX}{ymd}", f"{FILE_PREFIX}{hyphen}"):
        for ext in SUPPORTED_EXTS:
            candidates.append(root / f"{stem}{ext}")
    for path in candidates:
        if path.is_file():
            return path
    return None


def find_latest_hk_fund_flow_file(data_dir: Optional[Path] = None) -> Optional[Path]:
    """目录中日期最新的 hk_fund_flow_* 文件。"""
    root = data_dir or DATA_DIR
    if not root.is_dir():
        return None
    dated: List[Tuple[str, Path]] = []
    for ext in SUPPORTED_EXTS:
        for path in root.glob(f"{FILE_PREFIX}*{ext}"):
            d = parse_fund_flow_filename_date(path)
            if d:
                dated.append((d, path))
    if not dated:
        return None
    dated.sort(key=lambda x: x[0], reverse=True)
    return dated[0][1]


def resolve_hk_fund_flow_file_for_realtime(
    trade_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    allow_latest: bool = False,
) -> Tuple[Optional[Path], Optional[str]]:
    """优先当日文件；默认不允许回退最新文件（实时补采须与交易日一致）。"""
    requested = resolve_trade_date_str(trade_date)
    exact = find_hk_fund_flow_file(requested, data_dir)
    if exact:
        return exact, requested
    if not allow_latest:
        return None, requested
    latest = find_latest_hk_fund_flow_file(data_dir)
    if latest is None:
        return None, requested
    file_date = parse_fund_flow_filename_date(latest) or requested
    return latest, file_date


class HkFundFlowFromFileCollector:
    """读取港股资金流向文件并 UPSERT 到 stock_fund_flow_daily_hk，再回写港股行情表。"""

    SOURCE = "file"

    def __init__(
        self,
        trade_date: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        self.trade_date = resolve_trade_date_str(trade_date)
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.logger = logger

    def find_file(self) -> Optional[Path]:
        return find_hk_fund_flow_file(self.trade_date, self.data_dir)

    def load_dataframe(self, file_path: Path) -> pd.DataFrame:
        """
        读取资金流向文件。同花顺常把 GBK/制表符文本另存为 .xls，需按内容探测。
        """
        from io import BytesIO, StringIO

        content = Path(file_path).read_bytes()
        if not content:
            raise RuntimeError(f"港股资金流向文件为空: {file_path}")

        suffix = file_path.suffix.lower()
        parse_errors: List[str] = []
        df: Optional[pd.DataFrame] = None

        def _ok(trial: Optional[pd.DataFrame]) -> bool:
            return trial is not None and not trial.empty and len(trial.columns) >= 2

        # 1) 真 CSV 后缀
        if suffix == ".csv":
            for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
                try:
                    trial = pd.read_csv(BytesIO(content), encoding=enc)
                    if _ok(trial):
                        df = trial
                        break
                except Exception as e:  # noqa: BLE001
                    parse_errors.append(f"csv({enc}): {e}")

        # 2) Excel 后缀：显式指定 engine
        if df is None and suffix in (".xlsx", ".xls"):
            engines = ("openpyxl", "xlrd") if suffix == ".xlsx" else ("xlrd", "openpyxl")
            for engine in engines:
                try:
                    trial = pd.read_excel(BytesIO(content), engine=engine)
                    if _ok(trial):
                        df = trial
                        break
                except Exception as e:  # noqa: BLE001
                    parse_errors.append(f"excel({engine}): {e}")

        # 3) 兜底：同花顺 .xls 实为 GBK/制表符文本
        if df is None:
            for enc in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
                try:
                    txt = content.decode(enc, errors="strict")
                    if "\t" in txt:
                        trial = pd.read_csv(StringIO(txt), sep="\t")
                    else:
                        trial = pd.read_csv(StringIO(txt), sep=None, engine="python")
                    if _ok(trial):
                        df = trial
                        self.logger.info(
                            "港股资金流向按文本解析成功 path=%s encoding=%s",
                            file_path.name,
                            enc,
                        )
                        break
                except Exception as e:  # noqa: BLE001
                    parse_errors.append(f"text({enc}): {e}")

        # 4) 兜底：HTML 表伪装成 xls
        if df is None:
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    tables = pd.read_html(BytesIO(content), encoding=enc)
                    if tables and _ok(tables[0]):
                        df = tables[0]
                        break
                except Exception as e:  # noqa: BLE001
                    parse_errors.append(f"html({enc}): {e}")

        if df is None or df.empty:
            detail = "; ".join(parse_errors[-6:]) if parse_errors else "未知原因"
            raise RuntimeError(f"港股资金流向文件解析失败: {file_path.name} ({detail})")
        return df

    def _column_map(self, df: pd.DataFrame) -> Dict[str, Any]:
        return {str(c).strip(): c for c in df.columns}

    def _col(self, col_map: Dict[str, Any], *names: str):
        for n in names:
            if n in col_map:
                return col_map[n]
        for n in names:
            n_norm = n.replace("%", "").replace("％", "").strip()
            for k, v in col_map.items():
                k_norm = k.replace("%", "").replace("％", "").strip()
                if k_norm == n_norm:
                    return v
        return None

    def dataframe_to_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        col_map = self._column_map(df)

        def col(*names: str):
            return self._col(col_map, *names)

        c_code = col("代码", "股票代码", "code")
        c_name = col("名称", "股票名称", "股票简称", "name")
        c_price = col("现价", "最新价", "current_price")
        c_chg = col("涨幅%", "涨幅", "涨跌幅", "change_percent")
        c_amt = col("金额", "成交额", "turnover_amount", "amount")
        c_outer = col("外盘", "outer_volume")
        c_inner = col("内盘", "inner_volume")
        c_tr = col("换手率", "turnover_rate")

        if c_code is None:
            raise RuntimeError(f"港股资金流向文件缺少代码列: {list(df.columns)}")
        if c_amt is None or c_outer is None or c_inner is None:
            raise RuntimeError(
                f"港股资金流向文件缺少金额/外盘/内盘列: {list(df.columns)}"
            )

        now = datetime.now()
        by_code: Dict[str, Dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = normalize_hk_fund_flow_code(row.get(c_code))
            if not code:
                continue
            if code in by_code:
                continue
            amount = parse_numeric(row.get(c_amt))
            outer = parse_numeric(row.get(c_outer))
            inner = parse_numeric(row.get(c_inner))
            inflow, outflow, net = compute_flow_from_outer_inner(amount, outer, inner)
            name_raw = row.get(c_name) if c_name else None
            name = None
            if name_raw is not None and not (isinstance(name_raw, float) and pd.isna(name_raw)):
                ns = str(name_raw).strip()
                if ns and ns not in ("-", "--"):
                    name = ns
            by_code[code] = {
                "code": code,
                "trade_date": self.trade_date,
                "name": name,
                "inflow_amount": inflow,
                "outflow_amount": outflow,
                "net_amount": net,
                "turnover_amount": amount,
                "change_percent": parse_percent(row.get(c_chg)) if c_chg else None,
                "turnover_rate": parse_percent(row.get(c_tr)) if c_tr else None,
                "current_price": parse_numeric(row.get(c_price)) if c_price else None,
                "outer_volume": outer,
                "inner_volume": inner,
                "source": self.SOURCE,
                "created_at": now,
                "updated_at": now,
            }
        return list(by_code.values())

    def dataframe_to_realtime_quote_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """同花顺资金流向表 → 港股实时行情行（总手按手入库）。"""
        col_map = self._column_map(df)
        c_code = self._col(col_map, "代码", "股票代码", "code")
        c_name = self._col(col_map, "名称", "股票名称", "股票简称", "name")
        c_price = self._col(col_map, "现价", "最新价", "current_price")
        c_chg = self._col(col_map, "涨幅%", "涨幅", "涨跌幅", "change_percent")
        c_chg_amt = self._col(col_map, "涨跌", "涨跌额", "change_amount")
        c_vol = self._col(col_map, "总手", "成交量", "volume")
        c_amt = self._col(col_map, "金额", "成交额", "turnover_amount", "amount")
        c_high = self._col(col_map, "最高", "high")
        c_low = self._col(col_map, "最低", "low")
        c_open = self._col(col_map, "开盘", "今开", "open")
        c_pre = self._col(col_map, "昨收", "昨收价", "pre_close")
        c_outer = self._col(col_map, "外盘", "outer_volume")
        c_inner = self._col(col_map, "内盘", "inner_volume")
        if c_code is None:
            raise RuntimeError(f"港股资金流向文件缺少代码列: {list(df.columns)}")

        now = datetime.now()
        now_s = now.strftime("%Y-%m-%d %H:%M:%S")
        by_code: Dict[str, Dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = normalize_hk_fund_flow_code(row.get(c_code) if c_code else None)
            if not code:
                continue
            if code in by_code:
                continue
            name_raw = row.get(c_name) if c_name else None
            name = None
            if name_raw is not None and not (isinstance(name_raw, float) and pd.isna(name_raw)):
                ns = str(name_raw).strip()
                if ns and ns not in ("-", "--"):
                    name = ns
            if name and "退" in name:
                continue
            price = parse_numeric(row.get(c_price)) if c_price else None
            if price is None or price <= 0:
                continue
            amount = parse_numeric(row.get(c_amt)) if c_amt else None
            outer = parse_numeric(row.get(c_outer)) if c_outer else None
            inner = parse_numeric(row.get(c_inner)) if c_inner else None
            inflow, outflow, net = compute_flow_from_outer_inner(amount, outer, inner)
            by_code[code] = {
                "code": code,
                "trade_date": self.trade_date,
                "name": name or code,
                "english_name": None,
                "current_price": price,
                "change_percent": parse_percent(row.get(c_chg)) if c_chg else None,
                "change_amount": parse_numeric(row.get(c_chg_amt)) if c_chg_amt else None,
                "volume": parse_numeric(row.get(c_vol)) if c_vol else None,
                "amount": amount,
                "high": parse_numeric(row.get(c_high)) if c_high else None,
                "low": parse_numeric(row.get(c_low)) if c_low else None,
                "open": parse_numeric(row.get(c_open)) if c_open else None,
                "pre_close": parse_numeric(row.get(c_pre)) if c_pre else None,
                "inflow_amount": inflow,
                "outflow_amount": outflow,
                "net_amount": net,
                "update_time": now_s,
            }
        return list(by_code.values())

    def upsert_realtime_quotes(self, rows: List[Dict[str, Any]], batch_size: int = 500) -> int:
        if not rows:
            return 0
        basic_sql = text(
            """
            INSERT INTO stock_basic_info_hk (code, name, create_date)
            VALUES (:code, :name, :create_date)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                create_date = EXCLUDED.create_date
            """
        )
        quote_sql = text(
            """
            INSERT INTO stock_realtime_quote_hk
            (code, trade_date, name, english_name, current_price, change_percent, change_amount,
             volume, amount, high, low, open, pre_close,
             inflow_amount, outflow_amount, net_amount, update_time)
            VALUES
            (:code, :trade_date, :name, :english_name, :current_price, :change_percent, :change_amount,
             :volume, :amount, :high, :low, :open, :pre_close,
             :inflow_amount, :outflow_amount, :net_amount, :update_time)
            ON CONFLICT (code, trade_date) DO UPDATE SET
                name = EXCLUDED.name,
                english_name = EXCLUDED.english_name,
                current_price = EXCLUDED.current_price,
                change_percent = EXCLUDED.change_percent,
                change_amount = EXCLUDED.change_amount,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                open = EXCLUDED.open,
                pre_close = EXCLUDED.pre_close,
                inflow_amount = EXCLUDED.inflow_amount,
                outflow_amount = EXCLUDED.outflow_amount,
                net_amount = EXCLUDED.net_amount,
                update_time = EXCLUDED.update_time
            """
        )
        session = SessionLocal()
        written = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                session.execute(
                    basic_sql,
                    [{"code": r["code"], "name": r["name"], "create_date": r["update_time"]} for r in chunk],
                )
                session.execute(quote_sql, chunk)
                session.commit()
                written += len(chunk)
            return written
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect_realtime_quotes(
        self,
        min_rows: int = HK_REALTIME_FILE_MIN_ROWS,
        allow_latest: bool = False,
    ) -> Dict[str, Any]:
        """接口不足量时的文件补丁：写入 stock_realtime_quote_hk / stock_basic_info_hk。

        默认仅使用当日 hk_fund_flow 文件；当日不存在则失败（按错误处理）。
        """
        path, file_date = resolve_hk_fund_flow_file_for_realtime(
            self.trade_date, self.data_dir, allow_latest=allow_latest
        )
        if path is None:
            ymd = trade_date_to_yyyymmdd(self.trade_date)
            if allow_latest:
                msg = (
                    f"未找到港股资金流向文件: {self.data_dir / (FILE_PREFIX + ymd)}.*"
                    f"（亦尝试目录内最新 hk_fund_flow_*）"
                )
            else:
                msg = (
                    f"未找到当日港股资金流向文件: {self.data_dir / (FILE_PREFIX + ymd)}.*"
                    f"（接口无数据且当日文件不存在，按错误处理）"
                )
            self.logger.error(msg)
            return {
                "success": False,
                "trade_date": self.trade_date,
                "error": msg,
                "written": 0,
                "fetched": 0,
            }
        if file_date and file_date != self.trade_date:
            self.logger.warning(
                "当日资金流向文件不存在，改用 %s（文件交易日 %s）",
                path.name,
                file_date,
            )
            self.trade_date = file_date
        df = self.load_dataframe(path)
        rows = self.dataframe_to_realtime_quote_rows(df)
        if len(rows) < min_rows:
            msg = (
                f"港股资金流向文件有效行情仅 {len(rows)} 条，少于最低要求 {min_rows} 条"
                f"（文件 {path.name}）"
            )
            self.logger.error(msg)
            return {
                "success": False,
                "trade_date": self.trade_date,
                "file": str(path),
                "error": msg,
                "written": 0,
                "fetched": len(df),
                "unique": len(rows),
            }
        written = self.upsert_realtime_quotes(rows)
        result = {
            "success": True,
            "trade_date": self.trade_date,
            "file": str(path),
            "fetched": len(df),
            "unique": len(rows),
            "written": written,
            "source": self.SOURCE,
        }
        self.logger.info(
            "港股实时行情文件补采完成 trade_date=%s file=%s fetched=%s unique=%s written=%s",
            self.trade_date,
            path.name,
            result["fetched"],
            result["unique"],
            written,
        )
        return result

    def upsert_rows(self, rows: List[Dict[str, Any]], batch_size: int = 500) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_fund_flow_daily_hk (
                code, trade_date, name, inflow_amount, outflow_amount, net_amount,
                turnover_amount, change_percent, turnover_rate, current_price,
                outer_volume, inner_volume, source, created_at, updated_at
            ) VALUES (
                :code, :trade_date, :name, :inflow_amount, :outflow_amount, :net_amount,
                :turnover_amount, :change_percent, :turnover_rate, :current_price,
                :outer_volume, :inner_volume, :source, :created_at, :updated_at
            )
            ON CONFLICT (code, trade_date) DO UPDATE SET
                name = EXCLUDED.name,
                inflow_amount = EXCLUDED.inflow_amount,
                outflow_amount = EXCLUDED.outflow_amount,
                net_amount = EXCLUDED.net_amount,
                turnover_amount = EXCLUDED.turnover_amount,
                change_percent = EXCLUDED.change_percent,
                turnover_rate = EXCLUDED.turnover_rate,
                current_price = EXCLUDED.current_price,
                outer_volume = EXCLUDED.outer_volume,
                inner_volume = EXCLUDED.inner_volume,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
            """
        )
        session = SessionLocal()
        written = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                session.execute(sql, chunk)
                session.commit()
                written += len(chunk)
            return written
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def sync_to_quote_tables(
        self, rows: List[Dict[str, Any]], batch_size: int = 500
    ) -> Dict[str, int]:
        """回写港股实时/历史行情三列；仅 UPDATE 已存在行。"""
        if not rows:
            return {"realtime_updated": 0, "historical_updated": 0}

        hist_sql = text(
            """
            UPDATE historical_quotes_hk
            SET inflow_amount = :inflow_amount,
                outflow_amount = :outflow_amount,
                net_amount = :net_amount
            WHERE code = :code AND date = :trade_date
            """
        )
        rt_sql = text(
            """
            UPDATE stock_realtime_quote_hk
            SET inflow_amount = :inflow_amount,
                outflow_amount = :outflow_amount,
                net_amount = :net_amount
            WHERE code = :code AND trade_date = :trade_date
            """
        )
        session = SessionLocal()
        hist_n = 0
        rt_n = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                params = [
                    {
                        "code": r["code"],
                        "trade_date": r["trade_date"],
                        "inflow_amount": r.get("inflow_amount"),
                        "outflow_amount": r.get("outflow_amount"),
                        "net_amount": r.get("net_amount"),
                    }
                    for r in chunk
                ]
                for p in params:
                    rh = session.execute(hist_sql, p)
                    hist_n += rh.rowcount or 0
                    rr = session.execute(rt_sql, p)
                    rt_n += rr.rowcount or 0
                session.commit()
            return {"realtime_updated": rt_n, "historical_updated": hist_n}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect(self) -> Dict[str, Any]:
        file_path = self.find_file()
        if file_path is None:
            ymd = trade_date_to_yyyymmdd(self.trade_date)
            msg = (
                f"未找到港股资金流向文件: {self.data_dir / (FILE_PREFIX + ymd)}.*"
                f"（亦尝试 YYYY-MM-DD 后缀）"
            )
            self.logger.error(msg)
            return {
                "success": False,
                "trade_date": self.trade_date,
                "error": msg,
                "written": 0,
            }
        df = self.load_dataframe(file_path)
        rows = self.dataframe_to_rows(df)
        written = self.upsert_rows(rows)
        synced = self.sync_to_quote_tables(rows)
        result = {
            "success": True,
            "trade_date": self.trade_date,
            "file": str(file_path),
            "fetched": len(df),
            "unique": len(rows),
            "written": written,
            "realtime_updated": synced["realtime_updated"],
            "historical_updated": synced["historical_updated"],
            "source": self.SOURCE,
        }
        self.logger.info(
            "港股资金流向文件采集完成 trade_date=%s file=%s fetched=%s unique=%s "
            "written=%s hist=%s realtime=%s",
            self.trade_date,
            file_path.name,
            result["fetched"],
            result["unique"],
            written,
            synced["historical_updated"],
            synced["realtime_updated"],
        )
        return result


def collect_hk_fund_flow_from_file(
    trade_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    return HkFundFlowFromFileCollector(trade_date=trade_date, data_dir=data_dir).collect()


def collect_hk_realtime_quotes_from_file(
    trade_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    min_rows: int = HK_REALTIME_FILE_MIN_ROWS,
    allow_latest: bool = False,
) -> Dict[str, Any]:
    """港股实时采集接口不足量时，从当日 hk_fund_flow_YYYYMMDD 文件补写入库。

    默认 allow_latest=False：当日文件不存在则返回 success=False（由调用方按错误处理）。
    """
    return HkFundFlowFromFileCollector(trade_date=trade_date, data_dir=data_dir).collect_realtime_quotes(
        min_rows=min_rows,
        allow_latest=allow_latest,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(collect_hk_fund_flow_from_file())
