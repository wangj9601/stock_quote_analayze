# -*- coding: utf-8 -*-
"""诊断 002414 高德红外：confluence 近端 S/R + 极窄箱体变盘临界。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def main() -> int:
    from backend_api.database import SessionLocal
    from backend_api.stock.pattern_routes import _tactical_enrichment
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.analysis.pattern_tactical import (
        ULTRA_SQUEEZE_MIN_STRENGTH,
        ULTRA_SQUEEZE_WIDTH_PCT,
        annotate_hits_breakout_probe,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code = "002414"
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
        close = last.get("close")
        print(
            f"code={code} asof={asof_s} bars={len(bars)} "
            f"last_close={close} date={last.get('date') or last.get('trade_date')}"
        )

        vp, confluence, rpe, gms, classic = _tactical_enrichment(
            db, bars, code, str(asof_s)[:10]
        )
        ns = (confluence or {}).get("nearest_support_zone") if confluence else None
        nr = (confluence or {}).get("nearest_resistance_zone") if confluence else None
        print(
            json.dumps(
                {
                    "nearest_support": ns,
                    "nearest_resistance": nr,
                },
                ensure_ascii=False,
                default=str,
            )
        )
        if isinstance(ns, dict) and isinstance(nr, dict) and close:
            s = float(ns.get("center") or 0)
            r = float(nr.get("center") or 0)
            w = (r - s) / float(close) if float(close) else None
            print(
                json.dumps(
                    {
                        "width_pct": round(w, 6) if w is not None else None,
                        "width_ok": w is not None and w < ULTRA_SQUEEZE_WIDTH_PCT,
                        "s_str": ns.get("strength"),
                        "r_str": nr.get("strength"),
                        "strength_ok": (
                            float(ns.get("strength") or 0) > ULTRA_SQUEEZE_MIN_STRENGTH
                            and float(nr.get("strength") or 0) > ULTRA_SQUEEZE_MIN_STRENGTH
                        ),
                    },
                    ensure_ascii=False,
                )
            )

        market = market_snapshot_from_bars(bars) if bars else {"last_close": close}
        tactical = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            gms=gms,
            classic=classic,
            invalidated_count=inv_n,
            market=market,
            asof=str(asof_s)[:10],
        )
        hits = annotate_hits_breakout_probe(hits, tactical)
        ultra = tactical.get("ultra_squeeze")
        print(
            json.dumps(
                {
                    "short_bias": tactical.get("short_bias"),
                    "bias_label": tactical.get("bias_label"),
                    "display_status": tactical.get("display_status"),
                    "status_note": tactical.get("status_note"),
                    "risk_note": tactical.get("risk_note"),
                    "ultra_squeeze": ultra,
                    "breakout_probe": tactical.get("breakout_probe"),
                    "wedge_breakout_alert": tactical.get("wedge_breakout_alert"),
                    "buy_hints": tactical.get("buy_hints"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        for h in hits:
            if h.get("ultra_squeeze") or h.get("display_status"):
                print(
                    json.dumps(
                        {
                            "hit_type": h.get("pattern_type"),
                            "hit_status": h.get("status"),
                            "display_status": h.get("display_status"),
                            "ultra_squeeze": h.get("ultra_squeeze"),
                        },
                        ensure_ascii=False,
                    )
                )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
