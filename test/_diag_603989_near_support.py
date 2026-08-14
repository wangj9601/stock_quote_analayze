# -*- coding: utf-8 -*-
"""诊断 603989 艾华：近端共振优先 vs 远端楔下沿 buy_hints。"""
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
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )
    from backend_core.analysis.pattern_tactical import (
        build_pattern_tactical,
        market_snapshot_from_bars,
    )

    code = "603989"
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

        print(f"code={code} asof={asof_s} bars={len(bars)} hits={len(hits)}")
        if bars:
            print(f"last_close={bars[-1].get('close')} date={bars[-1].get('date') or bars[-1].get('trade_date')}")

        for h in hits:
            lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
            print(
                json.dumps(
                    {
                        "type": h.get("pattern_type"),
                        "status": h.get("status"),
                        "confidence": h.get("confidence"),
                        "upper": lv.get("upper"),
                        "lower": lv.get("lower"),
                        "last_close": lv.get("last_close"),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )

        vp = confluence = rpe = None
        try:
            from backend_api.stock.pattern_routes import _tactical_enrichment

            vp, confluence, rpe, *_rest = _tactical_enrichment(db, bars, code, asof_s)
        except Exception as e:
            print("ENRICH_ERR", type(e).__name__, e)

        if isinstance(confluence, dict):
            ns = confluence.get("nearest_support_zone")
            print("nearest_support_zone=", json.dumps(ns, ensure_ascii=False, default=str))
            supports = confluence.get("supports") or []
            print(f"supports_n={len(supports)}")
            for z in supports[:5]:
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )

        tactical = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
            asof=asof_s,
            market=market_snapshot_from_bars(bars) if bars else None,
        )
        print("=== buy_hints ===")
        print(json.dumps(tactical.get("buy_hints"), ensure_ascii=False, indent=2, default=str))
        print("short_bias=", tactical.get("short_bias"), "risk_note=", tactical.get("risk_note"))
        ev = [
            e
            for e in (tactical.get("evidence") or [])
            if isinstance(e, dict) and e.get("code") == "near_support_pref"
        ]
        print("near_support_pref evidence=", json.dumps(ev, ensure_ascii=False, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
