# -*- coding: utf-8 -*-
"""诊断 000063 中兴通讯：confluence 近端 S/R 强度比 + 高倾角风暴预警。"""
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
        ASYMMETRY_NEAR_RESIST_PCT,
        ASYMMETRY_STRENGTH_RATIO,
        annotate_hits_breakout_probe,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code = "000063"
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
            s_str = float(
                ns.get("strength_adjusted")
                if ns.get("strength_adjusted") is not None
                else ns.get("strength")
                or 0
            )
            r_str = float(
                nr.get("strength_adjusted")
                if nr.get("strength_adjusted") is not None
                else nr.get("strength")
                or 0
            )
            s = float(ns.get("center") or 0)
            r = float(nr.get("center") or 0)
            c = float(close)
            dist = max(0.0, (r - c) / c) if c else None
            # 带内距离记 0
            lo = nr.get("low")
            hi = nr.get("high")
            if lo is not None and hi is not None and float(lo) <= c <= float(hi):
                dist = 0.0
            ratio = (r_str / s_str) if s_str > 0 else None
            print(
                json.dumps(
                    {
                        "s_px": s,
                        "r_px": r,
                        "s_str": s_str,
                        "r_str": r_str,
                        "ratio": round(ratio, 2) if ratio is not None else None,
                        "ratio_ok": ratio is not None
                        and ratio > ASYMMETRY_STRENGTH_RATIO,
                        "dist_to_resist_pct": round(dist, 6) if dist is not None else None,
                        "near_ok": dist is not None
                        and dist < ASYMMETRY_NEAR_RESIST_PCT,
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
        storm = tactical.get("asymmetry_storm")
        print(
            json.dumps(
                {
                    "short_bias": tactical.get("short_bias"),
                    "bias_label": tactical.get("bias_label"),
                    "display_status": tactical.get("display_status"),
                    "status_note": tactical.get("status_note"),
                    "risk_note": tactical.get("risk_note"),
                    "asymmetry_storm": storm,
                    "ultra_squeeze": tactical.get("ultra_squeeze"),
                    "breakout_probe": tactical.get("breakout_probe"),
                    "wedge_breakout_alert": tactical.get("wedge_breakout_alert"),
                    "buy_hints": tactical.get("buy_hints"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        for h in hits:
            if h.get("asymmetry_storm") or h.get("display_status"):
                print(
                    json.dumps(
                        {
                            "hit_type": h.get("pattern_type"),
                            "hit_status": h.get("status"),
                            "display_status": h.get("display_status"),
                            "asymmetry_storm": h.get("asymmetry_storm"),
                        },
                        ensure_ascii=False,
                    )
                )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
