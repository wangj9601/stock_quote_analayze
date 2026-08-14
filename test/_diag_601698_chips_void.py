# -*- coding: utf-8 -*-
"""诊断 601698 中国卫通：VAL 下方支撑筹码真空折减（PDF asof≈2026-08-14）。"""
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

    code = "601698"
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
        print(f"code={code} asof={asof_s} bars={len(bars)} last_close={close}")

        vp = confluence = rpe = gms = classic = None
        try:
            from backend_api.stock.pattern_routes import _tactical_enrichment

            vp, confluence, rpe, gms, classic = _tactical_enrichment(
                db, bars, code, asof_s
            )
        except Exception as e:
            print("ENRICH_ERR", type(e).__name__, e)

        if isinstance(vp, dict):
            print(
                "VP:",
                json.dumps(
                    {
                        "ok": vp.get("ok"),
                        "lookback": vp.get("lookback"),
                        "poc": vp.get("poc"),
                        "val": vp.get("val"),
                        "vah": vp.get("vah"),
                        "nearest_support": vp.get("nearest_support"),
                        "support_note": vp.get("support_note"),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

        atr = None
        if isinstance(classic, dict):
            atr = classic.get("atr") or (classic.get("atr_pivot") or {}).get("atr")
        print(f"ATR={atr} gms_score={(gms or {}).get('score') if isinstance(gms, dict) else None}")

        if isinstance(confluence, dict):
            ns = confluence.get("nearest_support_zone")
            print("nearest_support_zone=", json.dumps(ns, ensure_ascii=False, default=str))
            for z in (confluence.get("supports") or [])[:5]:
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "strength_adjusted": z.get("strength_adjusted"),
                            "chips_void": z.get("chips_void"),
                            "void_note": z.get("void_note"),
                            "sources": z.get("sources"),
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
            classic=classic if isinstance(classic, dict) else None,
        )
        print("short_bias=", tactical.get("short_bias"), "risk_note=", tactical.get("risk_note"))
        print("buy_hints=", json.dumps(tactical.get("buy_hints"), ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
