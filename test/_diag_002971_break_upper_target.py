# -*- coding: utf-8 -*-
"""诊断 002971 和远气体：break_upper 目标为何锚到形态上沿而非更远共振阻力。"""
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
        _break_level_from_resistance,
        _farther_resistance_target,
        _hit_bounds,
        _hit_box_bounds,
        _hit_close,
        _iter_confluence_resistances,
        _iter_confluence_supports,
        _level_far_below,
        _pick_near_support_floor_far,
        _pressing_resistance_for_buy,
        _resolve_break_upper_target,
        _resolve_watch_target,
        _target_thin_upside,
        build_pattern_tactical,
        market_snapshot_from_bars,
        measured_target,
    )

    code = "002971"
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

        print(f"code={code} asof={asof_s} bars={len(bars)} hits={len(hits)} inv={inv_n}")
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
            print("=== resistances ===")
            for z in _iter_confluence_resistances(confluence):
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "labels": z.get("labels") or z.get("methods"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )
            print("=== supports ===")
            for z in _iter_confluence_supports(confluence):
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "labels": z.get("labels") or z.get("methods"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )
            nz = confluence.get("nearest_resistance_zone")
            print("nearest_resistance_zone=", json.dumps(nz, ensure_ascii=False, default=str))

        snap = market_snapshot_from_bars(bars) if bars else None
        tactical = build_pattern_tactical(
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
                    "short_bias": tactical.get("short_bias"),
                    "bias_label": tactical.get("bias_label"),
                    "grade": tactical.get("grade"),
                    "confidence": tactical.get("confidence"),
                    "rationale": tactical.get("rationale"),
                    "risk_note": tactical.get("risk_note"),
                    "buy_hints": tactical.get("buy_hints"),
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
        if isinstance(confluence, dict):
            raw_r = confluence.get("resistances") or []
            print(f"=== raw resistances count={len(raw_r)} ===")
            for z in raw_r:
                if not isinstance(z, dict):
                    continue
                print(
                    json.dumps(
                        {
                            "center": z.get("center"),
                            "low": z.get("low"),
                            "high": z.get("high"),
                            "strength": z.get("strength"),
                            "labels": z.get("labels") or z.get("methods"),
                            "sources": z.get("sources"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )

        # 复现 break_upper 目标选取路径
        primary = None
        for h in hits or []:
            if isinstance(h, dict) and h.get("status") in (None, "forming", "confirmed"):
                primary = h
                break
        if primary is None and hits:
            primary = hits[0] if isinstance(hits[0], dict) else None

        upper = lower = None
        if primary:
            upper, lower = _hit_bounds(primary)
        box_lo, box_hi = _hit_box_bounds(primary) if primary else (None, None)
        pattern_floor = box_lo if box_lo is not None else lower
        floor_far = _level_far_below(close, pattern_floor)
        primary_tgt = box_hi if box_hi is not None else (upper if upper is not None else None)
        thin_rr = _target_thin_upside(close, primary_tgt)
        watch_tgt = _resolve_watch_target(close, primary_tgt, confluence, upper)
        press_buy = _pressing_resistance_for_buy(confluence, close)
        near_main = _pick_near_support_floor_far(confluence, close)

        break_px = None
        if press_buy is not None:
            break_px = _break_level_from_resistance(press_buy)
            if break_px is None and upper is not None:
                break_px = upper

        u_pref = upper if upper is not None else primary_tgt
        new_bu = None
        if break_px is not None:
            new_bu = _resolve_break_upper_target(
                confluence,
                close,
                break_px=break_px,
                upper=upper,
                primary_tgt=primary_tgt,
            )
        farther = None
        if break_px is not None:
            farther = _farther_resistance_target(
                confluence, close, above=break_px, upper=upper or primary_tgt
            )

        print("=== break_upper path ===")
        print(
            json.dumps(
                {
                    "close": close,
                    "upper": upper,
                    "lower": lower,
                    "box_lo": box_lo,
                    "box_hi": box_hi,
                    "pattern_floor": pattern_floor,
                    "floor_far": floor_far,
                    "floor_far_pct": (
                        (close - pattern_floor) / close
                        if close and pattern_floor
                        else None
                    ),
                    "primary_tgt": primary_tgt,
                    "thin_rr": thin_rr,
                    "watch_tgt": watch_tgt,
                    "press_buy": press_buy,
                    "near_main": near_main,
                    "break_px": break_px,
                    "u_pref": u_pref,
                    "resolved_break_upper_target": new_bu,
                    "farther_resistance_target": farther,
                    "measured": measured_target(primary) if primary else None,
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
