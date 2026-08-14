# -*- coding: utf-8 -*-
"""诊断 601991：楔形蓄势预警 → 上方共振阻力预警目标（约 7.12@12.2）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def main() -> int:
    from backend_api.database import SessionLocal
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.analysis.pattern_tactical import (
        annotate_hits_breakout_probe,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_core.analysis.stock_multi_strategy import _eval_gms
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code = "601991"
    asof = "2026-08-14"
    adjust = normalize_price_adjust("qfq")
    lookback = 160

    db = SessionLocal()
    try:
        asof_s = resolve_effective_trade_date(db, asof, market="CN")
        bars_map = batch_load_ohlc_asc(db, [code], lookback=lookback, asof=asof_s)
        bars = bars_map.get(code) or []
        if adjust == "qfq" and bars:
            bars, _ = apply_qfq_to_code_bars(db, code, bars)
        hits, inv_n = (
            detect_all_counted(bars, types=None, include_invalidated=True)
            if len(bars) >= 30
            else ([], 0)
        )

        last = bars[-1] if bars else {}
        print(
            f"code={code} asof={asof_s} bars={len(bars)} "
            f"last_close={last.get('close')} date={last.get('date') or last.get('trade_date')}"
        )

        gms_pack = None
        try:
            gms_pack = _eval_gms(db, code, str(asof_s)[:10])
        except Exception as e:
            print(f"GMS eval error: {e}")
        gms_score = (gms_pack or {}).get("score") if isinstance(gms_pack, dict) else None

        classic = None
        confluence = None
        try:
            from backend_api.stock.stock_analysis import KeyLevels
            from backend_core.analysis.confluence_zones import (
                compute_confluence_from_reference,
            )

            lc = float(last.get("close")) if last.get("close") is not None else 0.0
            classic = KeyLevels.calculate_classic_reference_levels(bars, lc)
            if isinstance(classic, dict):
                conf = compute_confluence_from_reference(
                    classic, last_close=lc, atr=classic.get("atr")
                )
                if isinstance(conf, dict) and conf.get("ok"):
                    confluence = conf
        except Exception as e:
            print(f"classic/confluence skip: {e}")

        if isinstance(confluence, dict):
            above = []
            for z in confluence.get("resistances") or []:
                if not isinstance(z, dict):
                    continue
                c = z.get("center")
                if c is None:
                    continue
                above.append(
                    {
                        "center": c,
                        "strength": z.get("strength"),
                        "low": z.get("low"),
                        "high": z.get("high"),
                        "sources": z.get("sources"),
                    }
                )
            print(
                json.dumps(
                    {"confluence_resistances_above": above[:8]},
                    ensure_ascii=False,
                    indent=2,
                )
            )

        gms_in = {"score": gms_score, "hit": bool((gms_pack or {}).get("hit"))} if gms_score is not None else None
        out = build_pattern_tactical(
            hits,
            confluence=confluence,
            classic=classic if isinstance(classic, dict) else None,
            gms=gms_in,
            invalidated_count=inv_n,
            asof=asof_s,
            market=market_snapshot_from_bars(bars),
        )
        annotated = annotate_hits_breakout_probe(
            [h for h in hits if str(h.get("status") or "") != "invalidated"],
            out,
        )
        fw = next(
            (h for h in annotated if str(h.get("pattern_type")) == "falling_wedge"),
            None,
        )
        alert = out.get("wedge_breakout_alert")
        print(
            json.dumps(
                {
                    "display_status": out.get("display_status"),
                    "status_note": out.get("status_note"),
                    "wedge_breakout_alert": alert,
                    "buy_hints": out.get("buy_hints"),
                    "hit_display_status": (fw or {}).get("display_status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if isinstance(alert, dict) and alert.get("ok"):
            print(
                f"ALERT_TARGET={alert.get('target')} strength={alert.get('target_strength')} "
                f"inv={alert.get('alert_invalidation')}"
            )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
