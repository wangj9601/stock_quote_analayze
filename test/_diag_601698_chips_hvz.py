# -*- coding: utf-8 -*-
"""诊断 601698 中国卫通：阻力叠 VAL 筹码密集压制增益（PDF asof≈2026-08-14）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def main() -> int:
    from backend_api.database import SessionLocal
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
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

        last = bars[-1] if bars else {}
        close = last.get("close")
        print(f"code={code} asof={asof_s} bars={len(bars)} last_close={close}")

        vp = confluence = classic = None
        try:
            from backend_api.stock.pattern_routes import _tactical_enrichment

            vp, confluence, _rpe, _gms, classic = _tactical_enrichment(
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
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )

        atr = None
        if isinstance(classic, dict):
            atr = classic.get("atr") or (classic.get("atr_pivot") or {}).get("atr")
        print(f"ATR={atr}")

        if isinstance(confluence, dict):
            print(
                "params=",
                json.dumps(
                    (confluence.get("params") or {}),
                    ensure_ascii=False,
                    default=str,
                ),
            )
            for z in (confluence.get("supports") or [])[:5]:
                print(
                    "S",
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "strength": z.get("strength"),
                            "strength_adjusted": z.get("strength_adjusted"),
                            "chips_void": z.get("chips_void"),
                            "chips_hvz": z.get("chips_hvz"),
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            for z in (confluence.get("resistances") or [])[:6]:
                print(
                    "R",
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "strength_adjusted": z.get("strength_adjusted"),
                            "chips_hvz": z.get("chips_hvz"),
                            "hvz_source": z.get("hvz_source"),
                            "hvz_level": z.get("hvz_level"),
                            "hvz_note": z.get("hvz_note"),
                            "sources": z.get("sources"),
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
