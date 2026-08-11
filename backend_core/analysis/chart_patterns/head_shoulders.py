# -*- coding: utf-8 -*-
"""头肩顶 / 头肩底（基于 ZigZag 五枢轴）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .pivots import extract_pivot_sequence
from .rules import invalidate_bottom, invalidate_top
from .schema import fmt_px, make_hit


def _closes(bars: Sequence[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for b in bars:
        try:
            c = float(b.get("close"))
            if c == c:
                out.append(c)
        except (TypeError, ValueError):
            continue
    return out


def _detect_hs_top(
    pivots: List[Dict[str, Any]],
    bars: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """高-低-更高-低-高：左肩、头、右肩。"""
    if len(pivots) < 5:
        return None
    # 取末段交替枢轴，找 … H L H L H
    for end in range(len(pivots), 4, -1):
        win = pivots[end - 5 : end]
        kinds = [p["kind"] for p in win]
        if kinds != ["high", "low", "high", "low", "high"]:
            continue
        ls, n1, head, n2, rs = win
        # 头应明显高于两肩
        if head["price"] <= ls["price"] * 1.01 or head["price"] <= rs["price"] * 1.01:
            continue
        # 两肩高度接近
        mid_s = (ls["price"] + rs["price"]) / 2.0
        if mid_s <= 0 or abs(ls["price"] - rs["price"]) / mid_s > 0.08:
            continue
        neck = (n1["price"] + n2["price"]) / 2.0
        closes = _closes(bars)
        if not closes:
            return None
        last = closes[-1]
        confirmed = last < neck
        if confirmed:
            status = "confirmed"
            conf = 0.7
        elif invalidate_top(last, float(head["price"])):
            # 形成中却收盘升破头部×1.01 → 失效
            status = "invalidated"
            conf = 0.2
        else:
            status = "forming"
            conf = 0.5
        # 右肩略低于左肩略加分（仅对有效形态）
        if status != "invalidated" and rs["price"] <= ls["price"]:
            conf = min(1.0, conf + 0.05)
        reason = (
            f"头肩顶 {fmt_px('左肩', ls['price'], ls.get('date'))} "
            f"{fmt_px('头', head['price'], head.get('date'))} "
            f"{fmt_px('右肩', rs['price'], rs.get('date'))} "
            f"{fmt_px('颈线', round(neck, 4), approx=True)}"
        )
        if status == "invalidated":
            reason += f" 失效:收盘{round(last, 4)}>头×1.01"
        return make_hit(
            pattern_family="head_shoulders",
            pattern_type="head_shoulders_top",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels={
                "left_shoulder": ls["price"],
                "head": head["price"],
                "right_shoulder": rs["price"],
                "neckline": round(neck, 4),
                "last_close": round(last, 4),
            },
            pivots=[
                {"role": "LS", "date": ls.get("date"), "price": ls["price"]},
                {"role": "head", "date": head.get("date"), "price": head["price"]},
                {"role": "RS", "date": rs.get("date"), "price": rs["price"]},
            ],
        )
    return None


def _detect_hs_bottom(
    pivots: List[Dict[str, Any]],
    bars: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """低-高-更低-高-低。"""
    if len(pivots) < 5:
        return None
    for end in range(len(pivots), 4, -1):
        win = pivots[end - 5 : end]
        kinds = [p["kind"] for p in win]
        if kinds != ["low", "high", "low", "high", "low"]:
            continue
        ls, n1, head, n2, rs = win
        if head["price"] >= ls["price"] * 0.99 or head["price"] >= rs["price"] * 0.99:
            continue
        mid_s = (ls["price"] + rs["price"]) / 2.0
        if mid_s <= 0 or abs(ls["price"] - rs["price"]) / mid_s > 0.08:
            continue
        neck = (n1["price"] + n2["price"]) / 2.0
        closes = _closes(bars)
        if not closes:
            return None
        last = closes[-1]
        confirmed = last > neck
        if confirmed:
            status = "confirmed"
            conf = 0.7
        elif invalidate_bottom(last, float(head["price"])):
            # 形成中却收盘跌破头部×0.99 → 失效
            status = "invalidated"
            conf = 0.2
        else:
            status = "forming"
            conf = 0.5
        if status != "invalidated" and rs["price"] >= ls["price"]:
            conf = min(1.0, conf + 0.05)
        reason = (
            f"头肩底 {fmt_px('左肩', ls['price'], ls.get('date'))} "
            f"{fmt_px('头', head['price'], head.get('date'))} "
            f"{fmt_px('右肩', rs['price'], rs.get('date'))} "
            f"{fmt_px('颈线', round(neck, 4), approx=True)}"
        )
        if status == "invalidated":
            reason += f" 失效:收盘{round(last, 4)}<头×0.99"
        return make_hit(
            pattern_family="head_shoulders",
            pattern_type="head_shoulders_bottom",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels={
                "left_shoulder": ls["price"],
                "head": head["price"],
                "right_shoulder": rs["price"],
                "neckline": round(neck, 4),
                "last_close": round(last, 4),
            },
            pivots=[
                {"role": "LS", "date": ls.get("date"), "price": ls["price"]},
                {"role": "head", "date": head.get("date"), "price": head["price"]},
                {"role": "RS", "date": rs.get("date"), "price": rs["price"]},
            ],
        )
    return None


def detect_head_shoulders(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    piv = pivots if pivots is not None else extract_pivot_sequence(bars)
    hits: List[Dict[str, Any]] = []
    top = _detect_hs_top(piv, bars)
    if top:
        hits.append(top)
    bottom = _detect_hs_bottom(piv, bars)
    if bottom:
        hits.append(bottom)
    return hits
