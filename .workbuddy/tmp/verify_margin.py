# -*- coding: utf-8 -*-
from backend_core.data_collectors.tushare.margin import collect_margin_for_date
from backend_core.database.db import SessionLocal
from sqlalchemy import text

r1 = collect_margin_for_date("2024-10-25", source="auto")
print(
    "run1",
    {
        k: r1.get(k)
        for k in (
            "success",
            "upserted",
            "source",
            "error",
            "tushare_error",
            "codes",
            "sparse",
            "fallback",
        )
    },
)
r2 = collect_margin_for_date("2024-10-25", source="auto")
print(
    "run2",
    {
        k: r2.get(k)
        for k in (
            "success",
            "upserted",
            "source",
            "error",
            "tushare_error",
            "codes",
            "sparse",
            "fallback",
        )
    },
)

s = SessionLocal()
n = s.execute(
    text("SELECT count(*) FROM stock_margin_daily WHERE trade_date='2024-10-25'")
).scalar()
src = s.execute(
    text(
        "SELECT source, count(*) FROM stock_margin_daily "
        "WHERE trade_date='2024-10-25' GROUP BY source"
    )
).fetchall()
print("db_count", n, "by_source", src)

from backend_api.stock.margin import (
    _compute_signal,
    _fetch_margin_rows,
    _resolve_float_mv,
)

rows = _fetch_margin_rows(s, "000001", start="2024-09-01", end="2024-10-25")
print("000001 rows", len(rows))
if rows:
    mv, mv_src = _resolve_float_mv(s, "000001", "2024-10-25")
    sig = _compute_signal(
        rows, trade_date="2024-10-25", float_mv=mv, float_mv_source=mv_src
    )
    print(
        "signal",
        {
            k: sig.get(k)
            for k in (
                "available",
                "rzye",
                "rz_net",
                "crowding",
                "squeeze_risk",
                "flags",
                "float_mv_source",
            )
        },
    )
s.close()
