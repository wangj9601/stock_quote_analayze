# -*- coding: utf-8 -*-
"""Tushare 个股资金流向 moneyflow → stock_fund_flow_em_daily。

接口：https://tushare.pro/document/2?doc_id=170
金额单位：万元 → 入库统一为元。
主力净流入 ≈ 特大单净额 + 大单净额（对齐东财「主力」口径，非账户身份）。
Tushare 注明净流入基于主动买卖，不能简单把各档加总当总净流入。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from backend_core.config.config import TUSHARE_CONFIG
from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    normalize_code,
    safe_float,
    upsert_rows,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

WAN = 1e4
MONEYFLOW_FIELDS = (
    "ts_code,trade_date,"
    "buy_sm_vol,buy_sm_amount,sell_sm_vol,sell_sm_amount,"
    "buy_md_vol,buy_md_amount,sell_md_vol,sell_md_amount,"
    "buy_lg_vol,buy_lg_amount,sell_lg_vol,sell_lg_amount,"
    "buy_elg_vol,buy_elg_amount,sell_elg_vol,sell_elg_amount,"
    "net_mf_vol,net_mf_amount"
)


def code_to_ts_code(code: str) -> str:
    c = (normalize_code(code) or str(code).strip()).zfill(6)
    if c.startswith("6"):
        return f"{c}.SH"
    if c.startswith(("4", "8")):
        return f"{c}.BJ"
    return f"{c}.SZ"


def looks_like_moneyflow_columns(cols: Sequence[str]) -> bool:
    names = {str(c).strip().lower() for c in cols}
    return "buy_elg_amount" in names or "buy_lg_amount" in names


def _net_yuan(buy: Any, sell: Any) -> Optional[float]:
    b = safe_float(buy)
    s = safe_float(sell)
    if b is None and s is None:
        return None
    return ((b or 0.0) - (s or 0.0)) * WAN


def _pct(buy: Any, sell: Any) -> Optional[float]:
    b = safe_float(buy)
    s = safe_float(sell)
    tot = (b or 0.0) + (s or 0.0)
    if tot <= 0:
        return None
    return ((b or 0.0) - (s or 0.0)) / tot * 100.0


def _trade_date(val: Any) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10:
        return s[:10]
    return None


def moneyflow_record_to_em_row(
    row: Dict[str, Any],
    *,
    code: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """将 Tushare moneyflow 一行映射为 em 日表字段（金额已换算为元）。"""
    td = _trade_date(row.get("trade_date") or row.get("日期"))
    if not td:
        return None
    ts_code = str(row.get("ts_code") or "").strip()
    code_n = normalize_code(code) or (
        normalize_code(ts_code.split(".")[0]) if ts_code else None
    )
    if not code_n:
        return None

    elg = _net_yuan(row.get("buy_elg_amount"), row.get("sell_elg_amount"))
    lg = _net_yuan(row.get("buy_lg_amount"), row.get("sell_lg_amount"))
    md = _net_yuan(row.get("buy_md_amount"), row.get("sell_md_amount"))
    sm = _net_yuan(row.get("buy_sm_amount"), row.get("sell_sm_amount"))
    main = None
    if elg is not None or lg is not None:
        main = (elg or 0.0) + (lg or 0.0)

    elg_buy = safe_float(row.get("buy_elg_amount"))
    elg_sell = safe_float(row.get("sell_elg_amount"))
    lg_buy = safe_float(row.get("buy_lg_amount"))
    lg_sell = safe_float(row.get("sell_lg_amount"))
    main_tot = (elg_buy or 0.0) + (elg_sell or 0.0) + (lg_buy or 0.0) + (lg_sell or 0.0)
    main_pct = None
    if main is not None and main_tot > 0:
        main_pct = (main / WAN) / main_tot * 100.0

    ts = now or datetime.now()
    return {
        "code": code_n,
        "trade_date": td,
        "main_net_inflow": main,
        "main_net_inflow_pct": main_pct,
        "super_large_net_inflow": elg,
        "super_large_net_inflow_pct": _pct(
            row.get("buy_elg_amount"), row.get("sell_elg_amount")
        ),
        "large_net_inflow": lg,
        "large_net_inflow_pct": _pct(row.get("buy_lg_amount"), row.get("sell_lg_amount")),
        "mid_net_inflow": md,
        "mid_net_inflow_pct": _pct(row.get("buy_md_amount"), row.get("sell_md_amount")),
        "small_net_inflow": sm,
        "small_net_inflow_pct": _pct(row.get("buy_sm_amount"), row.get("sell_sm_amount")),
        "close_price": None,
        "change_percent": None,
        "source": "tushare",
        "created_at": ts,
        "updated_at": ts,
    }


def rows_from_moneyflow_df(
    df: pd.DataFrame,
    *,
    code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    now = datetime.now()
    out: List[Dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = moneyflow_record_to_em_row(raw, code=code, now=now)
        if row:
            out.append(row)
    out.sort(key=lambda r: (r["code"], r["trade_date"]))
    return out


def _tushare_token() -> str:
    return (
        (TUSHARE_CONFIG.get("token") or "").strip()
        or (os.getenv("TUSHARE_TOKEN") or "").strip()
    )


def _pro_api():
    token = _tushare_token()
    if not token:
        raise RuntimeError("未配置 TUSHARE_TOKEN，无法调用 Tushare moneyflow")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def fetch_moneyflow_df(
    *,
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """trade_date / start_date / end_date 使用 YYYYMMDD。"""
    pro = _pro_api()
    kwargs: Dict[str, Any] = {"fields": MONEYFLOW_FIELDS}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date.replace("-", "")[:8]
    if start_date:
        kwargs["start_date"] = start_date.replace("-", "")[:8]
    if end_date:
        kwargs["end_date"] = end_date.replace("-", "")[:8]
    df = pro.moneyflow(**kwargs)
    if df is None or df.empty:
        return None
    return df


def collect_tushare_moneyflow_for_code(
    code: str,
    *,
    days: int = 120,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    code_n = normalize_code(code)
    if not code_n:
        return {"success": False, "code": code, "error": "invalid code", "upserted": 0}
    days_n = max(5, min(int(days or 120), 250))
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        cal = datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(
            days=max(int(days_n * 1.8), days_n + 20)
        )
        start_date = cal.strftime("%Y-%m-%d")
    try:
        df = fetch_moneyflow_df(
            ts_code=code_to_ts_code(code_n),
            start_date=start_date,
            end_date=end,
        )
    except Exception as e:
        logger.warning("tushare moneyflow %s fail: %s", code_n, e)
        return {"success": False, "code": code_n, "error": str(e), "upserted": 0}
    if df is None or df.empty:
        return {"success": False, "code": code_n, "error": "no data", "upserted": 0}
    rows = rows_from_moneyflow_df(df, code=code_n)
    if days_n and len(rows) > days_n:
        rows = rows[-days_n:]
    session = SessionLocal()
    try:
        n = upsert_rows(session, rows)
        session.commit()
        return {
            "success": True,
            "code": code_n,
            "source": "tushare",
            "upserted": n,
            "first_date": rows[0]["trade_date"] if rows else None,
            "last_date": rows[-1]["trade_date"] if rows else None,
        }
    except Exception as e:
        session.rollback()
        logger.exception("tushare moneyflow upsert failed code=%s", code_n)
        return {"success": False, "code": code_n, "error": str(e), "upserted": 0}
    finally:
        session.close()


def collect_tushare_moneyflow_for_date(trade_date: str) -> Dict[str, Any]:
    """全市场单日：一次 moneyflow(trade_date=) 调用。"""
    td = (trade_date or "").replace("-", "")[:8]
    if len(td) != 8:
        return {"success": False, "error": "trade_date 格式应为 YYYY-MM-DD", "upserted": 0}
    try:
        df = fetch_moneyflow_df(trade_date=td)
    except Exception as e:
        logger.warning("tushare moneyflow date=%s fail: %s", td, e)
        return {"success": False, "error": str(e), "upserted": 0, "trade_date": trade_date}
    if df is None or df.empty:
        return {
            "success": False,
            "error": "no data",
            "upserted": 0,
            "trade_date": f"{td[:4]}-{td[4:6]}-{td[6:8]}",
        }
    rows = rows_from_moneyflow_df(df)
    session = SessionLocal()
    try:
        n = upsert_rows(session, rows)
        session.commit()
        return {
            "success": True,
            "source": "tushare",
            "upserted": n,
            "codes": len({r["code"] for r in rows}),
            "trade_date": f"{td[:4]}-{td[4:6]}-{td[6:8]}",
        }
    except Exception as e:
        session.rollback()
        logger.exception("tushare moneyflow upsert failed date=%s", td)
        return {"success": False, "error": str(e), "upserted": 0}
    finally:
        session.close()


def collect_main_force_for_code(
    code: str,
    *,
    source: str = "auto",
    days: int = 120,
) -> Dict[str, Any]:
    """source=auto：先东财，失败再 Tushare moneyflow。"""
    src = (source or "auto").strip().lower()
    if src not in ("auto", "em", "tushare"):
        return {"success": False, "error": "source 应为 auto / em / tushare", "upserted": 0}

    em_err = None
    if src in ("auto", "em"):
        from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
            collect_em_stock_fund_flow_for_code,
        )

        res = collect_em_stock_fund_flow_for_code(code, keep_last_n=days)
        if res.get("success") and int(res.get("upserted") or 0) > 0:
            res["source"] = "em"
            return res
        em_err = res.get("error") or "eastmoney empty"
        if src == "em":
            return res

    ts_res = collect_tushare_moneyflow_for_code(code, days=days)
    if em_err:
        ts_res["eastmoney_error"] = em_err
    if src == "auto" and ts_res.get("success"):
        ts_res["fallback"] = "tushare"
    return ts_res
