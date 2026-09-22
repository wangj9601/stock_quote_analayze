# -*- coding: utf-8 -*-
"""袋鼠尾形态识别（复用 KGT detector，输出 chart_patterns 标准 hit）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.strategies.kangaroo_tail.detector import detect_kangaroo_tails_in_bars

from .schema import make_hit


def detect_kangaroo_tail_patterns(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """返回标准化 hit 列表，供 chart_patterns.engine 汇总。"""
    cfg = dict(pattern_cfg or {})
    kgt_cfg = dict(cfg.get("kangaroo_tail") or cfg.get("kgt") or {})
    if not kgt_cfg:
        for key in (
            "min_range_pct",
            "max_body_ratio",
            "shadow_body_mult",
            "shadow_range_mult",
            "opposite_shadow_body_mult",
            "close_half_ratio",
            "require_trend_filter",
            "ma_period",
            "directions",
            "exclude_limit_board",
            "max_hits",
        ):
            if key in cfg:
                kgt_cfg[key] = cfg[key]
    # 形态工具默认不做趋势过滤，避免漏掉更多标注
    if "require_trend_filter" not in kgt_cfg:
        kgt_cfg["require_trend_filter"] = False

    lookback = max(30, int(cfg.get("lookback_days") or 60))
    seq = list(bars or [])
    if len(seq) > lookback:
        seq = seq[-lookback:]
    max_hits = int(kgt_cfg.get("max_hits") or 5)

    raw_hits = detect_kangaroo_tails_in_bars(seq, pattern_cfg=kgt_cfg, max_hits=max_hits)
    out: List[Dict[str, Any]] = []
    for raw in raw_hits:
        direction = str(raw.get("direction") or "")
        ptype = str(raw.get("pattern_type") or "")
        if not ptype:
            ptype = (
                "kangaroo_tail_bullish"
                if direction == "bullish"
                else "kangaroo_tail_bearish"
            )
        score = float(raw.get("score") or 0)
        conf = min(0.99, max(0.0, score / 100.0))
        date_s = str(raw.get("signal_date") or "")[:10]
        if direction == "bullish":
            reason = (
                f"看涨袋鼠尾 {date_s} "
                f"下影={raw.get('lower_shadow')} "
                f"振幅={raw.get('range_pct')}% "
                f"得分={score}"
            )
            pivot_price = raw.get("low")
        else:
            reason = (
                f"看跌袋鼠尾 {date_s} "
                f"上影={raw.get('upper_shadow')} "
                f"振幅={raw.get('range_pct')}% "
                f"得分={score}"
            )
            pivot_price = raw.get("high")

        out.append(
            make_hit(
                pattern_family="kangaroo_tail",
                pattern_type=ptype,
                status="confirmed",
                confidence=conf,
                reason=reason,
                key_levels={
                    "high": raw.get("high"),
                    "low": raw.get("low"),
                    "close": raw.get("close"),
                    "open": raw.get("open"),
                    "last_close": raw.get("last_close") or raw.get("close"),
                },
                pivots=[
                    {
                        "role": "tail",
                        "date": date_s,
                        "price": pivot_price,
                    }
                ],
                extra={
                    "confirm_date": date_s,
                    "formed_at": date_s,
                    "direction": direction,
                    "score": score,
                    "range_pct": raw.get("range_pct"),
                    "body_ratio": raw.get("body_ratio"),
                    "shadow_ratio": raw.get("shadow_ratio"),
                    "close_pos": raw.get("close_pos"),
                    "lower_shadow": raw.get("lower_shadow"),
                    "upper_shadow": raw.get("upper_shadow"),
                    "ma20": raw.get("ma20"),
                },
            )
        )
    return out
