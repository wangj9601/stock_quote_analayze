# -*- coding: utf-8 -*-
"""诊断 605100 华丰股份：RPE+R4 动量买点 / 超强支撑高亮。"""
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
    from backend_core.analysis.chart_patterns.scanner import apply_qfq_to_code_bars
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )
    from backend_core.analysis.pattern_tactical import (
        SUPER_SUPPORT_STRENGTH,
        build_pattern_tactical,
        market_snapshot_from_bars,
    )
    from backend_api.stock.pattern_routes import _tactical_enrichment

    code = "605100"
    asof = "2026-08-14"
    db = SessionLocal()
    try:
        asof_s = resolve_effective_trade_date(db, asof, market="CN")
        bars = batch_load_ohlc_asc(db, [code], lookback=160, asof=asof_s).get(code) or []
        if bars:
            bars, _ = apply_qfq_to_code_bars(db, code, bars)
        hits, inv_n = (
            detect_all_counted(bars, include_invalidated=True)
            if len(bars) >= 30
            else ([], 0)
        )
        vp, confluence, rpe, gms, classic = _tactical_enrichment(db, bars, code, asof_s)
        cam = (classic or {}).get("camarilla") if isinstance(classic, dict) else None
        tac = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            gms=gms,
            invalidated_count=inv_n,
            asof=asof_s,
            market=market_snapshot_from_bars(bars),
            classic=classic,
        )
        print(
            json.dumps(
                {
                    "code": code,
                    "asof": asof_s,
                    "close": bars[-1].get("close") if bars else None,
                    "hits": [
                        {
                            "type": h.get("pattern_type"),
                            "status": h.get("status"),
                            "confidence": h.get("confidence"),
                        }
                        for h in hits
                    ],
                    "rpe": rpe,
                    "R4": (cam or {}).get("R4") if isinstance(cam, dict) else None,
                    "super_support_min": SUPER_SUPPORT_STRENGTH,
                    "supports_top": [
                        {
                            "center": z.get("center"),
                            "strength": z.get("strength"),
                        }
                        for z in (confluence or {}).get("supports") or []
                    ][:5],
                    "tactical": {
                        "short_bias": tac.get("short_bias"),
                        "bias_label": tac.get("bias_label"),
                        "grade": tac.get("grade"),
                        "structure_note": tac.get("structure_note"),
                        "highlight": tac.get("highlight"),
                        "buy_hints": tac.get("buy_hints"),
                        "rationale": tac.get("rationale"),
                        "evidence_codes": [
                            e.get("code")
                            for e in (tac.get("evidence") or [])
                            if e.get("ok")
                        ],
                    },
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
