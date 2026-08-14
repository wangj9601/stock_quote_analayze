# -*- coding: utf-8 -*-
"""诊断 600206 有研新材：近端买点 invalidation 应按档绑定（非共用 42.56）。"""
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
        INVALIDATION_BELOW_ENTRY_PCT,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )

    code = "600206"
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

        print(f"code={code} asof={asof_s} bars={len(bars)} hits={len(hits)} invalidated={inv_n}")
        if bars:
            print(
                f"last_close={bars[-1].get('close')} date={bars[-1].get('date') or bars[-1].get('trade_date')}"
            )

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
                        "shrink_pct": lv.get("shrink_pct"),
                        "bars_to_apex": lv.get("bars_to_apex"),
                        "apex_window": lv.get("apex_window"),
                        "upper_slope": lv.get("upper_slope"),
                        "lower_slope": lv.get("lower_slope"),
                        "reason": (h.get("reason") or "")[:120],
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
            supports = confluence.get("supports") or []
            print("supports=", json.dumps(supports[:6], ensure_ascii=False, default=str))
            ns = confluence.get("nearest_support_zone")
            print("nearest_support_zone=", json.dumps(ns, ensure_ascii=False, default=str))

        snap = market_snapshot_from_bars(bars) if bars else None
        out = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
            asof=asof_s,
            market=snap,
        )
        print("=== tactical ===")
        print(
            json.dumps(
                {
                    "short_bias": out.get("short_bias"),
                    "bias_label": out.get("bias_label"),
                    "grade": out.get("grade"),
                    "confidence": out.get("confidence"),
                    "risk_note": out.get("risk_note"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        for i, h in enumerate(out.get("buy_hints") or [], 1):
            ez = h.get("entry_zone") or {}
            lo = ez.get("low")
            inv = h.get("invalidation")
            print(
                json.dumps(
                    {
                        "n": i,
                        "type": h.get("type"),
                        "priority": h.get("priority"),
                        "anchor": ez.get("anchor"),
                        "entry": f"{ez.get('low')}–{ez.get('high')}",
                        "center": ez.get("center"),
                        "strength": ez.get("strength"),
                        "invalidation": inv,
                        "target": h.get("target"),
                        "trigger": h.get("trigger"),
                        "inv_vs_low_ok": (
                            inv is not None
                            and lo is not None
                            and float(inv) < float(lo)
                        ),
                        "approx_1pct": (
                            round(float(lo) * (1.0 - INVALIDATION_BELOW_ENTRY_PCT), 2)
                            if lo is not None
                            else None
                        ),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
