"""
GMS 信号检测器
检测左侧买点（均值吸附）、右侧买点（动量引爆）、卖点
"""

import logging
from typing import Optional

from .models import GMSIndicators
from .interfaces import ISignalDetector

logger = logging.getLogger(__name__)


class GMSSignalDetector(ISignalDetector):
    """GMS 买点/卖点检测"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        left = self.config.get("left_buy", {})
        right = self.config.get("right_buy", {})
        exit_cfg = self.config.get("exit", {})
        self.ratio_d20_abs_max = float(left.get("ratio_d20_abs_max", 0.015))
        self.volume_ratio_max = float(left.get("volume_ratio_max", 0.8))
        # 可选：均值收敛态得分下限，0 表示不启用（收紧低分「左侧」信号）
        self.left_min_accumulation_score = float(left.get("min_accumulation_score", 0))
        self.volume_ratio_min = float(right.get("volume_ratio_min", 1.5))
        self.overbought_ratio = float(exit_cfg.get("overbought_ratio", 0.15))
        self.use_ratio_d_for_exit = self.config.get("ratio_indicators", {}).get("use_ratio_d_for_exit", False)

    def detect_left_buy(self, indicators: GMSIndicators) -> bool:
        """
        左侧买点（均值吸附）：
        - 优先用均值收敛态等级 S/A 判断
        - 前置：F > Z 且 d₂₀ < d₁（即 delta < 0）
        - 极度粘合：|Δ/d₂₀| < 1.5%
        - 地量洗盘：m₂₀ < 0.8m
        - 可选：均值收敛态得分 ≥ min_accumulation_score（配置为 0 时不启用）
        """
        if getattr(indicators, "accumulation_grade", None) in ("S", "A"):
            pass
        else:
            if indicators.rising_days <= 0:
                return False
            if indicators.falling_days <= indicators.rising_days:  # F > Z
                return False
            if indicators.delta >= 0:  # d20 < d1 => delta < 0
                return False

        if indicators.ratio_d20 is not None:
            if abs(indicators.ratio_d20) >= self.ratio_d20_abs_max:
                return False
        else:
            return False

        if indicators.volume_ratio is not None:
            if indicators.volume_ratio >= self.volume_ratio_max:
                return False
        else:
            return False

        if self.left_min_accumulation_score > 0:
            acc = getattr(indicators, "score_accumulation", None)
            if acc is None or float(acc) < self.left_min_accumulation_score:
                return False

        return True

    def detect_right_buy(self, indicators: GMSIndicators) -> bool:
        """
        右侧买点（动量引爆）：
        - 优先用动量溢出态等级 全速切入/分批买入 判断
        - 前置：d₂₀ > d 且 Δ > 0
        - 位移放量：m₂₀ > 1.5m
        """
        if getattr(indicators, "momentum_grade", None) in ("全速切入", "分批买入"):
            pass
        else:
            if indicators.instant_deviation <= 0:  # d20 > d
                return False
            if indicators.delta <= 0:  # Δ > 0
                return False
        if indicators.volume_ratio is None or indicators.volume_ratio < self.volume_ratio_min:
            return False
        return True

    def detect_sell(self, indicators: GMSIndicators) -> bool:
        """
        卖点（单日可判）：乖离过大
        - Δ/d₂₀ > 15% 或 Δ/d > 15%（若配置 use_ratio_d_for_exit）
        注：趋势破坏（d20 跌破 d 三日）需多日序列，此处不实现
        """
        if self.use_ratio_d_for_exit and indicators.ratio_d is not None:
            if indicators.ratio_d > self.overbought_ratio:
                return True
        if indicators.ratio_d20 is not None:
            if indicators.ratio_d20 > self.overbought_ratio:
                return True
        return False
