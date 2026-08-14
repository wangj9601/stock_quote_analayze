# -*- coding: utf-8 -*-
"""诊断 002286 保龄宝 asof≈2026-08-13/14：detect_all_counted + tactical。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def _reason_brief(reason, max_len: int = 180) -> str:
    if reason is None:
        return ""
    if isinstance(reason, (dict, list)):
        s = json.dumps(reason, ensure_ascii=False, default=str)
    else:
        s = str(reason)
    s = " ".join(s.split())
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


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
                    "formed_at": h.get("formed_at") or h.get("confirm_date"),
                    "key_levels": lv,
                    "reason": _reason_brief(h.get("reason")),
                },
                ensure_ascii=False,
                default=str,
            )
        )


def _check_hs(hits, bars, asof_s):
    """头肩：颈线是否为正、forming 是否陈旧。"""
    from backend_core.analysis.chart_patterns.head_shoulders import (
        _neck_at,
        _pivot_bar_index,
    )

    hs_hits = [
        h
        for h in hits
        if str(h.get("pattern_type") or "")
        in ("hs", "hs_top", "hs_bottom", "head_shoulders", "inverse_hs")
        or "hs" in str(h.get("pattern_type") or "").lower()
        or "头肩" in str(h.get("pattern_type") or "")
    ]
    # 更稳妥：按 type 字段常见命名
    hs_hits = [
        h
        for h in hits
        if str(h.get("pattern_type") or "")
        in ("hs", "ihs", "head_shoulders_top", "head_shoulders_bottom")
        or str(h.get("pattern_type") or "").startswith("hs")
        or str(h.get("pattern_type") or "").startswith("ihs")
    ]
    if not hs_hits:
        # fallback: look for neckline in key_levels + pivots with head role
        hs_hits = [
            h
            for h in hits
            if isinstance(h.get("key_levels"), dict)
            and "neckline" in (h.get("key_levels") or {})
            and any(
                (p or {}).get("role") in ("head", "left_shoulder", "right_shoulder", "neck1", "neck2")
                for p in (h.get("pivots") or [])
            )
        ]

    print(f"\n=== HS CHECK asof={asof_s} count={len(hs_hits)} ===")
    if not hs_hits:
        print("no head-shoulders hits")
        return

    last_i = len(bars) - 1
    last_date = None
    if bars:
        last_date = bars[-1].get("date") or bars[-1].get("trade_date")

    for i, h in enumerate(hs_hits, 1):
        lv = h.get("key_levels") if isinstance(h.get("key_levels"), dict) else {}
        neck = lv.get("neckline")
        neck_f = None
        try:
            neck_f = float(neck) if neck is not None else None
        except (TypeError, ValueError):
            neck_f = None

        pivots = h.get("pivots") or []
        n1 = next((p for p in pivots if p.get("role") == "neck1"), None)
        n2 = next((p for p in pivots if p.get("role") == "neck2"), None)
        formed_at = h.get("formed_at") or h.get("confirm_date")
        status = str(h.get("status") or "")

        neck_at_last = None
        n1_i = n2_i = None
        bars_after_formed = None
        if n1 and n2 and bars:
            try:
                n1_i = _pivot_bar_index(bars, n1)
                n2_i = _pivot_bar_index(bars, n2)
                n1_px = float(n1["price"])
                n2_px = float(n2["price"])
                neck_at_last = _neck_at(n1_px, n1_i, n2_px, n2_i, last_i)
            except Exception as e:
                neck_at_last = f"err:{type(e).__name__}:{e}"

        if formed_at and last_date:
            try:
                from datetime import datetime

                fa = datetime.strptime(str(formed_at)[:10], "%Y-%m-%d")
                ld = datetime.strptime(str(last_date)[:10], "%Y-%m-%d")
                bars_after_formed = (ld - fa).days  # calendar; bar count below
            except Exception:
                pass
        # bar-index lag: find formed_at bar
        formed_bar_lag = None
        if formed_at and bars:
            fa_s = str(formed_at)[:10]
            for bi, b in enumerate(bars):
                d = str(b.get("date") or b.get("trade_date") or "")[:10]
                if d == fa_s:
                    formed_bar_lag = last_i - bi
                    break

        print(
            json.dumps(
                {
                    "i": i,
                    "type": h.get("pattern_type"),
                    "status": status,
                    "confidence": h.get("confidence"),
                    "formed_at": formed_at,
                    "last_date": last_date,
                    "neckline_disp": neck,
                    "neckline_positive": (neck_f is not None and neck_f > 0),
                    "neck_at_last": round(neck_at_last, 4)
                    if isinstance(neck_at_last, float)
                    else neck_at_last,
                    "neck_at_last_positive": (
                        isinstance(neck_at_last, float) and neck_at_last > 0
                    ),
                    "n1": n1,
                    "n2": n2,
                    "n1_i": n1_i,
                    "n2_i": n2_i,
                    "forming_stale": status == "forming"
                    and (
                        (formed_bar_lag is not None and formed_bar_lag >= 10)
                        or (bars_after_formed is not None and bars_after_formed >= 14)
                    ),
                    "formed_bar_lag": formed_bar_lag,
                    "calendar_days_after_formed": bars_after_formed,
                    "reason": _reason_brief(h.get("reason")),
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
    from backend_core.analysis.pattern_tactical import (
        build_pattern_tactical,
        market_snapshot_from_bars,
    )

    adjust = normalize_price_adjust("qfq")
    asof_s = resolve_effective_trade_date(db, asof_req, market="CN")
    bars_map = batch_load_ohlc_asc(db, [code], lookback=lookback, asof=asof_s)
    bars = bars_map.get(code) or []
    adj_meta = None
    if adjust == "qfq" and bars:
        bars, adj_meta = apply_qfq_to_code_bars(db, code, bars)

    hits, inv_n = (
        detect_all_counted(bars, types=None, include_invalidated=True)
        if len(bars) >= 30
        else ([], 0)
    )

    print(f"\n# code={code} req={asof_req} -> effective={asof_s} adjust={adjust}")
    if bars:
        print(
            f"first={bars[0].get('date') or bars[0].get('trade_date')} "
            f"last={bars[-1].get('date') or bars[-1].get('trade_date')} "
            f"C={bars[-1].get('close')} bars={len(bars)}"
        )
    if adj_meta:
        print("adj_meta=", json.dumps(adj_meta, ensure_ascii=False, default=str))

    _dump_hits(hits, inv_n, asof_s, len(bars))
    _check_hs(hits, bars, asof_s)

    vp = confluence = rpe = None
    try:
        from backend_api.stock.pattern_routes import _tactical_enrichment

        vp, confluence, rpe, *_rest = _tactical_enrichment(db, bars, code, asof_s)
    except Exception as e:
        print("ENRICH_ERR", type(e).__name__, e)

    tactical = build_pattern_tactical(
        hits,
        confluence=confluence,
        vp=vp,
        rpe=rpe,
        invalidated_count=inv_n,
        asof=asof_s,
        market=market_snapshot_from_bars(bars) if bars else None,
    )
    print(f"\n=== TACTICAL asof={asof_s} (full) ===")
    print(json.dumps(tactical, ensure_ascii=False, indent=2, default=str))
    return asof_s, hits, bars, tactical


def main() -> int:
    from backend_api.database import SessionLocal

    code = "002286"
    db = SessionLocal()
    try:
        for asof in ("2026-08-13", "2026-08-14"):
            run_asof(db, code, asof)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
