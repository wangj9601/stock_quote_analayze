# -*- coding: utf-8 -*-
"""Tushare 融资融券明细 margin_detail → stock_margin_daily。

接口：https://tushare.pro/document/2?doc_id=59
金额单位：元（接口已为元，无需再乘万）。
需约 2000 积分；单次最多约 6000 行。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd
from sqlalchemy import text

from backend_core.config.config import TUSHARE_CONFIG
from backend_core.data_collectors.akshare.em_stock_fund_flow_daily import (
    normalize_code,
    safe_float,
)
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

# 全市场两融标的通常数千；低于此阈值视为稀疏，触发 AkShare 补洞
SPARSE_ROW_THRESHOLD = 500

MARGIN_FIELDS = (
    "trade_date,ts_code,name,"
    "rzye,rqye,rzmre,rqyl,rzche,rqchl,rqmcl,rzrqye"
)

UPSERT_SQL = """
INSERT INTO stock_margin_daily (
    code, trade_date, name,
    rzye, rzmre, rzche, rqye, rqyl, rqmcl, rqchl, rzrqye,
    source, created_at, updated_at
) VALUES (
    :code, :trade_date, :name,
    :rzye, :rzmre, :rzche, :rqye, :rqyl, :rqmcl, :rqchl, :rzrqye,
    :source, :created_at, :updated_at
)
ON CONFLICT (code, trade_date) DO UPDATE SET
    name = COALESCE(EXCLUDED.name, stock_margin_daily.name),
    rzye = EXCLUDED.rzye,
    rzmre = EXCLUDED.rzmre,
    rzche = EXCLUDED.rzche,
    rqye = EXCLUDED.rqye,
    rqyl = EXCLUDED.rqyl,
    rqmcl = EXCLUDED.rqmcl,
    rqchl = EXCLUDED.rqchl,
    rzrqye = EXCLUDED.rzrqye,
    source = EXCLUDED.source,
    updated_at = EXCLUDED.updated_at
WHERE stock_margin_daily.source IS DISTINCT FROM 'tushare'
   OR EXCLUDED.source = 'tushare'
