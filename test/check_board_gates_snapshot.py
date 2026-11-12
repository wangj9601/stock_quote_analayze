# -*- coding: utf-8 -*-
from sqlalchemy import text

from backend_core.database.db import SessionLocal

td = "2026-11-04"
db = SessionLocal()
try:
    print("short_state:", db.execute(
        text(
            "SELECT short_state, count(*) FROM board_gate_daily "
            "WHERE trade_date = CAST(:td AS date) GROUP BY 1 ORDER BY 2 DESC"
        ),
        {"td": td},
    ).fetchall())
    print("midlong_state:", db.execute(
        text(
            "SELECT midlong_state, count(*) FROM board_gate_daily "
            "WHERE trade_date = CAST(:td AS date) GROUP BY 1 ORDER BY 2 DESC"
        ),
        {"td": td},
    ).fetchall())
    print("kind:", db.execute(
        text(
            "SELECT board_kind, count(*) FROM board_gate_daily "
            "WHERE trade_date = CAST(:td AS date) GROUP BY 1"
        ),
        {"td": td},
    ).fetchall())
    print("observe:", db.execute(
        text(
            "SELECT count(*) FROM board_gate_daily "
            "WHERE trade_date = CAST(:td AS date) AND trade_observe_flag"
        ),
        {"td": td},
    ).fetchone())
    print("rs rated:", db.execute(
        text(
            "SELECT count(*) FROM board_rs_ratings "
            "WHERE trade_date = CAST(:td AS date) AND rs_rating IS NOT NULL"
        ),
        {"td": td},
    ).fetchone())
    print("observe industry ths:", db.execute(
        text(
            "SELECT count(*) FROM industry_board_basic_info "
            "WHERE COALESCE(trade_observe_flag, FALSE) = TRUE "
            "AND COALESCE(board_code_source, 'tonghuashun') = 'tonghuashun'"
        )
    ).fetchone())
    print("sample short_raw:", db.execute(
        text(
            "SELECT board_code, short_raw, short_state, midlong_raw, midlong_state "
            "FROM board_gate_daily WHERE trade_date = CAST(:td AS date) "
            "ORDER BY board_code LIMIT 8"
        ),
        {"td": td},
    ).fetchall())
finally:
    db.close()
