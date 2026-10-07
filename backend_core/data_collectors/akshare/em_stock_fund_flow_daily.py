# -*- coding: utf-8 -*-
"""东财个股资金流日采：ak.stock_individual_fund_flow → stock_fund_flow_em_daily。"""

from __future__ import annotations

import io
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO stock_fund_flow_em_daily (
    code, trade_date,
    main_net_inflow, main_net_inflow_pct,
    super_large_net_inflow, super_large_net_inflow_pct,
    large_net_inflow, large_net_inflow_pct,
    mid_net_inflow, mid_net_inflow_pct,
    small_net_inflow, small_net_inflow_pct,
    close_price, change_percent, source, created_at, updated_at
) VALUES (
    :code, :trade_date,
    :main_net_inflow, :main_net_inflow_pct,
    :super_large_net_inflow, :super_large_net_inflow_pct,
    :large_net_inflow, :large_net_inflow_pct,
    :mid_net_inflow, :mid_net_inflow_pct,
    :small_net_inflow, :small_net_inflow_pct,
    :close_price, :change_percent, :source, :created_at, :updated_at
)
ON CONFLICT (code, trade_date) DO UPDATE SET
    main_net_inflow = EXCLUDED.main_net_inflow,
    main_net_inflow_pct = EXCLUDED.main_net_inflow_pct,
    super_large_net_inflow = EXCLUDED.super_large_net_inflow,
    super_large_net_inflow_pct = EXCLUDED.super_large_net_inflow_pct,
    large_net_inflow = EXCLUDED.large_net_inflow,
    large_net_inflow_pct = EXCLUDED.large_net_inflow_pct,
    mid_net_inflow = EXCLUDED.mid_net_inflow,
    mid_net_inflow_pct = EXCLUDED.mid_net_inflow_pct,
    small_net_inflow = EXCLUDED.small_net_inflow,
    small_net_inflow_pct = EXCLUDED.small_net_inflow_pct,
    close_price = EXCLUDED.close_price,
    change_percent = EXCLUDED.change_percent,
    source = EXCLUDED.source,
    updated_at = EXCLUDED.updated_at
