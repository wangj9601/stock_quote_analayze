"""
A 股 / 港股历史行情：当 turnover_rate 为空或 0 时，从 akshare 拉取换手率并回写数据库。
逻辑与 stock/history_api.get_stock_history 中原有实现一致，供 /api/quotes/history 与单股历史复用。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _date_str(d: Any) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    s = str(d)
    return s[:10] if len(s) >= 10 else s


def _fetch_a_share_hist_df(code: str, start_ymd: str, end_ymd: str) -> Optional[pd.DataFrame]:
    """返回含「日期」「换手率」列的 DataFrame，失败返回 None。"""
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 未安装，无法回填换手率")
        return None

    hist_df = None
    try:
        hist_df = ak.stock_zh_a_hist(symbol=code, start_date=start_ymd, end_date=end_ymd, adjust="")
    except Exception as e:
        logger.debug("stock_zh_a_hist 失败 %s: %s，尝试 stock_zh_a_daily", code, e)
    if hist_df is None or hist_df.empty:
        try:
            if code.startswith("6"):
                _symbol = "sh" + code
            elif code.startswith(("0", "3")):
                _symbol = "sz" + code
            else:
                _symbol = "bj" + code
            _daily_df = ak.stock_zh_a_daily(symbol=_symbol, start_date=start_ymd, end_date=end_ymd, adjust="")
            if _daily_df is not None and not _daily_df.empty and "date" in _daily_df.columns and "turnover" in _daily_df.columns:
                hist_df = pd.DataFrame()
                hist_df["日期"] = pd.to_datetime(_daily_df["date"]).dt.strftime("%Y-%m-%d")
                hist_df["换手率"] = _daily_df["turnover"].astype(float) * 100
        except Exception as e2:
            logger.debug("stock_zh_a_daily 失败 %s: %s", code, e2)
            return None

    if hist_df is None or hist_df.empty:
        return None
    # 列名兼容：中文 / 英文
    if "日期" not in hist_df.columns and "date" in hist_df.columns:
        hist_df = hist_df.rename(columns={"date": "日期"})
    if "换手率" not in hist_df.columns and "turnover" in hist_df.columns:
        hist_df = hist_df.rename(columns={"turnover": "换手率"})
    if "换手率" not in hist_df.columns or "日期" not in hist_df.columns:
        return None

    hist_df = hist_df.copy()
    hist_df["日期"] = hist_df["日期"].astype(str)
    date_formatted = []
    for d in hist_df["日期"]:
        d = str(d)
        if len(d) == 8 and d.isdigit():
            date_formatted.append(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        else:
            date_formatted.append(d[:10])
    hist_df["日期"] = date_formatted
    hist_df.set_index("日期", inplace=True)
    return hist_df


def _fetch_hk_hist_df(code: str, start_ymd: str, end_ymd: str) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
    except ImportError:
        return None
    try:
        hist_df = ak.stock_hk_hist(
            symbol=code, period="daily", start_date=start_ymd, end_date=end_ymd, adjust=""
        )
    except Exception as e:
        logger.debug("stock_hk_hist 失败 %s: %s", code, e)
        return None
    if hist_df is None or hist_df.empty:
        return None
    if "换手率" not in hist_df.columns or "日期" not in hist_df.columns:
        return None
    hist_df = hist_df.copy()
    hist_df["日期"] = hist_df["日期"].astype(str)
    date_formatted = []
    for d in hist_df["日期"]:
        d = str(d)
        if len(d) == 8 and d.isdigit():
            date_formatted.append(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        else:
            date_formatted.append(d[:10])
    hist_df["日期"] = date_formatted
    hist_df.set_index("日期", inplace=True)
    return hist_df


def backfill_missing_turnover_a_share(
    items: List[Dict[str, Any]],
    db: Session,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """
    对 items（已序列化的行 dict，含 code/date/turnover_rate）中空换手率的记录，用 akshare 回填并 UPDATE historical_quotes。
    按 code 分组，每组一次网络请求。start_date/end_date 缺省时用当页行的最小/最大日期。
    """
    need = [
        it
        for it in items
        if it.get("turnover_rate") is None or it.get("turnover_rate") == 0
    ]
    if not need:
        return 0

    by_code: Dict[str, List[Dict[str, Any]]] = {}
    for it in need:
        c = it.get("code")
        if not c:
            continue
        by_code.setdefault(str(c), []).append(it)

    updated = 0
    for code, rows in by_code.items():
        dates = [_date_str(r.get("date")) for r in rows if _date_str(r.get("date"))]
        if not dates:
            continue
        q_start = (start_date or min(dates)).replace("-", "")[:8]
        q_end = (end_date or max(dates)).replace("-", "")[:8]
        if len(q_start) != 8 or len(q_end) != 8:
            continue

        hist_df = _fetch_a_share_hist_df(code, q_start, q_end)
        if hist_df is None or hist_df.empty:
            continue

        for it in rows:
            ds = _date_str(it.get("date"))
            if not ds:
                continue
            try:
                if ds not in hist_df.index:
                    continue
                val = hist_df.loc[ds, "换手率"]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.isna(val):
                    continue
                if isinstance(val, str):
                    val = val.replace("%", "")
                turnover = float(val)
                it["turnover_rate"] = turnover
                db.execute(
                    text(
                        "UPDATE historical_quotes SET turnover_rate = :tr WHERE code = :code AND date = :d"
                    ),
                    {"tr": turnover, "code": code, "d": ds},
                )
                updated += 1
            except Exception as ex:
                logger.debug("回填换手率失败 code=%s date=%s: %s", code, ds, ex)

    if updated:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return updated


def backfill_missing_turnover_hk(
    items: List[Dict[str, Any]],
    db: Session,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """同上，表为 historical_quotes_hk。"""
    need = [
        it
        for it in items
        if it.get("turnover_rate") is None or it.get("turnover_rate") == 0
    ]
    if not need:
        return 0

    by_code: Dict[str, List[Dict[str, Any]]] = {}
    for it in need:
        c = it.get("code")
        if not c:
            continue
        by_code.setdefault(str(c), []).append(it)

    updated = 0
    for code, rows in by_code.items():
        dates = [_date_str(r.get("date")) for r in rows if _date_str(r.get("date"))]
        if not dates:
            continue
        q_start = (start_date or min(dates)).replace("-", "")[:8]
        q_end = (end_date or max(dates)).replace("-", "")[:8]
        if len(q_start) != 8 or len(q_end) != 8:
            continue

        hist_df = _fetch_hk_hist_df(code, q_start, q_end)
        if hist_df is None or hist_df.empty:
            continue

        for it in rows:
            ds = _date_str(it.get("date"))
            if not ds:
                continue
            try:
                if ds not in hist_df.index:
                    continue
                val = hist_df.loc[ds, "换手率"]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.isna(val):
                    continue
                if isinstance(val, str):
                    val = val.replace("%", "")
                turnover = float(val)
                it["turnover_rate"] = turnover
                db.execute(
                    text(
                        "UPDATE historical_quotes_hk SET turnover_rate = :tr WHERE code = :code AND date = :d"
                    ),
                    {"tr": turnover, "code": code, "d": ds},
                )
                updated += 1
            except Exception as ex:
                logger.debug("回填港股换手率失败 code=%s date=%s: %s", code, ds, ex)

    if updated:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return updated
