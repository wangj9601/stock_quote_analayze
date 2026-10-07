# -*- coding: utf-8 -*-
"""Tushare 个股主力/分档资金流 → stock_fund_flow_em_daily。

支持：
- moneyflow_dc：东财口径（字段与现表一致），source=tushare_dc
- moneyflow：L2 主动买卖分档，主力净额=特大+大单买卖差，source=tushare_l2

金额：Tushare 接口多为「万元」，入库统一换算为「元」。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from sqlalchemy import text

from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    list_active_codes,
    normalize_code,
    upsert_rows,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

SOURCE_DC = "tushare_dc"
SOURCE_L2 = "tushare_l2"


def resolve_tushare_pro():
    """从环境变量 / 配置解析 pro_api；失败返回 None。"""
    token = (
        (os.getenv("TUSHARE_TOKEN") or "").strip()
        or str(
            (
                __import__(
                    "backend_core.config.config", fromlist=["TUSHARE_CONFIG"]
                ).TUSHARE_CONFIG
                or {}
            ).get("token")
            or ""
        ).strip()
    )
    try:
        import tushare as ts

        if token:
            return ts.pro_api(token)
        # 兼容已通过 ts.set_token 设置的全局 token
        return ts.pro_api()
    except Exception as e:
        logger.error("初始化 Tushare pro_api 失败: %s", e)
        return None


def code_to_ts_code(code: str) -> Optional[str]:
    c = normalize_code(code)
    if not c or not c.isdigit() or len(c) != 6:
        return None
    if c.startswith(("5", "6", "9")):
        return f"{c}.SH"
    if c.startswith(("4", "8")):
        return f"{c}.BJ"
    return f"{c}.SZ"


def ts_code_to_code(ts_code: Any) -> Optional[str]:
    if ts_code is None:
        return None
    s = str(ts_code).strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    return normalize_code(s)


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _wan_to_yuan(v: Any) -> Optional[float]:
    x = _f(v)
    if x is None:
        return None
    return round(x * 10000.0, 2)


def _fmt_date_ymd(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().replace("-", "")[:8]
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _to_yyyymmdd(d: str) -> str:
    return str(d).strip().replace("-", "")[:8]


def parse_moneyflow_dc_row(
    raw: Dict[str, Any], *, now: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    code = ts_code_to_code(raw.get("ts_code"))
    trade_date = _fmt_date_ymd(raw.get("trade_date"))
    if not code or not trade_date:
        return None
    ts = now or datetime.now()
    return {
        "code": code,
        "trade_date": trade_date,
        "main_net_inflow": _wan_to_yuan(raw.get("net_amount")),
        "main_net_inflow_pct": _f(raw.get("net_amount_rate")),
        "super_large_net_inflow": _wan_to_yuan(raw.get("buy_elg_amount")),
        "super_large_net_inflow_pct": _f(raw.get("buy_elg_amount_rate")),
        "large_net_inflow": _wan_to_yuan(raw.get("buy_lg_amount")),
        "large_net_inflow_pct": _f(raw.get("buy_lg_amount_rate")),
        "mid_net_inflow": _wan_to_yuan(raw.get("buy_md_amount")),
        "mid_net_inflow_pct": _f(raw.get("buy_md_amount_rate")),
        "small_net_inflow": _wan_to_yuan(raw.get("buy_sm_amount")),
        "small_net_inflow_pct": _f(raw.get("buy_sm_amount_rate")),
        "close_price": _f(raw.get("close")),
        "change_percent": _f(raw.get("pct_change")),
        "source": SOURCE_DC,
        "created_at": ts,
        "updated_at": ts,
    }


def parse_moneyflow_l2_row(
    raw: Dict[str, Any], *, now: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """L2 moneyflow：净额 = 买入额 − 卖出额（万元→元）。主力 = 特大 + 大单。"""
    code = ts_code_to_code(raw.get("ts_code"))
    trade_date = _fmt_date_ymd(raw.get("trade_date"))
    if not code or not trade_date:
        return None

    def _net(buy_key: str, sell_key: str) -> Optional[float]:
        b, s = _f(raw.get(buy_key)), _f(raw.get(sell_key))
        if b is None and s is None:
            return None
        return _wan_to_yuan((b or 0.0) - (s or 0.0))

    super_n = _net("buy_elg_amount", "sell_elg_amount")
    large_n = _net("buy_lg_amount", "sell_lg_amount")
    mid_n = _net("buy_md_amount", "sell_md_amount")
    small_n = _net("buy_sm_amount", "sell_sm_amount")
    main_n = None
    if super_n is not None or large_n is not None:
        main_n = (super_n or 0.0) + (large_n or 0.0)

    ts = now or datetime.now()
    return {
        "code": code,
        "trade_date": trade_date,
        "main_net_inflow": main_n,
        "main_net_inflow_pct": None,
        "super_large_net_inflow": super_n,
        "super_large_net_inflow_pct": None,
        "large_net_inflow": large_n,
        "large_net_inflow_pct": None,
        "mid_net_inflow": mid_n,
        "mid_net_inflow_pct": None,
        "small_net_inflow": small_n,
        "small_net_inflow_pct": None,
        "close_price": None,
        "change_percent": None,
        "source": SOURCE_L2,
        "created_at": ts,
        "updated_at": ts,
    }


def rows_from_df(df: pd.DataFrame, *, api: str = "dc") -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    now = datetime.now()
    parser = parse_moneyflow_dc_row if api == "dc" else parse_moneyflow_l2_row
    out: List[Dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = parser(raw, now=now)
        if row:
            out.append(row)
    out.sort(key=lambda r: (r["code"], r["trade_date"]))
    return out


def fetch_moneyflow(
    pro,
    *,
    api: str = "dc",
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """调用 moneyflow_dc 或 moneyflow。日期参数为 YYYYMMDD。"""
    kwargs: Dict[str, Any] = {}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = _to_yyyymmdd(trade_date)
    if start_date:
        kwargs["start_date"] = _to_yyyymmdd(start_date)
    if end_date:
        kwargs["end_date"] = _to_yyyymmdd(end_date)
    if not kwargs:
        raise ValueError("moneyflow 至少需要 ts_code 或 trade_date/区间")

    try:
        if api == "dc":
            df = pro.moneyflow_dc(**kwargs)
        elif api == "l2":
            df = pro.moneyflow(**kwargs)
        else:
            raise ValueError(f"未知 api={api}，应为 dc 或 l2")
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.warning("tushare moneyflow api=%s kwargs=%s fail: %s", api, kwargs, e)
        return None


def list_open_trade_dates(
    pro, *, start_date: str, end_date: str
) -> List[str]:
    """返回开市日列表 YYYY-MM-DD；失败时退化为工作日近似。"""
    sd, ed = _to_yyyymmdd(start_date), _to_yyyymmdd(end_date)
    try:
        df = pro.trade_cal(
            exchange="SSE", start_date=sd, end_date=ed, is_open="1"
        )
        if df is not None and not df.empty:
            col = "cal_date" if "cal_date" in df.columns else df.columns[0]
            dates = []
            for v in df[col].tolist():
                d = _fmt_date_ymd(v)
                if d:
                    dates.append(d)
            return sorted(set(dates))
    except Exception as e:
        logger.warning("trade_cal 失败，改用工作日近似: %s", e)

    out: List[str] = []
    d0 = datetime.strptime(sd, "%Y%m%d").date()
    d1 = datetime.strptime(ed, "%Y%m%d").date()
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def default_date_range(days: int = 120) -> tuple[str, str]:
    end = datetime.now().date()
    start = end - timedelta(days=max(1, int(days)))
    return start.isoformat(), end.isoformat()


def backfill_by_code(
    pro,
    codes: Sequence[str],
    *,
    api: str = "dc",
    start_date: str,
    end_date: str,
    sleep_sec: float = 0.35,
    code_filter: Optional[set] = None,
) -> Dict[str, Any]:
    ok = fail = upserted = 0
    errors: List[str] = []
    for i, code in enumerate(codes, 1):
        ts_code = code_to_ts_code(code)
        if not ts_code:
            fail += 1
            continue
        df = fetch_moneyflow(
            pro,
            api=api,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )
        rows = rows_from_df(df, api=api) if df is not None else []
        if code_filter is not None:
            rows = [r for r in rows if r["code"] in code_filter]
        session = SessionLocal()
        try:
            n = upsert_rows(session, rows)
            session.commit()
            if n:
                ok += 1
                upserted += n
                print(
                    f"[{i}/{len(codes)}] OK {code} "
                    f"{rows[0]['trade_date']}~{rows[-1]['trade_date']} n={n}"
                )
            else:
                fail += 1
                print(f"[{i}/{len(codes)}] EMPTY {code}")
                if len(errors) < 20:
                    errors.append(f"{code}:empty")
        except Exception as e:
            session.rollback()
            fail += 1
            print(f"[{i}/{len(codes)}] FAIL {code} {e}")
            if len(errors) < 20:
                errors.append(f"{code}:{e}")
        finally:
            session.close()
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    return {
        "ok": ok,
        "fail": fail,
        "upserted": upserted,
        "errors_sample": errors,
        "mode": "by_code",
        "api": api,
    }


def backfill_by_date(
    pro,
    trade_dates: Sequence[str],
    *,
    api: str = "dc",
    sleep_sec: float = 0.35,
    code_filter: Optional[set] = None,
) -> Dict[str, Any]:
    """按交易日全市场拉取（推荐用于 --all）。"""
    ok = fail = upserted = 0
    errors: List[str] = []
    for i, d in enumerate(trade_dates, 1):
        df = fetch_moneyflow(pro, api=api, trade_date=d)
        rows = rows_from_df(df, api=api) if df is not None else []
        if code_filter is not None:
            rows = [r for r in rows if r["code"] in code_filter]
        session = SessionLocal()
        try:
            n = upsert_rows(session, rows)
            session.commit()
            if n:
                ok += 1
                upserted += n
                print(f"[{i}/{len(trade_dates)}] OK {d} rows={n}")
            else:
                fail += 1
                print(f"[{i}/{len(trade_dates)}] EMPTY {d}")
                if len(errors) < 20:
                    errors.append(f"{d}:empty")
        except Exception as e:
            session.rollback()
            fail += 1
            print(f"[{i}/{len(trade_dates)}] FAIL {d} {e}")
            if len(errors) < 20:
                errors.append(f"{d}:{e}")
        finally:
            session.close()
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    return {
        "ok": ok,
        "fail": fail,
        "upserted": upserted,
        "errors_sample": errors,
        "mode": "by_date",
        "api": api,
    }
