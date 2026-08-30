"""IBD 风格股价相对强度（RS Rating）。"""

from .config import RS_WINDOWS, RS_WEIGHTS, PRICE_ADJUST, coverage_threshold, strength_label
from .calculator import (
    compute_rs_raw,
    percentile_to_rating,
    rank_cross_section,
    roc,
)

__all__ = [
    "RS_WINDOWS",
    "RS_WEIGHTS",
    "PRICE_ADJUST",
    "coverage_threshold",
    "strength_label",
    "compute_rs_raw",
    "percentile_to_rating",
    "rank_cross_section",
    "roc",
]
