"""A 股 RS 候选池过滤。"""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def list_candidate_codes(
    session: Session,
    trade_date: str,
    *,
    codes: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    候选池：当日有行情的 6 位 A 股，且基础信息存在、collect_enabled、非 ST、非退市名。
    """
    if codes is not None:
        want = [str(c).strip().zfill(6) for c in codes if str(c).strip()]
        want = [c for c in want if len(c) == 6 and c.isdigit()]
        if not want:
            return []
        stmt = text(
            """
            SELECT b.code
            FROM stock_basic_info b
            WHERE b.code IN :codes
              AND LENGTH(TRIM(b.code)) = 6
              AND COALESCE(b.collect_enabled, TRUE) = TRUE
              AND COALESCE(b.name, '') NOT LIKE '%ST%'
              AND COALESCE(b.name, '') NOT LIKE '%退%'
            ORDER BY b.code
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = session.execute(stmt, {"codes": want}).fetchall()
        return [str(r[0]).strip() for r in rows if r and r[0]]

    rows = session.execute(
        text(
            """
            SELECT DISTINCT hq.code
            FROM historical_quotes hq
            INNER JOIN stock_basic_info b ON b.code = hq.code
            WHERE hq.date = :trade_date
              AND LENGTH(TRIM(hq.code)) = 6
              AND COALESCE(b.collect_enabled, TRUE) = TRUE
              AND COALESCE(b.name, '') NOT LIKE '%ST%'
              AND COALESCE(b.name, '') NOT LIKE '%退%'
            ORDER BY hq.code
            """
        ),
        {"trade_date": trade_date[:10]},
    ).fetchall()
    return [str(r[0]).strip() for r in rows if r and r[0]]
