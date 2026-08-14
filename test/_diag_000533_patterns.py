# -*- coding: utf-8 -*-
"""诊断 000533 asof=2026-08-13/14：detect_all_counted + 头肩斜颈外推。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def _dump_hits(hits, inv_n, asof_s, bars_n):
    print(f"\n===== asof={asof_s} bars={bars_n} hits={len(hits)} invalidated={inv_n} =====")
    for i, h in enumerate(hits, 1):
        lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
        print(
            json.dumps(
                {
                    "i": i,
                    "type": h.get("pattern_type"),
                    "status": h.get("status"),
                    "confidence": h.get("confidence"),
                    "formed_at": h.get("formed_at"),
                    "key_levels": lv,
                    "pivots": h.get("pivots"),
                    "reason": h.get("reason"),
                },
                ensure_ascii=False,
                default=str,
            )
        )


def _diag_hs_neck(bars):
    from backend_core.analysis.chart_patterns.pivots import extract_pivot_sequence
    from backend_core.analysis.chart_patterns.head_shoulders import (
        _detect_hs_top,
        _neck_at,
        _pivot_bar_index,
    )

    piv = extract_pivot_sequence(bars)
    top = _detect_hs_top(piv, bars)
    if not top:
        print("\n=== HS TOP: none ===")
        return
    lv = top.get("key_levels") or {}
    pivots = top.get("pivots") or []
    n1 = next((p for p in pivots if p.get("role") == "neck1"), None)
    n2 = next((p for p in pivots if p.get("role") == "neck2"), None)
    if not n1 or not n2:
        print("\n=== HS TOP: missing neck pivots ===")
        return
    # rebuild indices from full pivot list matching prices/dates
    n1_full = None
    n2_full = None
    for p in piv:
        if (
            n1_full is None
            and p.get("kind") == "low"
            and abs(float(p["price"]) - float(n1["price"])) < 1e-6
            and str(p.get("date") or "")[:10] == str(n1.get("date") or "")[:10]
        ):
            n1_full = p
        if (
            n2_full is None
            and p.get("kind") == "low"
            and abs(float(p["price"]) - float(n2["price"])) < 1e-6
            and str(p.get("date") or "")[:10] == str(n2.get("date") or "")[:10]
        ):
            n2_full = p
    n1_i = _pivot_bar_index(bars, n1_full or n1)
    n2_i = _pivot_bar_index(bars, n2_full or n2)
    last_i = len(bars) - 1
    n1_px = float(n1["price"])
    n2_px = float(n2["price"])
    neck_last = _neck_at(n1_px, n1_i, n2_px, n2_i, last_i)
    # slope per bar
    slope = (n2_px - n1_px) / (n2_i - n1_i) if n2_i != n1_i else 0.0
    bars_after_n2 = last_i - n2_i
    # when does neck cross 0?
    zero_i = None
    if slope != 0:
        # n1 + t*(n2-n1) = 0 => t = -n1/(n2-n1); i = n1_i + t*(n2_i-n1_i)
        t0 = -n1_px / (n2_px - n1_px)
        zero_i = n1_i + t0 * (n2_i - n1_i)

    print("\n=== HS NECK DIAG ===")
    print(
        json.dumps(
            {
                "status": top.get("status"),
                "confidence": top.get("confidence"),
                "neckline_disp": lv.get("neckline"),
                "neck_left": n1_px,
                "neck_right": n2_px,
                "n1_date": n1.get("date"),
                "n2_date": n2.get("date"),
                "n1_i": n1_i,
                "n2_i": n2_i,
                "last_i": last_i,
                "last_date": bars[last_i].get("date") or bars[last_i].get("trade_date"),
                "last_close": lv.get("last_close"),
                "span_bars_n1_n2": n2_i - n1_i,
                "bars_after_n2": bars_after_n2,
                "slope_per_bar": round(slope, 6),
                "neck_at_last": round(neck_last, 4),
                "zero_cross_bar_i": round(zero_i, 2) if zero_i is not None else None,
                "asymmetry_pct": round(abs(n1_px - n2_px) / ((n1_px + n2_px) / 2) * 100, 2),
                "pivots": pivots,
                "reason": top.get("reason"),
            },
            ensure_ascii=False,
            default=str,
        )
    )


def run_asof(db, code, asof_req, lookback=160):
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    adjust = normalize_price_adjust("qfq")
    asof_s = resolve_effective_trade_date(db, asof_req, market="CN")
    bars_map = batch_load_ohlc_asc(db, [code], lookback=lookback, asof=asof_s)
    bars = bars_map.get(code) or []
    if adjust == "qfq" and bars:
        bars, _ = apply_qfq_to_code_bars(db, code, bars)
    hits, inv_n = detect_all_counted(
        bars, types=None, include_invalidated=True
    ) if len(bars) >= 30 else ([], 0)
    print(f"\n# req={asof_req} -> effective={asof_s}")
    if bars:
        print(
            f"first={bars[0].get('date') or bars[0].get('trade_date')} "
            f"last={bars[-1].get('date') or bars[-1].get('trade_date')} "
            f"C={bars[-1].get('close')}"
        )
    _dump_hits(hits, inv_n, asof_s, len(bars))
    _diag_hs_neck(bars)
    return asof_s, hits, bars


def main() -> int:
    from backend_api.database import SessionLocal

    code = "000533"
    db = SessionLocal()
    try:
        for asof in ("2026-08-13", "2026-08-14"):
            run_asof(db, code, asof)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
