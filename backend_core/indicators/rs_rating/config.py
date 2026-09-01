"""IBD 风格 RS Rating 默认参数。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# 交易日窗口（约四个季度）与对应权重
RS_WINDOWS: Tuple[int, ...] = (63, 126, 189, 252)
RS_WEIGHTS: Tuple[float, ...] = (0.4, 0.2, 0.2, 0.2)

# 相对候选池的有效 RS_Raw 覆盖率；低于此值不发布 1–99 评级
COVERAGE_THRESHOLD = 0.90
# 港股：分母用「已有前复权序列」的股票数（无因子无法入评，不宜与全日候选硬比 90%）
COVERAGE_THRESHOLD_HK = 0.90

# 日历回看天数（覆盖约 252 个交易日并留余量）
LOOKBACK_CALENDAR_DAYS = 420
# 港股休市更多、窗口内有效 K 线更稀；420 日中位数约 225 根，达不到 253，故加长
LOOKBACK_CALENDAR_DAYS_HK = 600

MARKET_TYPE = "CN"
MARKET_TYPE_HK = "HK"

# 价格口径：前复权（库内因子现算）
PRICE_ADJUST = "qfq"

# A 股 / 港股复权因子源（日终批算只读库，不打外网）
CN_FACTOR_SOURCES: Tuple[str, ...] = ("akshare_sina_qfq", "baostock_qfq")
HK_FACTOR_SOURCES: Tuple[str, ...] = ("akshare_sina_hk_qfq", "akshare_em_hk_qfq")


def coverage_threshold(market: str = MARKET_TYPE) -> float:
    """A 股相对全日候选池；港股相对「已具备前复权序列」的股票（无因子者无法入评）。"""
    m = str(market or MARKET_TYPE).strip().upper()
    if m == MARKET_TYPE_HK:
        return float(COVERAGE_THRESHOLD_HK)
    return float(COVERAGE_THRESHOLD)


def strength_label(rs_rating: Optional[int]) -> Optional[str]:
    """展示用强弱档，不参与计算。"""
    if rs_rating is None:
        return None
    r = int(rs_rating)
    if r >= 90:
        return "很强"
    if r >= 70:
        return "偏强"
    if r >= 50:
        return "中性"
    if r >= 30:
        return "偏弱"
    return "很弱"


def window_weight_pairs() -> List[Dict[str, float]]:
    return [
        {"window": int(w), "weight": float(wt)}
        for w, wt in zip(RS_WINDOWS, RS_WEIGHTS)
    ]
