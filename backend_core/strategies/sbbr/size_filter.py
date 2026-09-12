"""做小：总市值 / 流通股本过滤（默认任一满足即通过）。"""

from __future__ import annotations

from typing import Any, Dict, Optional


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


def calc_shares_yi(shares: Optional[float]) -> Optional[float]:
    """股本(股) → 亿股。"""
    if shares is None:
        return None
    try:
        s = float(shares)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    return s / 1e8


def _parse_optional_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def evaluate_size(
    *,
    total_shares: Optional[float],
    free_float_shares: Optional[float],
    close: Optional[float],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """做小过滤：默认总市值 OR 流通股本任一达标即通过。

    - 总市值：`total_mv`（亿元），默认 20~300
    - 流通股本：`circ_shares_yi`（亿股），默认 **大于** 5（无上限）
    - `match_mode`：`any`（默认，OR）/ `all`（AND）
    - `circ_mv`（流通市值亿元）仅作展示，不参与默认过滤
    """
    size_cfg = (config or {}).get("size") or {}
    total_mv = calc_mv_yi(total_shares, close)
    circ_mv = calc_mv_yi(free_float_shares, close)
    circ_shares_yi = calc_shares_yi(free_float_shares)

    unknown = total_mv is None and circ_shares_yi is None
    exclude_unknown = bool(size_cfg.get("exclude_unknown_size", True))
    require_shares = bool(size_cfg.get("require_shares", True))

    if unknown:
        return {
            "size_ok": False if (exclude_unknown or require_shares) else None,
            "total_mv": None,
            "circ_mv": None,
            "circ_shares_yi": None,
            "size_reason": "unknown_shares",
        }

    t_min = float(size_cfg.get("total_mv_min_yi", 20))
    t_max = float(size_cfg.get("total_mv_max_yi", 300))
    s_min = float(size_cfg.get("circ_shares_min_yi", 5))
    s_max = _parse_optional_float(size_cfg.get("circ_shares_max_yi"))
    match_mode = str(size_cfg.get("match_mode") or "any").strip().lower()
    if match_mode not in ("any", "all"):
        match_mode = "any"

    total_ok = total_mv is not None and t_min <= total_mv <= t_max
    if circ_shares_yi is None:
        shares_ok = False
    elif s_max is None:
        shares_ok = circ_shares_yi > s_min
    else:
        shares_ok = s_min < circ_shares_yi <= s_max

    # 单侧缺数时只看有值侧；双侧都有时按 match_mode
    if total_mv is None:
        size_ok = shares_ok
        reason = "circ_shares_only"
    elif circ_shares_yi is None:
        size_ok = total_ok
        reason = "total_only"
    elif match_mode == "all":
        size_ok = total_ok and shares_ok
        reason = "ok" if size_ok else "out_of_range"
    else:
        size_ok = total_ok or shares_ok
        if size_ok:
            if total_ok and shares_ok:
                reason = "ok"
            elif total_ok:
                reason = "total_ok"
            else:
                reason = "circ_shares_ok"
        else:
            reason = "out_of_range"

    return {
        "size_ok": bool(size_ok),
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "circ_shares_yi": circ_shares_yi,
        "size_reason": reason,
    }
