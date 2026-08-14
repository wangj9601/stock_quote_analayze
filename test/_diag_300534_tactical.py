# -*- coding: utf-8 -*-
"""一次性诊断：300534 asof≈2026-08-13 形态战术标签。"""
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
        classify_short_bias,
    )

    code = "300534"
    asof = "2026-08-13"
    adjust = normalize_price_adjust("qfq")
    lookback = 160

    db = SessionLocal()
    try:
        asof_s = resolve_effective_trade_date(db, asof, market="CN")
        bars_map = batch_load_ohlc_asc(db, [code], lookback=lookback, asof=asof_s)
        bars = bars_map.get(code) or []
        adj_meta = None
        if adjust == "qfq" and bars:
            bars, adj_meta = apply_qfq_to_code_bars(db, code, bars)
        hits, inv_n = detect_all_counted(bars, types=None) if len(bars) >= 30 else ([], 0)

        print("=== BARS TAIL (last 20) ===")
        for b in bars[-20:]:
            d = b.get("trade_date") or b.get("date")
            print(
                f"  {d} O={b.get('open')} H={b.get('high')} "
                f"L={b.get('low')} C={b.get('close')}"
            )

        print("=== META ===")
        print(
            json.dumps(
                {
                    "code": code,
                    "asof_req": asof,
                    "asof": asof_s,
                    "adjust": adjust,
                    "bars": len(bars),
                    "hit_count": len(hits),
                    "invalidated_count": inv_n,
                    "adj_meta": adj_meta,
                },
                ensure_ascii=False,
                default=str,
            )
        )

        print("=== HITS SUMMARY ===")
        for h in hits:
            lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
            print(
                json.dumps(
                    {
                        "type": h.get("pattern_type"),
                        "status": h.get("status"),
                        "confidence": h.get("confidence"),
                        "formed_at": h.get("formed_at") or h.get("confirm_date"),
                        "key_levels": {
                            k: lv.get(k)
                            for k in ("upper", "lower", "neckline", "last_close")
                        },
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

        classified = classify_short_bias(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
        )
        tactical = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
        )

        print("=== PRIMARY ===")
        primary = classified.get("primary")
        if primary:
            lv = primary.get("key_levels") if isinstance(primary.get("key_levels"), dict) else {}
            print(
                json.dumps(
                    {
                        "type": primary.get("pattern_type"),
                        "status": primary.get("status"),
                        "confidence": primary.get("confidence"),
                        "key_levels": lv,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        else:
            print("None")

        print("=== PRESSURE_ZONE ===")
        print(json.dumps(classified.get("pressure_zone"), ensure_ascii=False, default=str))

        print("=== TACTICAL ===")
        print(json.dumps(tactical, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
