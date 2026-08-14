# -*- coding: utf-8 -*-
"""诊断 002300 太阳电缆 asof≈2026-08-13/14：形态 + tactical + Camarilla。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

OUT = Path(__file__).resolve().parent / "_diag_002300_out.txt"


def _brief(reason, max_len: int = 160) -> str:
    if reason is None:
        return ""
    if isinstance(reason, (dict, list)):
        s = json.dumps(reason, ensure_ascii=False, default=str)
    else:
        s = str(reason)
    s = " ".join(s.split())
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def run_asof(db, code: str, asof_req: str, lookback: int = 220):
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.analysis.classic_levels import compute_classic_levels_from_bars
    from backend_core.analysis.pattern_tactical import (
        build_pattern_tactical,
        market_snapshot_from_bars,
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

    hits, inv_n = (
        detect_all_counted(bars, types=None, include_invalidated=True)
        if len(bars) >= 30
        else ([], 0)
    )

    lines = []
    lines.append(f"# code={code} req={asof_req} -> effective={asof_s} adjust={adjust}")
    if bars:
        last = bars[-1]
        lines.append(
            f"first={bars[0].get('date') or bars[0].get('trade_date')} "
            f"last={last.get('date') or last.get('trade_date')} "
            f"C={last.get('close')} bars={len(bars)}"
        )

    for i, h in enumerate(hits, 1):
        lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
        lines.append(
            json.dumps(
                {
                    "i": i,
                    "type": h.get("pattern_type"),
                    "status": h.get("status"),
                    "confidence": h.get("confidence"),
                    "formed_at": h.get("formed_at") or h.get("confirm_date"),
                    "neckline": lv.get("neckline"),
                    "last_close": lv.get("last_close"),
                    "reason": _brief(h.get("reason")),
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
        lines.append(f"ENRICH_ERR {type(e).__name__}: {e}")

    tactical = build_pattern_tactical(
        hits,
        confluence=confluence,
        vp=vp,
        rpe=rpe,
        invalidated_count=inv_n,
        asof=asof_s,
        market=market_snapshot_from_bars(bars) if bars else None,
    )
    lines.append("=== TACTICAL ===")
    lines.append(json.dumps(tactical, ensure_ascii=False, indent=2, default=str))

    classic = None
    try:
        classic = compute_classic_levels_from_bars(bars)
        cam = (classic or {}).get("camarilla") if isinstance(classic, dict) else None
        lines.append("=== CAMARILLA ===")
        lines.append(json.dumps(cam, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        lines.append(f"CLASSIC_ERR {type(e).__name__}: {e}")

    text = "\n".join(lines)
    print(text)
    return text, asof_s, hits, tactical, classic


def main() -> int:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    chunks = []
    try:
        for asof in ("2026-08-13", "2026-08-14"):
            text, *_ = run_asof(db, "002300", asof)
            chunks.append(text)
            chunks.append("")
        OUT.write_text("\n".join(chunks), encoding="utf-8")
        print("WROTE", OUT)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
