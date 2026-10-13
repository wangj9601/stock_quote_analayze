# -*- coding: utf-8 -*-
"""诊断：为何一年窗口几乎无 BREAKOUT/LPS。"""
from __future__ import annotations

import copy
from collections import Counter

from sqlalchemy import text

from backend_api.database import SessionLocal
from backend_core.strategies.csb.config import get_default_csb_config
from backend_core.strategies.csb.data_loader import CSBDataLoader
from backend_core.strategies.csb.entry_detector import detect_breakout, detect_entry, detect_probe
from backend_core.strategies.csb.setup_detector import detect_setup


def main() -> None:
    db = SessionLocal()
    print("=== tasks matching 066d24af ===")
    try:
        rows = db.execute(
            text(
                """
                SELECT task_id, status,
                       config->>'start_date' AS start_date,
                       config->>'end_date' AS end_date,
                       config->>'preset_id' AS preset_id,
                       config->>'allowed_signal_types' AS allowed,
                       config->>'exit_mode' AS exit_mode,
                       LEFT(CAST(summary AS text), 400) AS summary_head
                FROM csb_backtest_tasks
                WHERE CAST(task_id AS text) LIKE :p
                ORDER BY created_at DESC NULLS LAST
                LIMIT 5
                """
            ),
            {"p": "066d24af%"},
        ).fetchall()
        for r in rows:
            print(dict(r._mapping))
        if not rows:
            print("(none)")
    except Exception as e:
        db.rollback()
        print("task query failed:", e)

    print("\n=== trace buy types all-time ===")
    for r in db.execute(
        text(
            """
            SELECT signal_type, COUNT(*) AS n,
                   MIN(trade_date)::text AS d0, MAX(trade_date)::text AS d1
            FROM csb_signal_trace
            WHERE signal_type IN ('CSB_PROBE','CSB_BREAKOUT','CSB_LPS','CSB_SETUP')
            GROUP BY signal_type
            ORDER BY n DESC
            """
        )
    ):
        print(dict(r._mapping))

    print("\n=== trace by config_id, 2025-01-01 .. 2026-10-01 ===")
    for r in db.execute(
        text(
            """
            SELECT config_id, signal_type, COUNT(*) AS n
            FROM csb_signal_trace
            WHERE trade_date >= DATE '2025-01-01'
              AND trade_date < DATE '2026-10-01'
              AND signal_type NOT LIKE '\\_\\_%' ESCAPE '\\'
            GROUP BY config_id, signal_type
            ORDER BY config_id, n DESC
            """
        )
    ):
        print(dict(r._mapping))

    loader = CSBDataLoader(db)
    cfg = get_default_csb_config()
    stocks = loader.list_a_share_candidates()
    sample = stocks[::15]  # ~360
    dates = [
        "2025-03-15",
        "2025-06-15",
        "2025-09-15",
        "2025-12-15",
        "2026-03-15",
        "2026-06-15",
        "2026-09-15",
    ]
    print(f"\n=== funnel sample stocks={len(sample)} dates={len(dates)} ===")

    funnel = Counter()
    # When setup fails only due to dry on breakout-like days
    dry_blocks_bo_candidate = 0
    bo_price_ok_but_no_setup = 0
    setup_fail_reasons = Counter()

    for d in dates:
        for code, _n in sample:
            bars = loader.load_bars(code, end_date=d, limit=300)
            bars = [b for b in bars if str(b.get("date") or "")[:10] <= d]
            if len(bars) < 250:
                continue
            funnel["checked"] += 1
            st = detect_setup(bars, cfg)
            ch = st.get("channel") or {}
            if not ch.get("ok"):
                funnel["channel_fail"] += 1
                continue
            funnel["channel_ok"] += 1
            if not ch.get("squeeze_ok"):
                funnel["no_squeeze"] += 1
            if not st.get("turnover_ok"):
                funnel["no_turnover"] += 1
            if not (st.get("ma250") or {}).get("ma250_ok"):
                funnel["no_ma250"] += 1
            if not st.get("touch_ok"):
                funnel["no_touch"] += 1
            if not (st.get("dry_vol") or {}).get("dry_ok"):
                funnel["no_dry"] += 1

            if st.get("setup_ok"):
                funnel["setup_ok"] += 1
            else:
                # attribute primary fail
                if not ch.get("squeeze_ok"):
                    setup_fail_reasons["squeeze"] += 1
                elif not st.get("turnover_ok"):
                    setup_fail_reasons["turnover"] += 1
                elif not (st.get("ma250") or {}).get("ma250_ok"):
                    setup_fail_reasons["ma250"] += 1
                elif not st.get("touch_ok"):
                    setup_fail_reasons["touch"] += 1
                elif not (st.get("dry_vol") or {}).get("dry_ok"):
                    setup_fail_reasons["dry"] += 1
                else:
                    setup_fail_reasons["other"] += 1

            # breakout components ignoring setup gate
            bo = detect_breakout(bars, {"setup_ok": True, "channel": ch}, cfg)
            if bo.get("expand_ok"):
                funnel["bo_expand_ok"] += 1
            if bo.get("body_ok"):
                funnel["bo_body_ok"] += 1
            if bo.get("shadow_ok"):
                funnel["bo_shadow_ok"] += 1
            if bo.get("break_line") and (bars[-1].get("close") or 0) >= bo["break_line"]:
                funnel["bo_price_ok"] += 1
            if bo.get("entry_signal"):
                funnel["bo_rules_ok_ignore_setup"] += 1
                if not st.get("setup_ok"):
                    bo_price_ok_but_no_setup += 1
                    dry = (st.get("dry_vol") or {}).get("dry_ok")
                    if dry is False:
                        dry_blocks_bo_candidate += 1

            # real detect with setup gate
            bo_real = detect_breakout(bars, st, cfg)
            if bo_real.get("entry_signal"):
                funnel["bo_real"] += 1
            if detect_probe(bars, st, cfg).get("entry_signal"):
                funnel["probe_real"] += 1
            en = detect_entry(bars, cfg)
            if en.get("entry_signal"):
                funnel[f"entry_{en.get('signal_type')}"] += 1

            # counterfactual: setup without dry requirement
            st2 = copy.deepcopy(st)
            if st2.get("channel", {}).get("squeeze_ok") and st2.get("turnover_ok") and (
                st2.get("ma250") or {}
            ).get("ma250_ok") and st2.get("touch_ok"):
                st2["setup_ok"] = True
                bo2 = detect_breakout(bars, st2, cfg)
                if bo2.get("entry_signal"):
                    funnel["bo_if_drop_dry_gate"] += 1

    print("FUNNEL", dict(funnel))
    print("setup_fail_primary", dict(setup_fail_reasons))
    print(
        "dry_blocks_bo_candidate",
        dry_blocks_bo_candidate,
        "bo_rules_ok_but_no_setup",
        bo_price_ok_but_no_setup,
    )
    db.close()


if __name__ == "__main__":
    main()
