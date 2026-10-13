# -*- coding: utf-8 -*-
from sqlalchemy import text
from backend_api.database import SessionLocal

db = SessionLocal()
q = text(
    """
    SELECT task_id, status, name,
           config->>'preset_id' AS preset_id,
           config->>'start_date' AS start_date,
           config->>'end_date' AS end_date,
           config->>'use_trace' AS use_trace,
           config->>'allowed_signal_types' AS allowed,
           summary->>'total_signals' AS total_signals,
           summary->>'sample_count' AS sample_count,
           LEFT(CAST(summary AS text), 500) AS summary_head
    FROM csb_backtest_tasks
    WHERE CAST(task_id AS text) LIKE :p
       OR config->>'preset_id' = 'breakout_lps_only'
    ORDER BY created_at DESC NULLS LAST
    LIMIT 30
    """
)
rows = db.execute(q, {"p": "066d%"}).fetchall()
print("rows", len(rows))
for r in rows:
    print(dict(r._mapping))

print("--- trace ---")
for r in db.execute(
    text(
        """
        SELECT signal_type, COUNT(*) AS n,
               MIN(trade_date)::text AS d0, MAX(trade_date)::text AS d1
        FROM csb_signal_trace
        GROUP BY signal_type
        ORDER BY n DESC
        """
    )
):
    print(dict(r._mapping))

# Same-day conflict: among days with expand_ok, how often dry fails
from backend_core.strategies.csb.config import get_default_csb_config
from backend_core.strategies.csb.data_loader import CSBDataLoader
from backend_core.strategies.csb.entry_detector import detect_breakout
from backend_core.strategies.csb.setup_detector import detect_setup, check_dry_volume
from backend_core.strategies.csb.indicators import avg_volume

cfg = get_default_csb_config()
loader = CSBDataLoader(db)
sample = loader.list_a_share_candidates()[::20]
dates = ["2025-06-15", "2025-12-15", "2026-06-15", "2026-09-15"]
expand_n = dry_fail_on_expand = 0
squeeze_and_expand = 0
for d in dates:
    for code, _ in sample:
        bars = loader.load_bars(code, end_date=d, limit=300)
        bars = [b for b in bars if str(b.get("date") or "")[:10] <= d]
        if len(bars) < 250:
            continue
        st = detect_setup(bars, cfg)
        ch = st.get("channel") or {}
        bo = detect_breakout(bars, {"setup_ok": True, "channel": ch}, cfg)
        if not bo.get("expand_ok"):
            continue
        expand_n += 1
        dry = check_dry_volume(bars, cfg)
        if not dry.get("dry_ok"):
            dry_fail_on_expand += 1
        if ch.get("squeeze_ok"):
            squeeze_and_expand += 1

print(
    "expand_ok days",
    expand_n,
    "dry_fail_among_them",
    dry_fail_on_expand,
    "also_squeeze",
    squeeze_and_expand,
)
db.close()
