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
# 港股近阈值：实际覆盖率 > 此值时按达到 COVERAGE_THRESHOLD_HK（0.90）处理并发布评级
COVERAGE_NEAR_PASS_HK = 0.88

# 日历回看天数（覆盖约 252 个交易日并留余量）
LOOKBACK_CALENDAR_DAYS = 420
# 港股休市更多、窗口内有效 K 线更稀；420 日中位数约 225 根，达不到 253。
# 600 日仍有一批「全表够 253、窗口内差几根」；提到 750 覆盖约两年半日历，抬升覆盖率。
LOOKBACK_CALENDAR_DAYS_HK = 750

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


def coverage_for_publish(coverage: float, market: str = MARKET_TYPE) -> float:
    """用于发布判定的覆盖率。

    港股：实际值 > ``COVERAGE_NEAR_PASS_HK``（0.88）时按 ``COVERAGE_THRESHOLD_HK``（0.90）计；
    A 股原样返回。
    """
    m = str(market or MARKET_TYPE).strip().upper()
    c = float(coverage or 0.0)
    if m == MARKET_TYPE_HK and c > float(COVERAGE_NEAR_PASS_HK):
        return float(COVERAGE_THRESHOLD_HK)
    return c


def coverage_allows_publish(coverage: float, market: str = MARKET_TYPE) -> bool:
    """是否达到发布 1–99 评级的覆盖率门槛。"""
    return coverage_for_publish(coverage, market) >= coverage_threshold(market)


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
