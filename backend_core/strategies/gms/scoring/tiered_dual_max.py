"""
标准版打分：双模块阶梯式，score_total = max(收敛, 动量)。
与改造前 indicators_calculator 逻辑一致。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import GMSIndicators
from ._helpers import safe_float

logger = logging.getLogger(__name__)

MECHANISM_ID = "tiered_dual_max"


class TieredDualMaxScorer:
    """GMS 标准版阶梯打分。"""

    mechanism_id = MECHANISM_ID

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        scoring = self.config.get("scoring", {})
        self.accumulation_fz_min = safe_float(scoring.get("accumulation_fz_min"), 1.5)
        self.balance_ratio_max = safe_float(scoring.get("balance_ratio_max"), 0.01)
        self.momentum_volume_ratio_min = safe_float(scoring.get("momentum_volume_ratio_min"), 1.5)
        self.acc_fz_tiers = scoring.get("accumulation_fz_tiers", [2.5, 1.5])
        self.balance_tiers = scoring.get("balance_ratio_d_tiers", [0.01, 0.015])
        self.vol_shrink_tiers = scoring.get("volume_ratio_shrink_tiers", [0.6, 0.8])
        self.ratio_d1_tiers = scoring.get("ratio_d1_tiers", [0.001, 0.03])
        self.vol_attack_tiers = scoring.get("volume_ratio_attack_tiers", [2.0, 1.5])
        self.stable_days = int(scoring.get("instant_deviation_stable_days", 3))
        self.acc_s_threshold = safe_float(scoring.get("accumulation_s_threshold"), 85)
        self.acc_a_threshold = safe_float(scoring.get("accumulation_a_threshold"), 70)
        self.mom_full_threshold = safe_float(scoring.get("momentum_full_threshold"), 90)
        self.mom_batch_threshold = safe_float(scoring.get("momentum_batch_threshold"), 80)
        self.weight_acc_fz = max(0, safe_float(scoring.get("weight_acc_fz"), 30))
        self.weight_acc_balance = max(0, safe_float(scoring.get("weight_acc_balance"), 40))
        self.weight_acc_volume = max(0, safe_float(scoring.get("weight_acc_volume"), 30))
        self.weight_mom_ratio_d1 = max(0, safe_float(scoring.get("weight_mom_ratio_d1"), 40))
        self.weight_mom_deviation = max(0, safe_float(scoring.get("weight_mom_deviation"), 30))
        self.weight_mom_volume = max(0, safe_float(scoring.get("weight_mom_volume"), 30))

    def calculate(
        self,
        row: Dict[str, Any],
        instant_deviation_series: Optional[List[float]] = None,
    ) -> Optional[GMSIndicators]:
        try:
            code = row.get("code", "")
            date = str(row.get("date", ""))[:10]
            market_type = row.get("market_type", "CN")

            delta = safe_float(row.get("macro_displacement_delta"))
            d = safe_float(row.get("ma20_d"))
            ratio_d20 = row.get("ratio_d20")
            ratio_d1 = row.get("ratio_d1")
            if ratio_d20 is not None:
                ratio_d20 = float(ratio_d20)
            if ratio_d1 is not None:
                ratio_d1 = float(ratio_d1)

            instant_deviation = safe_float(row.get("instant_deviation"))
            rising_days = int(row.get("rising_days_z", 0) or 0)
            falling_days = int(row.get("falling_days_f", 0) or 0)
            avg_volume_20d = safe_float(row.get("mavol20_m"))
            current_volume = safe_float(row.get("current_volume"))
            volume_ratio = row.get("volume_ratio")
            if volume_ratio is not None:
                volume_ratio = float(volume_ratio)
            ratio_d = row.get("ratio_d")
            if ratio_d is not None:
                ratio_d = float(ratio_d)

            fz_ratio = falling_days / rising_days if rising_days > 0 else None
            abs_ratio_d = abs(delta / d) if d and d > 0 else None

            score_acc_fz = self._score_accumulation_fz(fz_ratio)
            score_acc_balance = self._score_accumulation_balance(abs_ratio_d)
            score_acc_volume = self._score_accumulation_volume(volume_ratio)
            score_accumulation = score_acc_fz + score_acc_balance + score_acc_volume

            acc_fz_judge = self._judge_accumulation_fz(fz_ratio)
            acc_balance_judge = self._judge_accumulation_balance(abs_ratio_d)
            acc_volume_judge = self._judge_accumulation_volume(volume_ratio)

            accumulation_grade = ""
            if score_accumulation >= self.acc_s_threshold:
                accumulation_grade = "S"
            elif score_accumulation >= self.acc_a_threshold:
                accumulation_grade = "A"

            score_mom_ratio_d1 = self._score_momentum_ratio_d1(ratio_d1)
            score_mom_deviation, mom_deviation_judge = self._score_momentum_deviation_with_judge(
                instant_deviation, instant_deviation_series
            )
            score_mom_volume = self._score_momentum_volume(volume_ratio)
            score_momentum = score_mom_ratio_d1 + score_mom_deviation + score_mom_volume

            mom_ratio_d1_judge = self._judge_momentum_ratio_d1(ratio_d1)
            mom_volume_judge = self._judge_momentum_volume(volume_ratio)

            momentum_grade = ""
            if score_momentum >= self.mom_full_threshold:
                momentum_grade = "全速切入"
            elif score_momentum >= self.mom_batch_threshold:
                momentum_grade = "分批买入"

            score_total = max(score_accumulation, score_momentum)

            return GMSIndicators(
                code=code,
                date=date,
                market_type=market_type,
                delta=delta,
                d=d,
                ratio_d20=ratio_d20,
                ratio_d1=ratio_d1,
                instant_deviation=instant_deviation,
                rising_days=rising_days,
                falling_days=falling_days,
                avg_volume_20d=avg_volume_20d,
                current_volume=current_volume,
                ratio_d=ratio_d,
                volume_ratio=volume_ratio,
                fz_ratio=fz_ratio,
                score_accumulation=score_accumulation,
                score_balance=score_acc_balance,
                score_momentum=score_momentum,
                score_total=score_total,
                score_base_total=score_total,
                score_penalty_deduction=0.0,
                accumulation_grade=accumulation_grade,
                momentum_grade=momentum_grade,
                score_acc_fz=score_acc_fz,
                score_acc_balance=score_acc_balance,
                score_acc_volume=score_acc_volume,
                score_mom_ratio_d1=score_mom_ratio_d1,
                score_mom_deviation=score_mom_deviation,
                score_mom_volume=score_mom_volume,
                acc_fz_judge=acc_fz_judge,
                acc_balance_judge=acc_balance_judge,
                acc_volume_judge=acc_volume_judge,
                mom_ratio_d1_judge=mom_ratio_d1_judge,
                mom_deviation_judge=mom_deviation_judge,
                mom_volume_judge=mom_volume_judge,
                scoring_mechanism=MECHANISM_ID,
                raw_row=row,
            )
        except Exception as e:
            logger.warning("GMS 标准打分失败: %s, row=%s", e, row.get("code", ""))
            return None

    def _score_accumulation_fz(self, fz_ratio: Optional[float]) -> float:
        if fz_ratio is None or self.weight_acc_fz <= 0:
            return 0.0
        t1, t2 = (self.acc_fz_tiers[0], self.acc_fz_tiers[1]) if len(self.acc_fz_tiers) >= 2 else (2.5, 1.5)
        if fz_ratio >= t1:
            return self.weight_acc_fz
        if fz_ratio >= t2:
            return self.weight_acc_fz * 2 / 3
        return 0.0

    def _score_accumulation_balance(self, abs_ratio_d: Optional[float]) -> float:
        if abs_ratio_d is None or self.weight_acc_balance <= 0:
            return 0.0
        t1, t2 = (self.balance_tiers[0], self.balance_tiers[1]) if len(self.balance_tiers) >= 2 else (0.01, 0.015)
        if abs_ratio_d <= t1:
            return self.weight_acc_balance
        if abs_ratio_d <= t2:
            return self.weight_acc_balance * 0.5
        return 0.0

    def _score_accumulation_volume(self, volume_ratio: Optional[float]) -> float:
        if volume_ratio is None or self.weight_acc_volume <= 0:
            return 0.0
        t1, t2 = (self.vol_shrink_tiers[0], self.vol_shrink_tiers[1]) if len(self.vol_shrink_tiers) >= 2 else (0.6, 0.8)
        if volume_ratio <= t1:
            return self.weight_acc_volume
        if volume_ratio <= t2:
            return self.weight_acc_volume * 0.5
        return 0.0

    def _score_momentum_ratio_d1(self, ratio_d1: Optional[float]) -> float:
        if ratio_d1 is None or self.weight_mom_ratio_d1 <= 0:
            return 0.0
        low, high = (self.ratio_d1_tiers[0], self.ratio_d1_tiers[1]) if len(self.ratio_d1_tiers) >= 2 else (0.001, 0.03)
        if ratio_d1 <= 0:
            return 0.0
        if ratio_d1 > high:
            return 0.0
        if ratio_d1 > low:
            return self.weight_mom_ratio_d1
        return self.weight_mom_ratio_d1 * 0.5

    def _score_momentum_deviation_with_judge(
        self,
        instant_deviation: float,
        series: Optional[List[float]],
    ) -> tuple:
        if instant_deviation <= 0:
            return -10.0, "不合格(d₂₀-d<0)"
        if self.weight_mom_deviation <= 0:
            return 0.0, "—"
        if series is None or len(series) < self.stable_days:
            return self.weight_mom_deviation * 0.5, "达标(仅当日)"
        recent = series[-self.stable_days :]
        if all(x > 0 for x in recent):
            return self.weight_mom_deviation, f"达标(站稳{self.stable_days}日)"
        return self.weight_mom_deviation * 0.5, "达标(仅当日)"

    def _judge_accumulation_fz(self, fz_ratio: Optional[float]) -> str:
        if fz_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.acc_fz_tiers[0], self.acc_fz_tiers[1]) if len(self.acc_fz_tiers) >= 2 else (2.5, 1.5)
        if fz_ratio >= t1:
            return "达标(满分)"
        if fz_ratio >= t2:
            return "达标(2/3)"
        return "未达标"

    def _judge_accumulation_balance(self, abs_ratio_d: Optional[float]) -> str:
        if abs_ratio_d is None:
            return "未达标(无数据)"
        t1, t2 = (self.balance_tiers[0], self.balance_tiers[1]) if len(self.balance_tiers) >= 2 else (0.01, 0.015)
        if abs_ratio_d <= t1:
            return "达标(满分)"
        if abs_ratio_d <= t2:
            return "达标(1/2)"
        return "未达标"

    def _judge_accumulation_volume(self, volume_ratio: Optional[float]) -> str:
        if volume_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.vol_shrink_tiers[0], self.vol_shrink_tiers[1]) if len(self.vol_shrink_tiers) >= 2 else (0.6, 0.8)
        if volume_ratio <= t1:
            return "达标(满分)"
        if volume_ratio <= t2:
            return "达标(1/2)"
        return "未达标"

    def _judge_momentum_ratio_d1(self, ratio_d1: Optional[float]) -> str:
        if ratio_d1 is None:
            return "未达标(无数据)"
        low, high = (self.ratio_d1_tiers[0], self.ratio_d1_tiers[1]) if len(self.ratio_d1_tiers) >= 2 else (0.001, 0.03)
        if ratio_d1 <= 0:
            return "未达标(≤0)"
        if ratio_d1 > high:
            return "未达标(追高)"
        if ratio_d1 > low:
            return "达标(满分)"
        return "达标(1/2)"

    def _judge_momentum_volume(self, volume_ratio: Optional[float]) -> str:
        if volume_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.vol_attack_tiers[0], self.vol_attack_tiers[1]) if len(self.vol_attack_tiers) >= 2 else (2.0, 1.5)
        if volume_ratio >= t1:
            return "达标(满分)"
        if volume_ratio >= t2:
            return "达标(2/3)"
        return "未达标"

    def _score_momentum_volume(self, volume_ratio: Optional[float]) -> float:
        if volume_ratio is None or self.weight_mom_volume <= 0:
            return 0.0
        t1, t2 = (self.vol_attack_tiers[0], self.vol_attack_tiers[1]) if len(self.vol_attack_tiers) >= 2 else (2.0, 1.5)
        if volume_ratio >= t1:
            return self.weight_mom_volume
        if volume_ratio >= t2:
            return self.weight_mom_volume * 2 / 3
        return 0.0
