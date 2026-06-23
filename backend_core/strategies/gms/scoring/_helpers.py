"""打分模块共用工具。"""

from typing import Any, Optional


def safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def resolve_mechanism_id(config: Optional[dict]) -> str:
    scoring = (config or {}).get("scoring") or {}
    mid = (scoring.get("mechanism") or "").strip()
    if not mid:
        return "tiered_dual_max"
    return mid
