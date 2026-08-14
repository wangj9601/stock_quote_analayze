# -*- coding: utf-8 -*-
"""诊断 688110 东芯股份：旗形 upper/status、tactical、ATR、近端支撑 invalidation。"""
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
    from backend_core.analysis.chart_patterns.rules import BREAKOUT_UP_MULT
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.analysis.classic_levels import compute_classic_levels_from_bars
    from backend_core.analysis.pattern_tactical import (
        INVALIDATION_BELOW_ENTRY_PCT,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code = "688110"
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

        for h in hits:
            lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
            u = lv.get("upper")
            c = lv.get("last_close")
            thr = (float(u) * BREAKOUT_UP_MULT) if u else None
            print(
                json.dumps(
                    {
                        "type": h.get("pattern_type"),
                        "status": h.get("status"),
                        "confidence": h.get("confidence"),
                        "upper": u,
                        "lower": lv.get("lower"),
                        "last_close": c,
                        "confirm_thr": round(thr, 2) if thr is not None else None,
                        "close_gt_upper": (
                            float(c) > float(u) if c is not None and u is not None else None
                        ),
                        "close_gt_confirm": (
                            float(c) > thr if c is not None and thr is not None else None
                        ),
                        "reason": (h.get("reason") or "")[:140],
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )

        vp = confluence = rpe = None
        classic = None
        try:
            from backend_api.stock.pattern_routes import _tactical_enrichment

            enriched = _tactical_enrichment(db, bars, code, asof_s)
            vp, confluence, rpe = enriched[0], enriched[1], enriched[2]
            # (vp, confluence, rpe, gms, classic)
            if len(enriched) >= 5:
                classic = enriched[4]
            elif len(enriched) > 3:
                classic = enriched[3]
        except Exception as e:
            print("ENRICH_ERR", type(e).__name__, e)

        ref = compute_classic_levels_from_bars(bars) if bars else {}
        atr = ref.get("atr")
        close = float(last.get("close") or 0) or None
        atr_pct = (float(atr) / close) if atr and close else None
        print(
            json.dumps(
                {
                    "atr": atr,
                    "atr_pct": round(atr_pct, 4) if atr_pct is not None else None,
                    "atr_pivot": (ref.get("atr_pivot") or {}).get("atr")
                    if isinstance(ref.get("atr_pivot"), dict)
                    else None,
                },
                ensure_ascii=False,
                default=str,
            )
        )

        if isinstance(confluence, dict):
            print(
                "supports=",
                json.dumps((confluence.get("supports") or [])[:6], ensure_ascii=False, default=str),
            )
            print(
                "nearest_support_zone=",
                json.dumps(
                    confluence.get("nearest_support_zone"), ensure_ascii=False, default=str
                ),
            )

        snap = market_snapshot_from_bars(bars) if bars else None
        out = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
            asof=asof_s,
            market=snap,
            classic=classic if isinstance(classic, dict) else ref,
        )
        print("=== tactical ===")
        print(
            json.dumps(
                {
                    "short_bias": out.get("short_bias"),
                    "bias_label": out.get("bias_label"),
                    "grade": out.get("grade"),
                    "confidence": out.get("confidence"),
                    "rationale": out.get("rationale"),
                    "risk_note": out.get("risk_note"),
                    "breakout_probe": out.get("breakout_probe"),
                    "status_note": out.get("status_note"),
                    "display_status": out.get("display_status"),
                    "atr": out.get("atr"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        from backend_core.analysis.pattern_tactical import _clamp_invalidation

        if atr and close:
            demo = _clamp_invalidation(114.16, 114.16, atr=float(atr), close=float(close))
            print(
                json.dumps(
                    {
                        "clamp_demo_entry": 114.16,
                        "clamp_demo_inv": demo,
                        "clamp_1pct": round(114.16 * 0.99, 2),
                    },
                    ensure_ascii=False,
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
