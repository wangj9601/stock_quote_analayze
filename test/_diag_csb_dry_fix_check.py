# -*- coding: utf-8 -*-
"""快速核对：放量日 dry_ok 是否不再被同日否决。"""
from backend_api.database import SessionLocal
from backend_core.strategies.csb.config import get_default_csb_config
from backend_core.strategies.csb.data_loader import CSBDataLoader
from backend_core.strategies.csb.entry_detector import (
    detect_breakout,
    detect_entry,
    resolve_setup_for_breakout,
)
from backend_core.strategies.csb.setup_detector import check_dry_volume, detect_setup

db = SessionLocal()
cfg = get_default_csb_config()
loader = CSBDataLoader(db)
sample = loader.list_a_share_candidates()[::12]
dates = [
    "2025-03-15",
    "2025-06-15",
    "2025-09-15",
    "2025-12-15",
    "2026-03-15",
    "2026-06-15",
    "2026-09-15",
]
expand_n = dry_ok_on_expand = bo_via_prior = entry_bo = entry_lps = entry_probe = 0
for d in dates:
    for code, _ in sample:
        bars = loader.load_bars(code, end_date=d, limit=300)
        bars = [b for b in bars if str(b.get("date") or "")[:10] <= d]
        if len(bars) < 250:
            continue
        st = detect_setup(bars, cfg)
        ch = st.get("channel") or {}
        bo_ign = detect_breakout(bars, {"setup_ok": True, "channel": ch}, cfg)
        if bo_ign.get("expand_ok"):
            expand_n += 1
            if check_dry_volume(bars, cfg).get("dry_ok"):
                dry_ok_on_expand += 1
        setup_bo = resolve_setup_for_breakout(bars, st, cfg)
        if detect_breakout(bars, setup_bo, cfg).get("entry_signal"):
            bo_via_prior += 1
        en = detect_entry(bars, cfg)
        if en.get("entry_signal"):
            t = en.get("signal_type")
            if t == "CSB_BREAKOUT":
                entry_bo += 1
            elif t == "CSB_LPS":
                entry_lps += 1
            elif t == "CSB_PROBE":
                entry_probe += 1
print(
    {
        "expand_ok": expand_n,
        "dry_ok_among_expand": dry_ok_on_expand,
        "bo_via_prior_or_today_setup": bo_via_prior,
        "entry_bo": entry_bo,
        "entry_lps": entry_lps,
        "entry_probe": entry_probe,
    }
)
db.close()
