# -*- coding: utf-8 -*-
"""AkShare 沪/深交易所融资融券明细 → stock_margin_daily（补洞备源）。

- stock_margin_detail_sse(date)
- stock_margin_detail_szse(date)

date 参数：YYYYMMDD 或 YYYY-MM-DD（内部规范化）。
不覆盖已有 source=tushare 的行（fill_only / upsert 策略）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd

from backend_core.data_collectors.tushare.margin import (
    rows_from_margin_df,
    upsert_margin_rows,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)


def _norm_date_param(trade_date: str) -> Optional[str]:
    """返回 YYYYMMDD。"""
    s = (trade_date or "").strip().replace("-", "")[:8]
    if len(s) != 8 or not s.isdigit():
        return None
    return s


def _fmt_ymd(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _normalize_sse_df(df: pd.DataFrame, trade_date_ymd: str) -> pd.DataFrame:
    """统一列名，便于 margin_record_to_row。"""
    if df is None or df.empty:
        return df
    rename = {
        "信用交易日期": "trade_date",
        "标的证券代码": "code",
        "标的证券简称": "name",
        "融资余额": "rzye",
        "融资买入额": "rzmre",
        "融资偿还额": "rzche",
        "融券余量": "rqyl",
        "融券卖出量": "rqmcl",
        "融券偿还量": "rqchl",
        "融券余额": "rqye",
        "融资融券余额": "rzrqye",
    }
    out = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "trade_date" not in out.columns:
        out["trade_date"] = trade_date_ymd
    return out


def _normalize_szse_df(df: pd.DataFrame, trade_date_ymd: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    rename = {
        "证券代码": "code",
        "证券简称": "name",
        "融资余额": "rzye",
        "融资买入额": "rzmre",
        "融资偿还额": "rzche",
        "融券余额": "rqye",
        "融券余量": "rqyl",
        "融券卖出量": "rqmcl",
        "融券偿还量": "rqchl",
        "融资融券余额": "rzrqye",
    }
    out = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    out["trade_date"] = trade_date_ymd
    return out


def fetch_sse_margin_df(trade_date: str) -> Optional[pd.DataFrame]:
    ymd = _norm_date_param(trade_date)
    if not ymd:
        return None
    try:
        df = ak.stock_margin_detail_sse(date=ymd)
    except Exception as e:
        logger.warning("akshare sse margin %s fail: %s", ymd, e)
        return None
    if df is None or df.empty:
        return None
    return _normalize_sse_df(df, _fmt_ymd(ymd))


def fetch_szse_margin_df(trade_date: str) -> Optional[pd.DataFrame]:
    ymd = _norm_date_param(trade_date)
    if not ymd:
        return None
    # 深交所接口部分版本接受 YYYY-MM-DD
    for date_arg in (ymd, _fmt_ymd(ymd)):
        try:
            df = ak.stock_margin_detail_szse(date=date_arg)
            if df is not None and not df.empty:
                return _normalize_szse_df(df, _fmt_ymd(ymd))
        except Exception as e:
            logger.debug("akshare szse margin %s fail: %s", date_arg, e)
    logger.warning("akshare szse margin %s empty/fail", ymd)
    return None


def collect_akshare_margin_for_date(
    trade_date: str,
    *,
    fill_only: bool = True,
) -> Dict[str, Any]:
    """拉取沪+深明细并 upsert。fill_only 时不覆盖已有行（含 tushare）。"""
    ymd = _norm_date_param(trade_date)
    if not ymd:
        return {"success": False, "error": "trade_date 格式应为 YYYY-MM-DD", "upserted": 0}
    td_fmt = _fmt_ymd(ymd)
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    sse = fetch_sse_margin_df(ymd)
    if sse is not None and not sse.empty:
        rows.extend(rows_from_margin_df(sse, source="akshare_sse"))
    else:
        errors.append("sse empty")

    szse = fetch_szse_margin_df(ymd)
    if szse is not None and not szse.empty:
        rows.extend(rows_from_margin_df(szse, source="akshare_szse"))
    else:
        errors.append("szse empty")

    if not rows:
        return {
            "success": False,
            "error": "; ".join(errors) or "no data",
            "upserted": 0,
            "trade_date": td_fmt,
            "source": "akshare",
        }

    # 同 code 去重：优先保留已有字段更全的行（简单按出现顺序，深市后写可覆盖沪市同码极少）
    by_code: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        c = r["code"]
        prev = by_code.get(c)
        if prev is None:
            by_code[c] = r
            continue
        # 合并非空字段
        merged = dict(prev)
        for k, v in r.items():
            if v is not None and k not in ("created_at",):
                if merged.get(k) is None or k == "source":
                    merged[k] = v
        # 跨市场同码极罕见；保留后出现的 source 标记为 akshare
        if prev.get("source") != r.get("source"):
            merged["source"] = "akshare"
        by_code[c] = merged
    merged_rows = list(by_code.values())

    session = SessionLocal()
    try:
        n = upsert_margin_rows(session, merged_rows, fill_only=fill_only)
        session.commit()
        return {
            "success": True,
            "source": "akshare",
            "upserted": n,
            "codes": len(merged_rows),
            "trade_date": td_fmt,
            "sse_rows": len(sse) if sse is not None else 0,
            "szse_rows": len(szse) if szse is not None else 0,
            "errors": errors or None,
        }
    except Exception as e:
        session.rollback()
        logger.exception("akshare margin upsert failed date=%s", td_fmt)
        return {
            "success": False,
            "error": str(e),
            "upserted": 0,
            "trade_date": td_fmt,
            "source": "akshare",
        }
    finally:
        session.close()
