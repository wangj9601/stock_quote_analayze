# -*- coding: utf-8 -*-
"""标准化形态命中结构。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# 展示/入库口径：元，两位小数（与 classic_levels / confluence 一致）
PRICE_DECIMALS = 2

_PRICE_LEVEL_KEYS = frozenset(
    {
        "neckline",
        "upper",
        "lower",
        "mid",
        "head",
        "l1",
        "l2",
        "h1",
        "h2",
        "last_close",
    }
)


def _norm_date(v: Any) -> str:
    if v is None or v == "":
        return ""
    return str(v)[:10]


def round_px(price: Any) -> Optional[float]:
    """价格两位小数；无法解析则返回 None。"""
    try:
        x = float(price)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return round(x, PRICE_DECIMALS)


def fmt_px(label: str, price: Any, date: Any = None, *, approx: bool = False) -> str:
    """价位说明片段：左肩=44.97(2026-03-12)；无日期则不加括号。"""
    eq = "≈" if approx else "="
    px = round_px(price)
    px_s = f"{px:.{PRICE_DECIMALS}f}" if px is not None else str(price)
    s = f"{label}{eq}{px_s}"
    d = _norm_date(date)
    return f"{s}({d})" if d else s


def _normalize_key_levels(levels: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not levels:
        return {}
    out = dict(levels)
    for k in _PRICE_LEVEL_KEYS:
        if k not in out or out[k] is None or out[k] == "":
            continue
        rounded = round_px(out[k])
        if rounded is not None:
            out[k] = rounded
    return out


def _normalize_pivots(pivots: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in pivots or []:
        if not isinstance(p, dict):
            continue
        item = dict(p)
        if "price" in item and item["price"] is not None and item["price"] != "":
            rounded = round_px(item["price"])
            if rounded is not None:
                item["price"] = rounded
        out.append(item)
    return out

def _key_dates_from_pivots(pivots: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for p in pivots or []:
        if not isinstance(p, dict):
            continue
        d = _norm_date(p.get("date"))
        if not d:
            continue
        out.append({"role": str(p.get("role") or ""), "date": d})
    return out


def _derive_formed_at(
    pivots: Optional[List[Dict[str, Any]]],
    *,
    confirm_date: Any = None,
    formed_at: Any = None,
) -> str:
    """形成/关键日：优先显式 formed_at → 确认/突破日 → 枢轴中最晚日期。"""
    explicit = _norm_date(formed_at)
    if explicit:
        return explicit
    confirm = _norm_date(confirm_date)
    if confirm:
        return confirm
    dates = [kd["date"] for kd in _key_dates_from_pivots(pivots)]
    return max(dates) if dates else ""


def make_hit(
    *,
    pattern_family: str,
    pattern_type: str,
    status: str,
    confidence: float,
    reason: str,
    key_levels: Optional[Dict[str, Any]] = None,
    pivots: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conf = max(0.0, min(1.0, float(confidence)))
    piv = _normalize_pivots(pivots)
    allowed = ("forming", "confirmed", "invalidated", "archived")
    hit: Dict[str, Any] = {
        "pattern_family": pattern_family,
        "pattern_type": pattern_type,
        "status": status if status in allowed else "forming",
        "confidence": round(conf, 3),
        "reason": reason or "",
        "key_levels": _normalize_key_levels(key_levels),
        "pivots": piv,
    }
    if extra:
        hit.update(extra)
    hit["key_dates"] = hit.get("key_dates") or _key_dates_from_pivots(hit.get("pivots"))
    hit["formed_at"] = _derive_formed_at(
        hit.get("pivots"),
        confirm_date=hit.get("confirm_date"),
        formed_at=hit.get("formed_at"),
    )
    return hit
