"""GMS 信号风险提示标签构建。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import GMSIndicators
from .scoring.penalties import PenaltyEngine


def build_risk_tags(
    indicators: GMSIndicators,
    config: Dict[str, Any],
    *,
    left_buy: bool = False,
    right_buy: bool = False,
    sell: bool = False,
    trend_break: bool = False,
) -> List[Dict[str, str]]:
    tags: List[Dict[str, str]] = []
    scoring = config.get("scoring") or {}
    overbought = float(scoring.get("overbought_ratio") or config.get("overbought_ratio") or 0.15)
    watch_th = float(scoring.get("watch_threshold") or 60)

    if sell:
        tags.append(
            {
                "id": "overbought",
                "label": "乖离过大",
                "level": "danger",
                "reason": f"Δ/d₂₀ 或 Δ/d 超过阈值 {overbought:.0%}",
            }
        )
    elif indicators.ratio_d20 is not None and indicators.ratio_d20 > overbought * 0.85:
        tags.append(
            {
                "id": "overbought_near",
                "label": "接近过热",
                "level": "warn",
                "reason": "乖离率接近卖出阈值",
            }
        )

    vol_ratio = float(indicators.volume_ratio or 0)
    if vol_ratio > 0 and vol_ratio < 0.6:
        tags.append(
            {
                "id": "volume_weak",
                "label": "量能不足",
                "level": "warn",
                "reason": f"量比 {vol_ratio:.2f} 偏低",
            }
        )

    row = indicators.raw_row or {}
    ma60 = row.get("ma60_d")
    if ma60 is not None:
        close = float(row.get("d20") or (indicators.d + indicators.instant_deviation))
        if close > 0 and float(ma60) > 0 and close < float(ma60):
            tags.append(
                {
                    "id": "below_ma60",
                    "label": "低于MA60",
                    "level": "warn",
                    "reason": "收盘价低于 60 日均线",
                }
            )

    if trend_break:
        tags.append(
            {
                "id": "trend_break",
                "label": "趋势破坏",
                "level": "danger",
                "reason": "d₂₀ 连续跌破宏观位移 d",
            }
        )

    acc = float(indicators.score_accumulation or 0)
    if not left_buy and not right_buy and acc < watch_th:
        tags.append(
            {
                "id": "left_signal_weak",
                "label": "蓄势偏弱",
                "level": "info",
                "reason": f"均值收敛态得分 {acc:.0f} 低于关注线 {watch_th:.0f}",
            }
        )

    try:
        engine = PenaltyEngine(config)
        _, details = engine.apply(row)
        for p in details:
            if p.get("applied"):
                tags.append(
                    {
                        "id": f"penalty_{p.get('id')}",
                        "label": p.get("label") or p.get("id"),
                        "level": "warn",
                        "reason": f"减分规则触发，扣 {p.get('points')} 分",
                    }
                )
    except Exception:
        pass

    return tags


def detect_trend_break(d20_series: Optional[List[float]], d_series: Optional[List[float]], days: int = 3) -> bool:
    if not d20_series or not d_series or len(d20_series) < days or len(d_series) < days:
        return False
    recent_d20 = d20_series[-days:]
    recent_d = d_series[-days:]
    return all(d20 < d for d20, d in zip(recent_d20, recent_d))