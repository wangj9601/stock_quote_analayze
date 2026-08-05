# -*- coding: utf-8 -*-
"""多周期 K 线日历期末日聚合。

季线 / 半年线 / 年线的 bar 日期统一为自然日历：
  - 季末：03-31 / 06-30 / 09-30 / 12-31
  - 半年末：06-30 / 12-31
  - 年末：12-31

避免 pandas ``6ME`` 随数据起点漂移到 03-31/09-30 等错误锚点。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Dict, Iterable, Optional, Union

import pandas as pd

DateLike = Union[date, str, pd.Timestamp]

OHLCV_AGG: Dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "amount": "sum",
    "name": "first",
}


def to_calendar_quarter_end(ts) -> pd.Timestamp:
    """任意日期 → 所在季度最后一天。"""
    t = pd.Timestamp(ts)
    end_month = ((int(t.month) - 1) // 3 + 1) * 3
    return pd.Timestamp(year=int(t.year), month=end_month, day=1) + pd.offsets.MonthEnd(0)


def to_calendar_half_end(ts) -> pd.Timestamp:
    """任意日期 → 所在半年最后一天（06-30 / 12-31）。"""
    t = pd.Timestamp(ts)
    if int(t.month) <= 6:
        return pd.Timestamp(year=int(t.year), month=6, day=30)
    return pd.Timestamp(year=int(t.year), month=12, day=31)


def to_calendar_year_end(ts) -> pd.Timestamp:
    """任意日期 → 所在年最后一天（12-31）。"""
    t = pd.Timestamp(ts)
    return pd.Timestamp(year=int(t.year), month=12, day=31)


def _period_end_fn(period: str):
    p = str(period or "").strip().lower()
    if p in ("quarterly", "quarter", "q"):
        return to_calendar_quarter_end
    if p in ("semiannual", "semi", "half", "6m"):
        return to_calendar_half_end
    if p in ("annual", "year", "y", "a"):
        return to_calendar_year_end
    raise ValueError(f"不支持的周期: {period}（仅 quarterly/semiannual/annual）")


def calendar_period_end(ts: DateLike, period: str) -> date:
    """任意日期 → 所在季/半年/年的自然日历期末日。"""
    return _period_end_fn(period)(ts).date()


def is_last_session_day_of_period(
    d: DateLike,
    period: str,
    *,
    is_session_closed: Callable[[date], bool],
) -> bool:
    """判断 ``d`` 是否为该周期（季末 / 半年末 / 年末）内最后一个交易日。

    规则（与 bar 日期自然期末一致）：
    - ``d`` 当日必须为交易日；
    - ``d`` 不得超过所在周期的自然期末日；
    - ``(d, period_end]`` 区间内再无交易日（期末落在周末/节假日时，取期末前最后一个交易日）。

    Parameters
    ----------
    is_session_closed : 给定日期是否休市（周末或交易日历节假日）
    """
    day = pd.Timestamp(d).date()
    if is_session_closed(day):
        return False
    end = calendar_period_end(day, period)
    if day > end:
        return False
    cur = day + timedelta(days=1)
    while cur <= end:
        if not is_session_closed(cur):
            return False
        cur += timedelta(days=1)
    return True


def resample_ohlcv_to_period_ends(
    df: pd.DataFrame,
    period: str,
    *,
    columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """按日历期末日 groupby 聚合 OHLCV（及可选 name）。

    Parameters
    ----------
    df : 索引为 DatetimeIndex 的行情 DataFrame
    period : quarterly | semiannual | annual
    columns : 参与聚合的列；默认取 df 中出现在 OHLCV_AGG 的列
    """
    if df is None or df.empty:
        return pd.DataFrame()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("resample_ohlcv_to_period_ends 要求 DatetimeIndex")

    fn = _period_end_fn(period)
    if columns is None:
        cols = [c for c in OHLCV_AGG if c in df.columns]
    else:
        cols = [c for c in columns if c in df.columns and c in OHLCV_AGG]
    if not cols:
        return pd.DataFrame()

    agg = {c: OHLCV_AGG[c] for c in cols}
    tmp = df[cols].copy()
    tmp["_period_end"] = [fn(x) for x in tmp.index]
    out = tmp.groupby("_period_end", sort=True).agg(agg)
    out.index.name = None
    return out