"""


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def normalize_code(val: Any) -> Optional[str]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s:
        return None
    if s.endswith(".0") and s.replace(".", "", 1).isdigit():
        s = s[:-2]
    low = s.lower()
    for prefix in ("sh", "sz", "bj"):
        if low.startswith(prefix) and low[len(prefix) :].isdigit():
            return low[len(prefix) :].zfill(6)
    if s.isdigit():
        return s.zfill(6)
    return s


def infer_markets(code: str) -> List[str]:
    """按代码猜测东财 market 尝试顺序。"""
    c = normalize_code(code) or ""
    if c.startswith(("5", "6", "9")):
        return ["sh", "sz", "bj"]
    if c.startswith(("4", "8")):
        return ["bj", "sz", "sh"]
    return ["sz", "sh", "bj"]


def safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    s = str(val).strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "--", "None", "nan", "NaN"):
        return None
    # 东财偶发「亿」单位
    unit = 1.0
    if s.endswith("亿"):
        unit = 1e8
        s = s[:-1]
    elif s.endswith("万"):
        unit = 1e4
        s = s[:-1]
    try:
        return float(s) * unit
    except ValueError:
        return None


def _col(row: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    # 兼容列名空格差异
    for k, v in row.items():
        ks = str(k).strip()
        if ks in names:
            return v
    return None


def parse_em_row(code: str, row: Dict[str, Any], *, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    trade_date = _col(row, "date", "日期")
    if trade_date is None:
        return None
    td = str(trade_date).strip()[:10]
    if len(td) == 8 and td.isdigit():
        td = f"{td[:4]}-{td[4:6]}-{td[6:8]}"
    if len(td) < 10:
        return None
    ts = now or datetime.now()
    return {
        "code": code,
        "trade_date": td,
        "main_net_inflow": safe_float(_col(row, "主力净流入-净额", "主力净流入", "main_net_inflow")),
        "main_net_inflow_pct": safe_float(
            _col(row, "主力净流入-净占比", "main_net_inflow_pct")
        ),
        "super_large_net_inflow": safe_float(
            _col(row, "超大单净流入-净额", "超大单净流入", "super_large_net_inflow")
        ),
        "super_large_net_inflow_pct": safe_float(
            _col(row, "超大单净流入-净占比", "super_large_net_inflow_pct")
        ),
        "large_net_inflow": safe_float(
            _col(row, "大单净流入-净额", "大单净流入", "large_net_inflow")
        ),
        "large_net_inflow_pct": safe_float(
            _col(row, "大单净流入-净占比", "large_net_inflow_pct")
        ),
        "mid_net_inflow": safe_float(
            _col(row, "中单净流入-净额", "中单净流入", "mid_net_inflow")
        ),
        "mid_net_inflow_pct": safe_float(
            _col(row, "中单净流入-净占比", "mid_net_inflow_pct")
        ),
        "small_net_inflow": safe_float(
            _col(row, "小单净流入-净额", "小单净流入", "small_net_inflow")
        ),
        "small_net_inflow_pct": safe_float(
            _col(row, "小单净流入-净占比", "small_net_inflow_pct")
        ),
        "close_price": safe_float(_col(row, "收盘价", "最新价", "close_price")),
        "change_percent": safe_float(_col(row, "涨跌幅", "change_percent")),
        "source": "em",
        "created_at": ts,
        "updated_at": ts,
    }


def fetch_em_fund_flow_df(code: str) -> Optional[pd.DataFrame]:
    """拉取单票东财资金流历史；按 market 探测。"""
    code_n = normalize_code(code)
    if not code_n:
        return None
    last_err: Optional[Exception] = None
    for market in infer_markets(code_n):
        try:
            df = ak.stock_individual_fund_flow(stock=code_n, market=market)
            if df is not None and not df.empty:
                return df
        except Exception as ex:
            last_err = ex
            logger.debug("em fund flow %s market=%s fail: %s", code_n, market, ex)
    if last_err:
        logger.warning("em fund flow %s all markets failed: %s", code_n, last_err)
    return None


def rows_from_df(
    code: str,
    df: pd.DataFrame,
    *,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    code_n = normalize_code(code) or code
    now = datetime.now()
    out: List[Dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = parse_em_row(code_n, raw, now=now)
        if not row:
            continue
        td = row["trade_date"]
        if min_date and td < min_date:
            continue
        if max_date and td > max_date:
            continue
        out.append(row)
    out.sort(key=lambda r: r["trade_date"])
    return out


def upsert_rows(session, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    # SQLite 兼容：无 ON CONFLICT 时走逐条；生产为 PostgreSQL
    bind = session.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    if dialect == "postgresql":
        session.execute(text(UPSERT_SQL), list(rows))
        return len(rows)
    # 非 PG：逐条 replace
    n = 0
    for r in rows:
        session.execute(
            text(
                """
                DELETE FROM stock_fund_flow_em_daily
                WHERE code = :code AND trade_date = :trade_date
                """
            ),
            {"code": r["code"], "trade_date": r["trade_date"]},
        )
        session.execute(
            text(
                """
                INSERT INTO stock_fund_flow_em_daily (
                    code, trade_date,
                    main_net_inflow, main_net_inflow_pct,
                    super_large_net_inflow, super_large_net_inflow_pct,
                    large_net_inflow, large_net_inflow_pct,
                    mid_net_inflow, mid_net_inflow_pct,
                    small_net_inflow, small_net_inflow_pct,
                    close_price, change_percent, source, created_at, updated_at
                ) VALUES (
                    :code, :trade_date,
                    :main_net_inflow, :main_net_inflow_pct,
                    :super_large_net_inflow, :super_large_net_inflow_pct,
                    :large_net_inflow, :large_net_inflow_pct,
                    :mid_net_inflow, :mid_net_inflow_pct,
                    :small_net_inflow, :small_net_inflow_pct,
                    :close_price, :change_percent, :source, :created_at, :updated_at
                )
                """
            ),
            r,
        )
        n += 1
    return n


def list_active_codes(session, *, limit: Optional[int] = None) -> List[str]:
    sql = """
        SELECT code FROM stock_basic_info
        WHERE COALESCE(collect_enabled, TRUE) = TRUE
        ORDER BY code
    """
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    rows = session.execute(text(sql)).fetchall()
    return [normalize_code(r[0]) for r in rows if normalize_code(r[0])]


def collect_em_stock_fund_flow_for_code(
    code: str,
    *,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    keep_last_n: Optional[int] = None,
    sleep_sec: float = 0.0,
) -> Dict[str, Any]:
    """采集并落库单票；返回统计。"""
    code_n = normalize_code(code)
    if not code_n:
        return {"success": False, "code": code, "error": "invalid code", "upserted": 0}
    df = fetch_em_fund_flow_df(code_n)
    if sleep_sec > 0:
        time.sleep(sleep_sec)
    if df is None or df.empty:
        return {"success": False, "code": code_n, "error": "no data", "upserted": 0}
    rows = rows_from_df(code_n, df, min_date=min_date, max_date=max_date)
    if keep_last_n and keep_last_n > 0 and len(rows) > keep_last_n:
        rows = rows[-int(keep_last_n) :]
    session = SessionLocal()
    try:
        n = upsert_rows(session, rows)
        session.commit()
        return {
            "success": True,
            "code": code_n,
            "upserted": n,
            "first_date": rows[0]["trade_date"] if rows else None,
            "last_date": rows[-1]["trade_date"] if rows else None,
        }
    except Exception as e:
        session.rollback()
        logger.exception("em fund flow upsert failed code=%s", code_n)
        return {"success": False, "code": code_n, "error": str(e), "upserted": 0}
    finally:
        session.close()


def collect_em_stock_fund_flow_daily(
    *,
    codes: Optional[Sequence[str]] = None,
    trade_date: Optional[str] = None,
    recent_days: Optional[int] = None,
    sleep_sec: Optional[float] = None,
    max_codes: Optional[int] = None,
    progress_every: int = 50,
) -> Dict[str, Any]:
    """
    批量采集东财个股资金流。

    - codes 为空：取 stock_basic_info.collect_enabled 活跃池
    - trade_date：若指定，仅 upsert 该日（仍拉取全序列后过滤）
    - recent_days：仅保留序列末尾 N 个交易日（日更用，默认环境变量或 5）
    """
    sleep = (
        float(sleep_sec)
        if sleep_sec is not None
        else _env_float("EM_FUND_FLOW_SLEEP_SEC", 0.35)
    )
    lim = max_codes if max_codes is not None else _env_int("EM_FUND_FLOW_MAX_CODES", 0)
    if lim <= 0:
        lim = None

    rd = recent_days
    if rd is None and not trade_date:
        rd = _env_int("EM_FUND_FLOW_RECENT_DAYS", 5)

    session = SessionLocal()
    try:
        if codes:
            code_list = [normalize_code(c) for c in codes]
            code_list = [c for c in code_list if c]
        else:
            code_list = list_active_codes(session, limit=lim)
        if lim and codes:
            code_list = code_list[: int(lim)]
    finally:
        session.close()

    ok = 0
    fail = 0
    upserted = 0
    errors: List[str] = []
    min_date = trade_date
    max_date = trade_date
    keep_last_n = None if trade_date else rd

    for i, code in enumerate(code_list, 1):
        res = collect_em_stock_fund_flow_for_code(
            code,
            min_date=min_date,
            max_date=max_date,
            keep_last_n=keep_last_n,
            sleep_sec=0.0,
        )
        if res.get("success"):
            ok += 1
            upserted += int(res.get("upserted") or 0)
        else:
            fail += 1
            err = res.get("error") or "fail"
            if len(errors) < 20:
                errors.append(f"{code}:{err}")
        if sleep > 0:
            time.sleep(sleep)
        if progress_every and i % progress_every == 0:
            logger.info(
                "em fund flow progress %s/%s ok=%s fail=%s upserted=%s",
                i,
                len(code_list),
                ok,
                fail,
                upserted,
            )

    return {
        "success": True,
        "codes_total": len(code_list),
        "ok": ok,
        "fail": fail,
        "upserted": upserted,
        "trade_date": trade_date,
        "recent_days": keep_last_n,
        "sleep_sec": sleep,
        "errors_sample": errors,
    }


IMPORT_TEMPLATE_CSV = (
    "日期,主力净流入-净额,主力净流入-净占比,超大单净流入-净额,超大单净流入-净占比,"
    "大单净流入-净额,大单净流入-净占比,中单净流入-净额,中单净流入-净占比,"
    "小单净流入-净额,小单净流入-净占比,收盘价,涨跌幅\n"
    "2026-09-08,12345678,3.2,8000000,2.1,4345678,1.1,-1000000,-0.3,-2000000,-0.5,12.34,1.2\n"
)

_AMOUNT_FIELDS = (
    "main_net_inflow",
    "super_large_net_inflow",
    "large_net_inflow",
    "mid_net_inflow",
    "small_net_inflow",
)


def apply_amount_unit(row: Dict[str, Any], unit: str) -> Dict[str, Any]:
    u = (unit or "yuan").strip().lower()
    factor = {"yuan": 1.0, "wan": 1e4, "yi": 1e8}.get(u, 1.0)
    if factor == 1.0:
        return row
    out = dict(row)
    for k in _AMOUNT_FIELDS:
        if out.get(k) is not None:
            out[k] = float(out[k]) * factor
    return out


def _decode_bytes(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def parse_import_table(
    code: str,
    raw: str,
    *,
    amount_unit: str = "auto",
    filename: str = "",
) -> List[Dict[str, Any]]:
    """解析 CSV / TSV / JSON。Tushare moneyflow 列自动换算万元→元。"""
    import csv
    import io
    import json

    text = (raw or "").lstrip("\ufeff").strip()
    if not text:
        return []
    lines = [
        ln
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    text = "\n".join(lines).strip()
    if not text:
        return []
    code_n = normalize_code(code) or code
    unit = (amount_unit or "auto").strip().lower()
    records: List[Dict[str, Any]] = []
    if text.startswith("[") or text.startswith("{"):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("rows") or data.get("data") or data.get("items") or [data]
        records = [dict(x) for x in data if isinstance(x, dict)]
    else:
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        records = [dict(r) for r in reader]

    if not records:
        return []
    cols = list(records[0].keys())
    from backend_core.data_collectors.tushare.moneyflow import (
        looks_like_moneyflow_columns,
        moneyflow_record_to_em_row,
    )

    now = datetime.now()
    out: List[Dict[str, Any]] = []
    if looks_like_moneyflow_columns(cols):
        for rec in records:
            row = moneyflow_record_to_em_row(rec, code=code_n, now=now)
            if row:
                row["source"] = "manual"
                out.append(row)
        out.sort(key=lambda r: r["trade_date"])
        return out

    scale = unit if unit in ("yuan", "wan", "yi") else "yuan"
    for rec in records:
        row = parse_em_row(code_n, rec, now=now)
        if not row:
            continue
        row = apply_amount_unit(row, scale)
        row["source"] = "manual"
        out.append(row)
    out.sort(key=lambda r: r["trade_date"])
    return out


def parse_import_bytes(
    code: str,
    content: bytes,
    *,
    filename: str = "",
    amount_unit: str = "auto",
) -> List[Dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
        text = df.to_csv(index=False)
        return parse_import_table(
            code, text, amount_unit=amount_unit, filename=filename
        )
    return parse_import_table(
        code, _decode_bytes(content), amount_unit=amount_unit, filename=filename
    )
