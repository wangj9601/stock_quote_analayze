"""港股 RS 候选池过滤。"""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


def _normalize_hk_code(code: str) -> Optional[str]:
    c = str(code or "").strip().upper()
    if c.startswith("HK") and len(c) > 2:
        c = c[2:]
    if c.isdigit():
        c = c.zfill(5) if len(c) <= 5 else c
    if len(c) == 5 and c.isdigit():
        return c
    return None


def list_candidate_codes_hk(
    session: Session,
    trade_date: str,
    *,
    codes: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    港股候选池：当日 historical_quotes_hk 有行情的 5 位代码，
    且 stock_basic_info_hk 存在、collect_enabled。
    """
    if codes is not None:
        want = []
        for c in codes:
            n = _normalize_hk_code(str(c))
            if n:
                want.append(n)
        want = list(dict.fromkeys(want))
        if not want:
            return []
        stmt = text(
            """
            SELECT b.code
            FROM stock_basic_info_hk b
            WHERE b.code IN :codes
              AND LENGTH(TRIM(b.code)) = 5
              AND COALESCE(b.collect_enabled, TRUE) = TRUE
            ORDER BY b.code
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = session.execute(stmt, {"codes": want}).fetchall()
        return [str(r[0]).strip() for r in rows if r and r[0]]

    rows = session.execute(
        text(
            """
            SELECT DISTINCT hq.code
            FROM historical_quotes_hk hq
            INNER JOIN stock_basic_info_hk b ON b.code = hq.code
            WHERE hq.date = :trade_date
              AND LENGTH(TRIM(hq.code)) = 5
              AND COALESCE(b.collect_enabled, TRUE) = TRUE
            ORDER BY hq.code
            """
        ),
        {"trade_date": trade_date[:10]},
    ).fetchall()
    return [str(r[0]).strip() for r in rows if r and r[0]]
