"""
GMS 数据加载器
从 mean_frequency_resonance_indicators 表加载指标，并计算 Δ/d、量比
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class GMSDataLoader:
    """从 mean_frequency_resonance_indicators 加载 GMS 所需指标"""

    def __init__(self, db: Session):
        self.db = db

    def load_indicators(
        self,
        codes: List[str],
        date: str,
        market_type: str = "CN",
    ) -> List[Dict[str, Any]]:
        """
        批量加载指定日期、市场的指标数据

        Args:
            codes: 股票代码列表
            date: 日期 (YYYY-MM-DD)
            market_type: CN 或 HK

        Returns:
            每只股票的指标字典列表，包含表字段及衍生的 ratio_d、volume_ratio
        """
        if not codes:
            return []

        try:
            from backend_api.models import MeanFrequencyResonanceIndicators

            query = self.db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code.in_(codes),
                MeanFrequencyResonanceIndicators.date == str(date).strip()[:10],
            )
            rows = query.all()

            result = []
            for item in rows:
                delta = item.macro_displacement_delta or 0.0
                ma20_d = item.ma20_d or 0.0
                mavol20_m = item.mavol20_m or 0.0
                eff_m20_m = item.efficiency_m20_minus_m or 0.0

                # Δ/d 从表的 bias 字段取值
                ratio_d = getattr(item, "bias", None)

                # 计算 m₂₀ 和量比: m20 = efficiency_m20_minus_m + mavol20_m
                current_volume = eff_m20_m + mavol20_m if mavol20_m else 0.0
                volume_ratio = None
                if mavol20_m and mavol20_m > 0:
                    volume_ratio = current_volume / mavol20_m

                row_dict = {
                    "code": item.code,
                    "date": str(item.date)[:10] if item.date else str(date)[:10],
                    "market_type": item.market_type or market_type,
                    "macro_displacement_delta": delta,
                    "ma20_d": ma20_d,
                    "ratio_d20": getattr(item, "ratio_d20", None),
                    "ratio_d1": getattr(item, "ratio_d1", None),
                    "instant_deviation": item.instant_deviation or 0.0,
                    "rising_days_z": item.rising_days_z or 0,
                    "falling_days_f": item.falling_days_f or 0,
                    "mavol20_m": mavol20_m,
                    "efficiency_m20_minus_m": eff_m20_m,
                    "ratio_d": ratio_d,
                    "current_volume": current_volume,
                    "volume_ratio": volume_ratio,
                }
                result.append(row_dict)

            logger.info(f"GMS 加载 {len(result)} 条指标, date={date}, market={market_type}")
            return result

        except Exception as e:
            logger.error(f"GMS 加载指标失败: {e}", exc_info=True)
            raise
