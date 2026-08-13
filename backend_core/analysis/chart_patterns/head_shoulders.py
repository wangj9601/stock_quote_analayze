# -*- coding: utf-8 -*-
"""头肩顶 / 头肩底（基于 ZigZag 五枢轴）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .pivots import extract_pivot_sequence
from .rules import (
    INVALIDATE_BOTTOM_MULT,
    INVALIDATE_TOP_MULT,
    post_pivot_invalidate_bottom,
    post_pivot_invalidate_top,
)
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


def _bar_date(b: Dict[str, Any]) -> str:
    return str(b.get("date") or b.get("trade_date") or "")[:10]


def _bar_close(b: Dict[str, Any]) -> Optional[float]:
    try:
        c = float(b.get("close"))
        return c if c == c else None
    except (TypeError, ValueError):
        return None


def _pivot_bar_index(bars: Sequence[Dict[str, Any]], pivot: Dict[str, Any]) -> int:
    """右肩等枢轴对应的 K 线 index；优先 pivot['index']，否则按 date 回查。"""
    idx = pivot.get("index")
    try:
        i = int(idx)
        if 0 <= i < len(bars):
            return i
    except (TypeError, ValueError):
        pass
    d = pivot.get("date")
    if d is None:
        return -1
    d_s = str(d)[:10]
    for i, b in enumerate(bars):
        if str(b.get("date") or "")[:10] == d_s:
            return i
    return -1


def _first_close_break(
    bars: Sequence[Dict[str, Any]],
    start_i: int,
    neck: float,
    *,
    below: bool,
) -> Optional[Tuple[int, str]]:
    """右肩完成后：首次收盘有效破颈（顶=收盘<颈线；底=收盘>颈线）。"""
    if neck <= 0 or start_i < 0:
        return None
    for i in range(int(start_i) + 1, len(bars)):
        c = _bar_close(bars[i])
        if c is None:
            continue
        if below and c < neck:
            return i, _bar_date(bars[i])
        if (not below) and c > neck:
            return i, _bar_date(bars[i])
    return None


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
        head_px = float(head["price"])
        rs_i = _pivot_bar_index(bars, rs)
        confirm_date: Optional[str] = None
        # 右肩完成后：任一高点/收盘 > 头×1.01 → 失效（优先于颈线确认）
        if post_pivot_invalidate_top(bars, rs_i, head_px):
            status = "invalidated"
            conf = 0.2
        else:
            # 历史锁存：任一收盘破颈即 confirmed，反弹不得改回 forming
            brk = _first_close_break(bars, rs_i, neck, below=True)
            if brk:
                status = "confirmed"
                conf = 0.7
                confirm_date = brk[1]
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
            thr = round(head_px * INVALIDATE_TOP_MULT, 4)
            reason += f" 失效:右肩后高点/收盘>头×{INVALIDATE_TOP_MULT}({thr})"
        elif status == "confirmed" and confirm_date and last >= neck:
            reason += f" 破颈确认:{confirm_date}（现价已反抽颈线上方，状态仍锁存）"
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
            extra={"confirm_date": confirm_date},
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
        head_px = float(head["price"])
        rs_i = _pivot_bar_index(bars, rs)
        confirm_date: Optional[str] = None
        # 右肩完成后：任一低点/收盘 < 头×0.99 → 失效（优先于颈线确认）
        if post_pivot_invalidate_bottom(bars, rs_i, head_px):
            status = "invalidated"
            conf = 0.2
        else:
            brk = _first_close_break(bars, rs_i, neck, below=False)
            if brk:
                status = "confirmed"
                conf = 0.7
                confirm_date = brk[1]
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
            thr = round(head_px * INVALIDATE_BOTTOM_MULT, 4)
            reason += f" 失效:右肩后低点/收盘<头×{INVALIDATE_BOTTOM_MULT}({thr})"
        elif status == "confirmed" and confirm_date and last <= neck:
            reason += f" 破颈确认:{confirm_date}（现价已回落颈线下方，状态仍锁存）"
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
            extra={"confirm_date": confirm_date},
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
