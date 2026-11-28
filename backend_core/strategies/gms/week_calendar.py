"""
GMS 周线：已收盘周判定（Q20=A，覆盖周五休市）。

closed(F, as_of) := 不存在交易日 T 满足 as_of < T <= F
信号周 = 满足 closed 的最大周五标签 F（且 weekly_quotes 有 bar 时由调用方再过滤）。
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable, List, Optional, Sequence, Set

from sqlalchemy import text
from sqlalchemy.orm import Session


def normalize_date_str(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def friday_label_for_date(day: str) -> str:
    """返回包含 day 的 W-FRI 周五标签（日历周五，未必交易）。"""
    d = dt.datetime.strptime(normalize_date_str(day), "%Y-%m-%d").date()
    # Monday=0 ... Friday=4
    offset = (4 - d.weekday()) % 7
    fri = d + dt.timedelta(days=offset)
    return fri.isoformat()


def is_week_closed(friday_label: str, as_of: str, trade_dates: Set[str]) -> bool:
    """
    交易日完备：as_of 之后至周五标签 F（含）之间无剩余交易日。
    """
    f = normalize_date_str(friday_label)
    a = normalize_date_str(as_of)
    if not f or not a:
        return False
    for t in trade_dates:
        if a < t <= f:
            return False
    return True


def resolve_closed_week_friday(
    as_of: str,
    trade_dates: Sequence[str],
    *,
    candidate_fridays: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """
    解析截至 as_of 的最近已收盘周周五标签。

    candidate_fridays: 可选，来自 weekly_quotes 的周五集合；缺省则从交易日推导近若干周标签。
    """
    a = normalize_date_str(as_of)
    if not a:
        return None
    td = {normalize_date_str(x) for x in trade_dates if normalize_date_str(x)}
    if candidate_fridays:
        fridays = sorted({normalize_date_str(x) for x in candidate_fridays if normalize_date_str(x)})
    else:
        # 由 as_of 向前推约 3 年的周五标签候选
        end = dt.datetime.strptime(a, "%Y-%m-%d").date()
        start = end - dt.timedelta(days=400)
        fridays = []
        cur = start
        while cur <= end + dt.timedelta(days=7):
            if cur.weekday() == 4:
                fridays.append(cur.isoformat())
            cur += dt.timedelta(days=1)
        fridays = sorted(set(fridays))

    best: Optional[str] = None
    for f in fridays:
        if is_week_closed(f, a, td):
            best = f
    return best


def load_cn_trade_dates(
    db: Session,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[str]:
    """从 historical_quotes 去重取 A 股交易日（全市场 DISTINCT 可能偏重，限制日期窗）。"""
    end = normalize_date_str(end_date) or dt.date.today().isoformat()
    start = normalize_date_str(start_date)
    if not start:
        start = (
            dt.datetime.strptime(end, "%Y-%m-%d").date() - dt.timedelta(days=400)
        ).isoformat()
    rows = db.execute(
        text(
            """
            SELECT DISTINCT CAST(date AS TEXT) AS d
            FROM historical_quotes
            WHERE CAST(date AS TEXT) >= :start_date
              AND CAST(date AS TEXT) <= :end_date
            ORDER BY d
            """
        ),
        {"start_date": start, "end_date": end},
    ).fetchall()
    out: List[str] = []
    for r in rows:
        ds = normalize_date_str(r[0] if not hasattr(r, "d") else r.d)
        if ds:
            out.append(ds)
    return out


def load_weekly_friday_candidates(
    db: Session,
    *,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> List[str]:
    """从 weekly_quotes 取最近若干周五标签（降序后反转为升序）。"""
    end = normalize_date_str(end_date)
    sql = """
        SELECT DISTINCT date
        FROM weekly_quotes
        WHERE (:end_date = '' OR date <= :end_date)
        ORDER BY date DESC
        LIMIT :lim
    """
    rows = db.execute(
        text(sql),
        {"end_date": end or "", "lim": int(limit)},
    ).fetchall()
    fridays = [normalize_date_str(r[0]) for r in rows]
    fridays = [f for f in fridays if f]
    return sorted(set(fridays))


def resolve_gms_week_end(db: Session, as_of: str) -> Optional[str]:
    """DB 友好入口：返回截至 as_of 的最近已收盘周周五标签。"""
    a = normalize_date_str(as_of)
    if not a:
        return None
    trade_dates = load_cn_trade_dates(db, end_date=a)
    candidates = load_weekly_friday_candidates(db, end_date=a, limit=120)
    return resolve_closed_week_friday(a, trade_dates, candidate_fridays=candidates or None)


def resolve_gms_trade_date_fallback(db: Session) -> str:
    """取 historical_quotes 最新交易日，失败则用今天。"""
    try:
        row = db.execute(text("SELECT MAX(CAST(date AS TEXT)) FROM historical_quotes")).scalar()
        ds = normalize_date_str(row)
        if ds:
            return ds
    except Exception:
        pass
    return dt.date.today().isoformat()
