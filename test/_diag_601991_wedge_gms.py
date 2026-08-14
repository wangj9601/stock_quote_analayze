# -*- coding: utf-8 -*-
"""诊断 601991 大唐发电：下降楔形 upper/status、GMS、试探突破/蓄势预警。"""
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
        gms_score = None
        if isinstance(gms_pack, dict):
            gms_score = gms_pack.get("score")
            print(
                json.dumps(
                    {
                        "gms_hit": gms_pack.get("hit"),
                        "gms_score": gms_score,
                        "gms_label": gms_pack.get("label"),
                        "gms_reason": (gms_pack.get("reason") or "")[:120],
                    },
                    ensure_ascii=False,
                )
            )

        for h in hits:
            if str(h.get("pattern_type") or "") != "falling_wedge":
                continue
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
                    },
                    ensure_ascii=False,
                )
            )

        # classic / confluence 尽量对齐 API enrichment
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
                cam = classic.get("camarilla") if isinstance(classic.get("camarilla"), dict) else {}
                print(
                    json.dumps(
                        {
                            "camarilla_S4": cam.get("S4"),
                            "camarilla_R1": cam.get("R1"),
                            "atr": classic.get("atr"),
                        },
                        ensure_ascii=False,
                    )
                )
        except Exception as e:
            print(f"classic/confluence skip: {e}")

        gms_in = None
        if gms_score is not None:
            gms_in = {"score": gms_score, "hit": bool((gms_pack or {}).get("hit"))}

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
        print(
            json.dumps(
                {
                    "short_bias": out.get("short_bias"),
                    "bias_label": out.get("bias_label"),
                    "display_status": out.get("display_status"),
                    "status_note": out.get("status_note"),
                    "gms_score": out.get("gms_score"),
                    "breakout_probe": out.get("breakout_probe"),
                    "wedge_breakout_alert": out.get("wedge_breakout_alert"),
                    "hit_display_status": (fw or {}).get("display_status"),
                    "hit_wedge_alert": (fw or {}).get("wedge_breakout_alert"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
