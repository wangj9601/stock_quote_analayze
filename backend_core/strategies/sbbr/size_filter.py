"""做小：市值过滤。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def calc_mv_yi(shares: Optional[float], close: Optional[float]) -> Optional[float]:
    """股本(股) × 收盘价 → 亿元。"""
    if shares is None or close is None:
        return None
    try:
        s = float(shares)
        c = float(close)
    except (TypeError, ValueError):
        return None
    if s <= 0 or c <= 0:
        return None
    return s * c / 1e8


def evaluate_size(
    *,
    total_shares: Optional[float],
    free_float_shares: Optional[float],
    close: Optional[float],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    size_cfg = (config or {}).get("size") or {}
    total_mv = calc_mv_yi(total_shares, close)
    circ_mv = calc_mv_yi(free_float_shares, close)

    unknown = total_mv is None and circ_mv is None
    exclude_unknown = bool(size_cfg.get("exclude_unknown_size", True))
    require_shares = bool(size_cfg.get("require_shares", True))

    if unknown:
        return {
            "size_ok": False if (exclude_unknown or require_shares) else None,
            "total_mv": None,
            "circ_mv": None,
            "size_reason": "unknown_shares",
        }

    t_min = float(size_cfg.get("total_mv_min_yi", 20))
    t_max = float(size_cfg.get("total_mv_max_yi", 200))
    c_min = float(size_cfg.get("circ_mv_min_yi", 5))
    c_max = float(size_cfg.get("circ_mv_max_yi", 10))

    total_ok = total_mv is not None and t_min <= total_mv <= t_max
    circ_ok = circ_mv is not None and c_min <= circ_mv <= c_max
    # 流通市值缺省时仅看总市值；总市值缺省时仅看流通
    if total_mv is None:
        size_ok = circ_ok
        reason = "circ_only"
    elif circ_mv is None:
        size_ok = total_ok
        reason = "total_only"
    else:
        size_ok = total_ok and circ_ok
        reason = "ok" if size_ok else "out_of_range"

    return {
        "size_ok": bool(size_ok),
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "size_reason": reason,
    }