"""

INSERT_ONLY_SQL = """
INSERT INTO stock_margin_daily (
    code, trade_date, name,
    rzye, rzmre, rzche, rqye, rqyl, rqmcl, rqchl, rzrqye,
    source, created_at, updated_at
) VALUES (
    :code, :trade_date, :name,
    :rzye, :rzmre, :rzche, :rqye, :rqyl, :rqmcl, :rqchl, :rzrqye,
    :source, :created_at, :updated_at
)
ON CONFLICT (code, trade_date) DO NOTHING
"""


def code_to_ts_code(code: str) -> str:
    c = (normalize_code(code) or str(code).strip()).zfill(6)
    if c.startswith("6"):
        return f"{c}.SH"
    if c.startswith(("4", "8")):
        return f"{c}.BJ"
    return f"{c}.SZ"


def ts_code_to_code(ts_code: Any) -> Optional[str]:
    if ts_code is None:
        return None
    s = str(ts_code).strip()
    if "." in s:
        s = s.split(".", 1)[0]
    return normalize_code(s)


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


def _tushare_token() -> str:
    return (
        (TUSHARE_CONFIG.get("token") or "").strip()
        or (os.getenv("TUSHARE_TOKEN") or "").strip()
    )


def _pro_api():
    token = _tushare_token()
    if not token:
        raise RuntimeError("未配置 TUSHARE_TOKEN，无法调用 Tushare margin_detail（约需 2000 积分）")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def margin_record_to_row(
    row: Dict[str, Any],
    *,
    source: str = "tushare",
    code: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    td = _trade_date(row.get("trade_date") or row.get("信用交易日期") or row.get("日期"))
    if not td:
        return None
    ts_code = str(row.get("ts_code") or "").strip()
    code_n = normalize_code(code) or ts_code_to_code(ts_code) or normalize_code(
        row.get("标的证券代码") or row.get("证券代码") or row.get("code")
    )
    if not code_n:
        return None
    name = row.get("name") or row.get("标的证券简称") or row.get("证券简称")
    name_s = str(name).strip()[:64] if name is not None else None
    ts = now or datetime.now()
    rzye = safe_float(row.get("rzye") if "rzye" in row else row.get("融资余额"))
    rzmre = safe_float(row.get("rzmre") if "rzmre" in row else row.get("融资买入额"))
    rzche = safe_float(row.get("rzche") if "rzche" in row else row.get("融资偿还额"))
    rqye = safe_float(row.get("rqye") if "rqye" in row else row.get("融券余额"))
    rqyl = safe_float(row.get("rqyl") if "rqyl" in row else row.get("融券余量"))
    rqmcl = safe_float(row.get("rqmcl") if "rqmcl" in row else row.get("融券卖出量"))
    rqchl = safe_float(row.get("rqchl") if "rqchl" in row else row.get("融券偿还量"))
    rzrqye = safe_float(row.get("rzrqye") if "rzrqye" in row else row.get("融资融券余额"))
    if rzrqye is None and rzye is not None:
        # 无两融余额时用融资余额 + 融券余额近似
        rzrqye = (rzye or 0.0) + (rqye or 0.0)
    return {
        "code": code_n,
        "trade_date": td,
        "name": name_s or None,
        "rzye": rzye,
        "rzmre": rzmre,
        "rzche": rzche,
        "rqye": rqye,
        "rqyl": rqyl,
        "rqmcl": rqmcl,
        "rqchl": rqchl,
        "rzrqye": rzrqye,
        "source": source,
        "created_at": ts,
        "updated_at": ts,
    }


def rows_from_margin_df(
    df: pd.DataFrame,
    *,
    source: str = "tushare",
    code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    now = datetime.now()
    out: List[Dict[str, Any]] = []
    for raw in df.to_dict(orient="records"):
        row = margin_record_to_row(raw, source=source, code=code, now=now)
        if row:
            out.append(row)
    out.sort(key=lambda r: (r["code"], r["trade_date"]))
    return out


def upsert_margin_rows(
    session,
    rows: Sequence[Dict[str, Any]],
    *,
    fill_only: bool = False,
) -> int:
    """写入 stock_margin_daily。

    fill_only=True：仅插入缺失 (code, trade_date)，不覆盖已有行（用于 AkShare 补洞）。
    fill_only=False：tushare 可覆盖任意行；非 tushare 源不覆盖已有 tushare 行。
    """
    if not rows:
        return 0
    bind = session.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    sql = INSERT_ONLY_SQL if fill_only else UPSERT_SQL
    if dialect == "postgresql":
        session.execute(text(sql), list(rows))
        return len(rows)
    n = 0
    for r in rows:
        if fill_only:
            exists = session.execute(
                text(
                    """
                    SELECT 1 FROM stock_margin_daily
                    WHERE code = :code AND trade_date = :trade_date
                    """
                ),
                {"code": r["code"], "trade_date": r["trade_date"]},
            ).fetchone()
            if exists:
                continue
        else:
            if r.get("source") != "tushare":
                cur = session.execute(
                    text(
                        """
                        SELECT source FROM stock_margin_daily
                        WHERE code = :code AND trade_date = :trade_date
                        """
                    ),
                    {"code": r["code"], "trade_date": r["trade_date"]},
                ).fetchone()
                if cur and str(cur[0] or "") == "tushare":
                    continue
            session.execute(
                text(
                    """
                    DELETE FROM stock_margin_daily
                    WHERE code = :code AND trade_date = :trade_date
                    """
                ),
                {"code": r["code"], "trade_date": r["trade_date"]},
            )
        session.execute(
            text(
                """
                INSERT INTO stock_margin_daily (
                    code, trade_date, name,
                    rzye, rzmre, rzche, rqye, rqyl, rqmcl, rqchl, rzrqye,
                    source, created_at, updated_at
                ) VALUES (
                    :code, :trade_date, :name,
                    :rzye, :rzmre, :rzche, :rqye, :rqyl, :rqmcl, :rqchl, :rzrqye,
                    :source, :created_at, :updated_at
                )
                """
            ),
            r,
        )
        n += 1
    return n


def existing_codes_for_date(session, trade_date: str, *, source: Optional[str] = None) -> Set[str]:
    td = (trade_date or "")[:10]
    if source:
        rows = session.execute(
            text(
                """
                SELECT code FROM stock_margin_daily
                WHERE trade_date = :td AND source = :src
                """
            ),
            {"td": td, "src": source},
        ).fetchall()
    else:
        rows = session.execute(
            text("SELECT code FROM stock_margin_daily WHERE trade_date = :td"),
            {"td": td},
        ).fetchall()
    out: Set[str] = set()
    for r in rows:
        c = normalize_code(r[0])
        if c:
            out.add(c)
    return out


def fetch_margin_detail_df(
    *,
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """trade_date / start_date / end_date 使用 YYYYMMDD。"""
    pro = _pro_api()
    kwargs: Dict[str, Any] = {"fields": MARGIN_FIELDS}
    if ts_code:
        kwargs["ts_code"] = ts_code
    if trade_date:
        kwargs["trade_date"] = trade_date.replace("-", "")[:8]
    if start_date:
        kwargs["start_date"] = start_date.replace("-", "")[:8]
    if end_date:
        kwargs["end_date"] = end_date.replace("-", "")[:8]
    df = pro.margin_detail(**kwargs)
    if df is None or df.empty:
        return None
    return df


def collect_tushare_margin_for_date(trade_date: str) -> Dict[str, Any]:
    """全市场单日：pro.margin_detail(trade_date=)。"""
    td = (trade_date or "").replace("-", "")[:8]
    if len(td) != 8:
        return {"success": False, "error": "trade_date 格式应为 YYYY-MM-DD", "upserted": 0}
    td_fmt = f"{td[:4]}-{td[4:6]}-{td[6:8]}"
    try:
        df = fetch_margin_detail_df(trade_date=td)
    except Exception as e:
        err = str(e)
        logger.warning("tushare margin_detail date=%s fail: %s", td, e)
        if "积分" in err or "permission" in err.lower() or "权限" in err:
            return {
                "success": False,
                "error": f"Tushare 权限不足（margin_detail 约需 2000 积分）: {err}",
                "upserted": 0,
                "trade_date": td_fmt,
            }
        return {"success": False, "error": err, "upserted": 0, "trade_date": td_fmt}
    if df is None or df.empty:
        return {
            "success": False,
            "error": "no data",
            "upserted": 0,
            "trade_date": td_fmt,
            "sparse": True,
        }
    rows = rows_from_margin_df(df, source="tushare")
    session = SessionLocal()
    try:
        n = upsert_margin_rows(session, rows)
        session.commit()
        sparse = n < SPARSE_ROW_THRESHOLD
        return {
            "success": True,
            "source": "tushare",
            "upserted": n,
            "codes": len({r["code"] for r in rows}),
            "trade_date": td_fmt,
            "sparse": sparse,
        }
    except Exception as e:
        session.rollback()
        logger.exception("tushare margin upsert failed date=%s", td)
        return {"success": False, "error": str(e), "upserted": 0, "trade_date": td_fmt}
    finally:
        session.close()


def collect_tushare_margin_for_code(
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
        df = fetch_margin_detail_df(
            ts_code=code_to_ts_code(code_n),
            start_date=start_date,
            end_date=end,
        )
    except Exception as e:
        logger.warning("tushare margin_detail %s fail: %s", code_n, e)
        return {"success": False, "code": code_n, "error": str(e), "upserted": 0}
    if df is None or df.empty:
        return {"success": False, "code": code_n, "error": "no data", "upserted": 0}
    rows = rows_from_margin_df(df, source="tushare", code=code_n)
    if days_n and len(rows) > days_n:
        rows = rows[-days_n:]
    session = SessionLocal()
    try:
        n = upsert_margin_rows(session, rows)
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
        logger.exception("tushare margin upsert failed code=%s", code_n)
        return {"success": False, "code": code_n, "error": str(e), "upserted": 0}
    finally:
        session.close()


def collect_margin_for_date(
    trade_date: str,
    *,
    source: str = "auto",
) -> Dict[str, Any]:
    """source=auto：先 Tushare；失败或稀疏再 AkShare 补洞（不覆盖 tushare 行）。"""
    src = (source or "auto").strip().lower()
    if src not in ("auto", "tushare", "akshare"):
        return {"success": False, "error": "source 应为 auto / tushare / akshare", "upserted": 0}

    ts_res: Optional[Dict[str, Any]] = None
    ts_err = None
    if src in ("auto", "tushare"):
        ts_res = collect_tushare_margin_for_date(trade_date)
        if src == "tushare":
            return ts_res
        if ts_res.get("success") and not ts_res.get("sparse"):
            return ts_res
        ts_err = ts_res.get("error") or ("sparse" if ts_res.get("sparse") else "tushare empty")

    from backend_core.data_collectors.akshare.margin_detail import (
        collect_akshare_margin_for_date,
    )

    ak_res = collect_akshare_margin_for_date(trade_date, fill_only=True)
    if ts_err:
        ak_res["tushare_error"] = ts_err
    if ts_res and ts_res.get("upserted"):
        ak_res["tushare_upserted"] = ts_res.get("upserted")
    if ak_res.get("success") and int(ak_res.get("upserted") or 0) > 0:
        ak_res["fallback"] = "akshare"
        # 合并成功：任一侧有数据即 success
        if ts_res and ts_res.get("success"):
            ak_res["success"] = True
            ak_res["upserted"] = int(ts_res.get("upserted") or 0) + int(
                ak_res.get("upserted") or 0
            )
            ak_res["source"] = "tushare+akshare"
        return ak_res

    if ts_res and ts_res.get("success"):
        # Tushare 有稀疏数据但 AkShare 也没补上
        out = dict(ts_res)
        out["akshare_error"] = ak_res.get("error")
        return out
    out = dict(ak_res) if isinstance(ak_res, dict) else {"success": False, "upserted": 0}
    out.setdefault("success", False)
    if ts_err:
        out["tushare_error"] = ts_err
    if not out.get("error"):
        out["error"] = ts_err or "collect failed"
    return out
