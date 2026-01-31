"""
GMS 指标计算器
从 data_loader 输出的行数据计算 GMSIndicators，含蓄势/平衡/动量评分
"""

import logging
from typing import Dict, Any, Optional

from .models import GMSIndicators

logger = logging.getLogger(__name__)


class GMSIndicatorsCalculator:
    """GMS 指标与评分计算"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        scoring = self.config.get("scoring", {})
        self.accumulation_fz_min = float(scoring.get("accumulation_fz_min", 1.5))
        self.balance_ratio_max = float(scoring.get("balance_ratio_max", 0.01))
        self.momentum_volume_ratio_min = float(scoring.get("momentum_volume_ratio_min", 1.5))

    def calculate(self, row: Dict[str, Any]) -> Optional[GMSIndicators]:
        """
        从单行指标数据计算 GMS 衍生指标及评分

        Args:
            row: data_loader 输出的字典

        Returns:
            GMSIndicators 或 None（数据无效时）
        """
        try:
            code = row.get("code", "")
            date = str(row.get("date", ""))[:10]
            market_type = row.get("market_type", "CN")

            delta = float(row.get("macro_displacement_delta", 0) or 0)
            d = float(row.get("ma20_d", 0) or 0)
            ratio_d20 = row.get("ratio_d20")
            ratio_d1 = row.get("ratio_d1")
            if ratio_d20 is not None:
                ratio_d20 = float(ratio_d20)
            if ratio_d1 is not None:
                ratio_d1 = float(ratio_d1)

            instant_deviation = float(row.get("instant_deviation", 0) or 0)
            rising_days = int(row.get("rising_days_z", 0) or 0)
            falling_days = int(row.get("falling_days_f", 0) or 0)
            avg_volume_20d = float(row.get("mavol20_m", 0) or 0)
            current_volume = float(row.get("current_volume", 0) or 0)
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

            # 评分（使用 >= 和 <=，边界值算满足）
            score_acc = 0.0
            if fz_ratio is not None and fz_ratio >= self.accumulation_fz_min:
                score_acc = 30.0

            score_bal = 0.0
            if ratio_d20 is not None and d and abs(ratio_d20) < self.balance_ratio_max:
                score_bal = 40.0

            score_mom = 0.0
            if delta > 0 and volume_ratio is not None and volume_ratio >= self.momentum_volume_ratio_min:
                score_mom = 30.0

            score_total = score_acc + score_bal + score_mom

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
                score_accumulation=score_acc,
                score_balance=score_bal,
                score_momentum=score_mom,
                score_total=score_total,
                raw_row=row,
            )
        except Exception as e:
            logger.warning(f"GMS 指标计算失败: {e}, row={row.get('code', '')}")
            return None
