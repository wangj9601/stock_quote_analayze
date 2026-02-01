"""
GMS 指标计算器
从 data_loader 输出的行数据计算 GMSIndicators，双模块阶梯式评分（吸附态 / 突变态）
"""

import logging
from typing import Dict, Any, Optional, List

from .models import GMSIndicators

logger = logging.getLogger(__name__)


def _safe_float(v, default=0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class GMSIndicatorsCalculator:
    """GMS 指标与阶梯式评分计算"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        scoring = self.config.get("scoring", {})
        # 旧版兼容
        self.accumulation_fz_min = _safe_float(scoring.get("accumulation_fz_min"), 1.5)
        self.balance_ratio_max = _safe_float(scoring.get("balance_ratio_max"), 0.01)
        self.momentum_volume_ratio_min = _safe_float(scoring.get("momentum_volume_ratio_min"), 1.5)
        # 阶梯配置
        self.acc_fz_tiers = scoring.get("accumulation_fz_tiers", [2.5, 1.5])
        self.balance_tiers = scoring.get("balance_ratio_d_tiers", [0.01, 0.015])
        self.vol_shrink_tiers = scoring.get("volume_ratio_shrink_tiers", [0.6, 0.8])
        self.ratio_d1_tiers = scoring.get("ratio_d1_tiers", [0.001, 0.03])
        self.vol_attack_tiers = scoring.get("volume_ratio_attack_tiers", [2.0, 1.5])
        self.stable_days = int(scoring.get("instant_deviation_stable_days", 3))
        self.acc_s_threshold = _safe_float(scoring.get("accumulation_s_threshold"), 85)
        self.acc_a_threshold = _safe_float(scoring.get("accumulation_a_threshold"), 70)
        self.mom_full_threshold = _safe_float(scoring.get("momentum_full_threshold"), 90)
        self.mom_batch_threshold = _safe_float(scoring.get("momentum_batch_threshold"), 80)
        # 评分权重（可配置，默认 30/40/30）
        self.weight_acc_fz = max(0, _safe_float(scoring.get("weight_acc_fz"), 30))
        self.weight_acc_balance = max(0, _safe_float(scoring.get("weight_acc_balance"), 40))
        self.weight_acc_volume = max(0, _safe_float(scoring.get("weight_acc_volume"), 30))
        self.weight_mom_ratio_d1 = max(0, _safe_float(scoring.get("weight_mom_ratio_d1"), 40))
        self.weight_mom_deviation = max(0, _safe_float(scoring.get("weight_mom_deviation"), 30))
        self.weight_mom_volume = max(0, _safe_float(scoring.get("weight_mom_volume"), 30))

    def calculate(
        self,
        row: Dict[str, Any],
        instant_deviation_series: Optional[List[float]] = None,
    ) -> Optional[GMSIndicators]:
        """
        从单行指标数据计算 GMS 衍生指标及双模块阶梯评分

        Args:
            row: data_loader 输出的字典
            instant_deviation_series: 最近 N 日 instant_deviation 序列（用于站稳3日），
                最后一项为当日；None 时按仅当日处理

        Returns:
            GMSIndicators 或 None（数据无效时）
        """
        try:
            code = row.get("code", "")
            date = str(row.get("date", ""))[:10]
            market_type = row.get("market_type", "CN")

            delta = _safe_float(row.get("macro_displacement_delta"))
            d = _safe_float(row.get("ma20_d"))
            ratio_d20 = row.get("ratio_d20")
            ratio_d1 = row.get("ratio_d1")
            if ratio_d20 is not None:
                ratio_d20 = float(ratio_d20)
            if ratio_d1 is not None:
                ratio_d1 = float(ratio_d1)

            instant_deviation = _safe_float(row.get("instant_deviation"))
            rising_days = int(row.get("rising_days_z", 0) or 0)
            falling_days = int(row.get("falling_days_f", 0) or 0)
            avg_volume_20d = _safe_float(row.get("mavol20_m"))
            current_volume = _safe_float(row.get("current_volume"))
            volume_ratio = row.get("volume_ratio")
            if volume_ratio is not None:
                volume_ratio = float(volume_ratio)
            ratio_d = row.get("ratio_d")
            if ratio_d is not None:
                ratio_d = float(ratio_d)

            # F/Z 数方比
            fz_ratio = None
            if rising_days > 0:
                fz_ratio = falling_days / rising_days

            # |Δ/d|：引力粘合必须用宏观位移，Δ = d₂₀ - d₁，即 |delta/d|
            # 注意：ratio_d(bias) = Δ₂₀/d = (d₂₀-d)/d，与 Δ/d 不同，不可混用
            abs_ratio_d = abs(delta / d) if d and d > 0 else None

            # === 吸附态阶梯评分（满分 100）===
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

            # === 突变态阶梯评分（满分 100，可含负分）===
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

            # 综合总分：取两模块较高者，用于排序
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
                raw_row=row,
            )
        except Exception as e:
            logger.warning(f"GMS 指标计算失败: {e}, row={row.get('code', '')}")
            return None

    def _score_accumulation_fz(self, fz_ratio: Optional[float]) -> float:
        """吸附态-时间耗散 F/Z：≥t1→权重, [t2,t1)→2/3权重, <t2→0"""
        if fz_ratio is None or self.weight_acc_fz <= 0:
            return 0.0
        t1, t2 = (self.acc_fz_tiers[0], self.acc_fz_tiers[1]) if len(self.acc_fz_tiers) >= 2 else (2.5, 1.5)
        if fz_ratio >= t1:
            return self.weight_acc_fz
        if fz_ratio >= t2:
            return self.weight_acc_fz * 2 / 3
        return 0.0

    def _score_accumulation_balance(self, abs_ratio_d: Optional[float]) -> float:
        """吸附态-引力粘合 |Δ/d|：≤t1→权重, ≤t2→1/2权重, >t2→0"""
        if abs_ratio_d is None or self.weight_acc_balance <= 0:
            return 0.0
        t1, t2 = (self.balance_tiers[0], self.balance_tiers[1]) if len(self.balance_tiers) >= 2 else (0.01, 0.015)
        if abs_ratio_d <= t1:
            return self.weight_acc_balance
        if abs_ratio_d <= t2:
            return self.weight_acc_balance * 0.5
        return 0.0

    def _score_accumulation_volume(self, volume_ratio: Optional[float]) -> float:
        """吸附态-成交量缩 m₂₀/m：≤t1→权重, (t1,t2]→1/2权重, >t2→0"""
        if volume_ratio is None or self.weight_acc_volume <= 0:
            return 0.0
        t1, t2 = (self.vol_shrink_tiers[0], self.vol_shrink_tiers[1]) if len(self.vol_shrink_tiers) >= 2 else (0.6, 0.8)
        if volume_ratio <= t1:
            return self.weight_acc_volume
        if volume_ratio <= t2:
            return self.weight_acc_volume * 0.5
        return 0.0

    def _score_momentum_ratio_d1(self, ratio_d1: Optional[float]) -> float:
        """突变态-盈亏反转 Δ/d₁：手册规定 (0%,3%] 为最佳买点（刚突破），>3% 已涨太多非买点
        (0, 0.001] 刚过0轴→1/2权重; (0.001, 0.03] 刚突破→满分; >0.03→0分（追高/应止盈）"""
        if ratio_d1 is None or self.weight_mom_ratio_d1 <= 0:
            return 0.0
        low, high = (self.ratio_d1_tiers[0], self.ratio_d1_tiers[1]) if len(self.ratio_d1_tiers) >= 2 else (0.001, 0.03)
        if ratio_d1 <= 0:
            return 0.0
        if ratio_d1 > high:
            return 0.0  # 已涨太多，非"刚突破"买点，给0分
        if ratio_d1 > low:
            return self.weight_mom_ratio_d1  # (0.001, 0.03] 刚突破，满分
        return self.weight_mom_ratio_d1 * 0.5  # (0, 0.001] 刚过0轴

    def _score_momentum_deviation(
        self,
        instant_deviation: float,
        series: Optional[List[float]],
    ) -> float:
        """突变态-推力支撑 d₂₀-d：站稳3日→权重, 仅当日→1/2权重, <0→-10（固定）"""
        score, _ = self._score_momentum_deviation_with_judge(instant_deviation, series)
        return score

    def _score_momentum_deviation_with_judge(
        self,
        instant_deviation: float,
        series: Optional[List[float]],
    ) -> tuple:
        """突变态-推力支撑 d₂₀-d：返回 (score, judge)"""
        if instant_deviation <= 0:
            return -10.0, "不合格(d₂₀-d<0)"
        if self.weight_mom_deviation <= 0:
            return 0.0, "—"
        if series is None or len(series) < self.stable_days:
            return self.weight_mom_deviation * 0.5, "达标(仅当日)"
        recent = series[-self.stable_days:]
        if all(x > 0 for x in recent):
            return self.weight_mom_deviation, f"达标(站稳{self.stable_days}日)"
        return self.weight_mom_deviation * 0.5, "达标(仅当日)"

    def _judge_accumulation_fz(self, fz_ratio: Optional[float]) -> str:
        """吸附态 F/Z 判定"""
        if fz_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.acc_fz_tiers[0], self.acc_fz_tiers[1]) if len(self.acc_fz_tiers) >= 2 else (2.5, 1.5)
        if fz_ratio >= t1:
            return "达标(满分)"
        if fz_ratio >= t2:
            return "达标(2/3)"
        return "未达标"

    def _judge_accumulation_balance(self, abs_ratio_d: Optional[float]) -> str:
        """吸附态 |Δ/d| 判定"""
        if abs_ratio_d is None:
            return "未达标(无数据)"
        t1, t2 = (self.balance_tiers[0], self.balance_tiers[1]) if len(self.balance_tiers) >= 2 else (0.01, 0.015)
        if abs_ratio_d <= t1:
            return "达标(满分)"
        if abs_ratio_d <= t2:
            return "达标(1/2)"
        return "未达标"

    def _judge_accumulation_volume(self, volume_ratio: Optional[float]) -> str:
        """吸附态 成交量缩 判定"""
        if volume_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.vol_shrink_tiers[0], self.vol_shrink_tiers[1]) if len(self.vol_shrink_tiers) >= 2 else (0.6, 0.8)
        if volume_ratio <= t1:
            return "达标(满分)"
        if volume_ratio <= t2:
            return "达标(1/2)"
        return "未达标"

    def _judge_momentum_ratio_d1(self, ratio_d1: Optional[float]) -> str:
        """突变态 Δ/d₁ 判定"""
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
        """突变态 攻击强度 判定"""
        if volume_ratio is None:
            return "未达标(无数据)"
        t1, t2 = (self.vol_attack_tiers[0], self.vol_attack_tiers[1]) if len(self.vol_attack_tiers) >= 2 else (2.0, 1.5)
        if volume_ratio >= t1:
            return "达标(满分)"
        if volume_ratio >= t2:
            return "达标(2/3)"
        return "未达标"

    def _score_momentum_volume(self, volume_ratio: Optional[float]) -> float:
        """突变态-攻击强度 m₂₀/m：≥t1→权重, [t2,t1)→2/3权重, <t2→0"""
        if volume_ratio is None or self.weight_mom_volume <= 0:
            return 0.0
        t1, t2 = (self.vol_attack_tiers[0], self.vol_attack_tiers[1]) if len(self.vol_attack_tiers) >= 2 else (2.0, 1.5)
        if volume_ratio >= t1:
            return self.weight_mom_volume
        if volume_ratio >= t2:
            return self.weight_mom_volume * 2 / 3
        return 0.0
