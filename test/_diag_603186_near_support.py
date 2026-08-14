# -*- coding: utf-8 -*-
"""诊断 603186 华正新材：为何未走近端共振优先 / 仍锚远端形态下沿。"""
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
        BUY_PRESSURE_MIN_STRENGTH,
        BUY_PRESSURE_NEAR_PCT,
        NEAR_SUPPORT_B_MAX_BELOW_PCT,
        NEAR_SUPPORT_B_MIN_STRENGTH,
        NEAR_SUPPORT_MAX_BELOW_PCT,
        NEAR_SUPPORT_PREF_MIN_STRENGTH,
        PATTERN_LOWER_FAR_PCT,
        TARGET_MIN_UPSIDE_PCT,
        _hit_bounds,
        _hit_box_bounds,
        _hit_close,
        _iter_confluence_supports,
        _level_far_below,
        _pick_near_strong_support,
        _pick_near_support_floor_far,
        _pressing_resistance_for_buy,
        _target_thin_upside,
        build_pattern_tactical,
        market_snapshot_from_bars,
        measured_target,
    )

    code = "603186"
    asof = "2026-08-13"
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
                        "box_low": lv.get("box_low"),
                        "box_high": lv.get("box_high"),
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

        close = None
        if bars:
            close = float(bars[-1].get("close") or 0) or None

        print("=== constants ===")
        print(
            json.dumps(
                {
                    "NEAR_SUPPORT_PREF_MIN_STRENGTH": NEAR_SUPPORT_PREF_MIN_STRENGTH,
                    "NEAR_SUPPORT_MAX_BELOW_PCT": NEAR_SUPPORT_MAX_BELOW_PCT,
                    "NEAR_SUPPORT_B_MIN_STRENGTH": NEAR_SUPPORT_B_MIN_STRENGTH,
                    "NEAR_SUPPORT_B_MAX_BELOW_PCT": NEAR_SUPPORT_B_MAX_BELOW_PCT,
                    "PATTERN_LOWER_FAR_PCT": PATTERN_LOWER_FAR_PCT,
                    "TARGET_MIN_UPSIDE_PCT": TARGET_MIN_UPSIDE_PCT,
                    "BUY_PRESSURE_MIN_STRENGTH": BUY_PRESSURE_MIN_STRENGTH,
                    "BUY_PRESSURE_NEAR_PCT": BUY_PRESSURE_NEAR_PCT,
                },
                ensure_ascii=False,
            )
        )

        if isinstance(confluence, dict):
            ns = confluence.get("nearest_support_zone")
            nr = confluence.get("nearest_resistance_zone")
            print("nearest_support_zone=", json.dumps(ns, ensure_ascii=False, default=str))
            print("nearest_resistance_zone=", json.dumps(nr, ensure_ascii=False, default=str))
            supports = confluence.get("supports") or []
            resistances = confluence.get("resistances") or []
            print(f"supports_n={len(supports)} resistances_n={len(resistances)}")
            print("--- all supports (with distance) ---")
            for z in _iter_confluence_supports(confluence):
                center = z.get("center")
                hi = z.get("high")
                strength = z.get("strength")
                ref = center if center is not None else hi
                below_pct = None
                if close and ref is not None:
                    below_pct = (close - float(ref)) / close
                print(
                    json.dumps(
                        {
                            "center": center,
                            "low": z.get("low"),
                            "high": hi,
                            "strength": strength,
                            "below_pct": round(below_pct, 4) if below_pct is not None else None,
                            "pass_strength": (strength or 0) >= NEAR_SUPPORT_PREF_MIN_STRENGTH,
                            "pass_below_6pct": (
                                below_pct is not None
                                and 0 < below_pct <= NEAR_SUPPORT_MAX_BELOW_PCT
                            ),
                            "center_lt_close": center is not None and float(center) < close
                            if close
                            else None,
                            "high_lt_close": hi is not None and float(hi) < close
                            if close
                            else None,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )
            print("--- resistances top5 ---")
            for z in resistances[:5]:
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "methods": z.get("methods"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )

        near_zone = _pick_near_strong_support(confluence, close)
        near_floor_far = _pick_near_support_floor_far(confluence, close)
        press_buy = _pressing_resistance_for_buy(confluence, close)
        print("picked_near_zone_A=", json.dumps(near_zone, ensure_ascii=False, default=str))
        print("picked_near_zone_floor_far=", json.dumps(near_floor_far, ensure_ascii=False, default=str))
        print("press_buy=", json.dumps(press_buy, ensure_ascii=False, default=str))

        tactical = build_pattern_tactical(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
            asof=asof_s,
            market=market_snapshot_from_bars(bars) if bars else None,
        )

        primary = None
        # re-classify path already inside build; recover primary via classify for diagnostics
        from backend_core.analysis.pattern_tactical import classify_short_bias

        classified = classify_short_bias(
            hits,
            confluence=confluence,
            vp=vp,
            rpe=rpe,
            invalidated_count=inv_n,
            asof=asof_s,
            market=market_snapshot_from_bars(bars) if bars else None,
        )
        primary = classified.get("primary")
        if primary:
            upper, lower = _hit_bounds(primary)
            box_lo, box_hi = _hit_box_bounds(primary)
            pclose = _hit_close(primary) or close
            pattern_floor = box_lo if box_lo is not None else lower
            primary_tgt = box_hi if box_hi is not None else (
                upper if upper is not None else measured_target(primary)
            )
            print("=== primary / gate flags ===")
            print(
                json.dumps(
                    {
                        "pattern_type": primary.get("pattern_type"),
                        "status": primary.get("status"),
                        "confidence": primary.get("confidence"),
                        "close": pclose,
                        "upper": upper,
                        "lower": lower,
                        "box_lo": box_lo,
                        "box_hi": box_hi,
                        "pattern_floor": pattern_floor,
                        "primary_tgt": primary_tgt,
                        "floor_far": _level_far_below(pclose, pattern_floor),
                        "thin_rr": _target_thin_upside(pclose, primary_tgt),
                        "near_zone_ok": near_floor_far is not None,
                        "press_buy_ok": press_buy is not None,
                        "pressure_zone": classified.get("pressure_zone"),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )

        print("=== tactical summary ===")
        print(
            json.dumps(
                {
                    "short_bias": tactical.get("short_bias"),
                    "bias_label": tactical.get("bias_label"),
                    "grade": tactical.get("grade"),
                    "confidence": tactical.get("confidence"),
                    "rationale": tactical.get("rationale"),
                    "risk_note": tactical.get("risk_note"),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        print("=== buy_hints ===")
        print(json.dumps(tactical.get("buy_hints"), ensure_ascii=False, indent=2, default=str))
        ev = [
            e
            for e in (tactical.get("evidence") or [])
            if isinstance(e, dict)
            and e.get("code")
            in ("near_support_pref", "resonance_pressure", "approaching_pressure")
        ]
        print("key evidence=", json.dumps(ev, ensure_ascii=False, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
