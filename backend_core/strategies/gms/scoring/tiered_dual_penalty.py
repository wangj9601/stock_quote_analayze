"""
增强版打分：标准阶梯分 + 可配置减分项。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import GMSIndicators
from .penalties import PenaltyEngine
from .tiered_dual_max import TieredDualMaxScorer

MECHANISM_ID = "tiered_dual_penalty"


class TieredDualPenaltyScorer:
    """GMS 增强版：基础分后减分。"""

    mechanism_id = MECHANISM_ID

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._base = TieredDualMaxScorer(self.config)
        self._penalty_engine = PenaltyEngine(self.config)

    def calculate(
        self,
        row: Dict[str, Any],
        instant_deviation_series: Optional[List[float]] = None,
    ) -> Optional[GMSIndicators]:
        ind = self._base.calculate(row, instant_deviation_series)
        if ind is None:
            return None
        base_total = float(ind.score_total)
        deduction, details = self._penalty_engine.apply(row)
        final_total = max(0.0, min(100.0, base_total - deduction))
        ind.score_base_total = base_total
        ind.score_penalty_deduction = deduction
        ind.penalty_details = details
        ind.score_total = final_total
        ind.scoring_mechanism = MECHANISM_ID
        return ind

    def __getattr__(self, name: str):
        return getattr(self._base, name)
