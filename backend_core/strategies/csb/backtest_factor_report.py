# -*- coding: utf-8 -*-
"""CSB 回测：因子分桶与 hit_rate 对照（简化版）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


PART_SCORE_FIELDS: List[Tuple[str, str, str]] = [
    ("squeeze_days", "f_squeeze_days", "粘合天数"),
    ("squeeze_pct", "f_squeeze_pct", "粘合带宽"),
    ("touch_count", "f_touch_count", "回踩次数"),
    ("vol_expand_mult", "f_vol_expand", "放量倍数"),
    ("vol_ratio_5_20", "f_vol_ratio_5_20", "5/20量比"),
]

RAW_HEADER_ZH: Dict[str, str] = {
    "squeeze_days": "粘合天数",
    "squeeze_pct": "粘合带宽(%)",
    "touch_count": "回踩次数",
    "vol_expand_mult": "放量倍数",
    "channel_upper": "通道上轨",
    "channel_lower": "通道下轨",
    "horizon_pnl_pct": "满观察期盈亏(%)",
    "horizon_exit_price": "满观察期收盘",
}


def _f(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def flatten_score_factors(sig: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    sig = sig if isinstance(sig, dict) else {}
    out: Dict[str, Any] = {}
    for src, col, _ in PART_SCORE_FIELDS:
        val = sig.get(src)
        if val is None and isinstance(sig.get("detail"), dict):
            setup = sig["detail"].get("setup") or {}
            ch = setup.get("channel") or {}
            val = ch.get(src) if src in ch else setup.get(src)
        out[col] = _round(_f(val), 4) if col.startswith("f_") else val
    out["squeeze_days"] = sig.get("squeeze_days")
    out["squeeze_pct"] = _round(_f(sig.get("squeeze_pct")), 4)
    out["touch_count"] = sig.get("touch_count")
    out["vol_expand_mult"] = _round(_f(sig.get("vol_expand_mult")), 4)
    out["channel_upper"] = _round(_f(sig.get("channel_upper")), 4)
    out["channel_lower"] = _round(_f(sig.get("channel_lower")), 4)
    return out


def _round(v: Optional[float], n: int = 4) -> Optional[float]:
    if v is None:
        return None
    return round(v, n)


def attach_horizon_metrics(row: Dict[str, Any], future: Sequence[Dict[str, Any]], entry_price: float) -> Dict[str, Any]:
    if not future or not entry_price:
        return row
    last = future[-1]
    close = last.get("close") or last.get("open")
    try:
        px = float(close) if close is not None else None
    except (TypeError, ValueError):
        px = None
    if px is None or px <= 0:
        return row
    row["horizon_exit_price"] = round(px, 4)
    row["horizon_pnl_pct"] = round((px / float(entry_price) - 1.0) * 100.0, 2)
    return row


def enrich_detail_with_factors(
    row: Dict[str, Any],
    sig: Optional[Dict[str, Any]],
    future: Sequence[Dict[str, Any]],
    entry_price: float,
) -> Dict[str, Any]:
    row.update(flatten_score_factors(sig))
    attach_horizon_metrics(row, future, entry_price)
    return row


def _metrics_for_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    if not n:
        return {"total": 0, "hit": 0, "hit_rate": 0.0, "win_count": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0, "avg_max_gain_pct": 0.0}
    hits = sum(1 for r in rows if r.get("hit_target"))
    wins = sum(1 for r in rows if (_f(r.get("pnl_pct")) or 0) > 0)
    return {
        "total": n,
        "hit": hits,
        "hit_rate": round(hits / n, 4),
        "win_count": wins,
        "win_rate": round(wins / n, 4),
        "avg_pnl_pct": round(sum(_f(r.get("pnl_pct")) or 0 for r in rows) / n, 2),
        "avg_max_gain_pct": round(sum(_f(r.get("max_gain_pct")) or 0 for r in rows) / n, 2),
    }


def assign_score_buckets(details: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in details:
        sv = _f(r.get("score"))
        if sv is None:
            bucket = "未知"
        elif sv < 60:
            bucket = "[0,60)"
        elif sv < 70:
            bucket = "[60,70)"
        elif sv < 80:
            bucket = "[70,80)"
        elif sv < 90:
            bucket = "[80,90)"
        else:
            bucket = "[90,100]"
        grouped.setdefault(bucket, []).append(r)
    return {name: _metrics_for_rows(rows) for name, rows in grouped.items()}


_FACTOR_BIN_SPECS = [
    ("squeeze_days", "粘合天数", [(None, 15.0, "<15"), (15.0, 20.0, "[15,20)"), (20.0, None, "≥20")]),
    ("f_vol_expand", "放量倍数", [(None, 2.0, "<2"), (2.0, 2.5, "[2,2.5)"), (2.5, None, "≥2.5")]),
    ("touch_count", "回踩次数", [(None, 2.0, "<2"), (2.0, 3.0, "[2,3)"), (3.0, None, "≥3")]),
]


def _bin_value(v: Optional[float], edges) -> Optional[str]:
    if v is None:
        return None
    for lo, hi, label in edges:
        if lo is not None and v < lo:
            continue
        if hi is not None and v >= hi:
            continue
        return label
    return None


def build_factor_buckets(details: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for field, label, edges in _FACTOR_BIN_SPECS:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in details:
            name = _bin_value(_f(r.get(field)), edges)
            if name:
                grouped.setdefault(name, []).append(r)
        if grouped:
            out[field] = {
                "label": label,
                "field": field,
                "bins": [{"bucket": k, **_metrics_for_rows(v)} for k, v in grouped.items()],
            }
    return out


def build_hit_rate_compare(details: Sequence[Dict[str, Any]], exit_mode: str) -> Dict[str, Any]:
    n = len(details)
    m = _metrics_for_rows(details)
    hz = [_f(r.get("horizon_pnl_pct")) for r in details]
    hz_ok = [v for v in hz if v is not None]
    return {
        "sample": "same_trades",
        "exit_mode": exit_mode,
        "total": n,
        "hit_count": m["hit"],
        "hit_rate": m["hit_rate"],
        "avg_max_gain_pct": m["avg_max_gain_pct"],
        "actual": {
            "win_count": m["win_count"],
            "win_rate": m["win_rate"],
            "avg_pnl_pct": m["avg_pnl_pct"],
        },
        "horizon_hold": {
            "avg_pnl_pct": round(sum(hz_ok) / len(hz_ok), 2) if hz_ok else None,
            "coverage": len(hz_ok),
        },
    }
