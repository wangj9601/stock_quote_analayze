# -*- coding: utf-8 -*-
"""排查：用户9自选是否含会被误映射为 A股000981 的代码（港股00981等）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from backend_api.database import SessionLocal


def _zfill6(code: str) -> str:
    s = str(code or "").strip()
    return s.zfill(6) if s.isdigit() else s


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT stock_code, stock_name
                FROM watchlist
                WHERE user_id = 9
                ORDER BY stock_code
                """
            )
        ).fetchall()
        print("watchlist_total", len(rows))
        risky = []
        for code, name in rows:
            raw = str(code)
            mapped = _zfill6(raw)
            if (
                mapped == "000981"
                or "山子" in str(name or "")
                or "981" in raw
                or (raw.isdigit() and len(raw) == 5)
            ):
                risky.append((repr(raw), name, mapped))
        print("risky_or_5digit", len(risky))
        for item in risky:
            print(item)
        n5 = sum(1 for c, _ in rows if str(c).strip().isdigit() and len(str(c).strip()) == 5)
        print("5digit_count", n5)
    finally:
        db.close()


if __name__ == "__main__":
    main()
