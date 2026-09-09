# -*- coding: utf-8 -*-
"""港股资金流向文件采集：hk_fund_flow_YYYYMMDD → stock_fund_flow_daily_hk。

口径（1A）：流入 = 外盘/(外盘+内盘)×金额，流出 = 内盘/(外盘+内盘)×金额，净额 = 流入−流出。
外盘+内盘为 0 或无效时，流入/流出/净额置空。
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

    def dataframe_to_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        col_map = {str(c).strip(): c for c in df.columns}

        def col(*names: str):
            for n in names:
                if n in col_map:
                    return col_map[n]
            # 宽松：去掉 % 再匹配
            for n in names:
                for k, v in col_map.items():
                    if k.replace("%", "").replace("％", "").strip() == n.replace("%", "").strip():
                        return v
            return None

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(collect_hk_fund_flow_from_file())
