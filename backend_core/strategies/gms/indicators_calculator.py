"""
GMS 指标计算器（门面）
按 scoring.mechanism 分发至具体打分实现。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import GMSIndicators
from .scoring import get_mechanism
from .scoring._helpers import resolve_mechanism_id

logger = logging.getLogger(__name__)


class GMSIndicatorsCalculator:
    """GMS 指标与阶梯式评分计算（门面）。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        mechanism_id = resolve_mechanism_id(self.config)
        try:
            scorer_cls = get_mechanism(mechanism_id)
            self._scorer = scorer_cls(self.config)
        except ValueError as e:
            logger.warning("GMS 打分机制无效 %s，回退标准版: %s", mechanism_id, e)
            self._scorer = get_mechanism("tiered_dual_max")(self.config)
        self._base = getattr(self._scorer, "_base", self._scorer)

    def calculate(
        self,
        row: Dict[str, Any],
        instant_deviation_series: Optional[List[float]] = None,
    ) -> Optional[GMSIndicators]:
        return self._scorer.calculate(row, instant_deviation_series)

    def __getattr__(self, name: str):
        return getattr(self._base, name)
