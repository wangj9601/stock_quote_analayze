# -*- coding: utf-8 -*-
"""头肩顶 / 头肩底（基于 ZigZag 五枢轴）。

颈线：两峰（顶）/两谷间高点（底）线性斜颈线；破位按当日斜颈阈值确认。
几何：头相对两肩须有足够深度；颈线两峰不可过度不对称（抑制双底+虚高颈线误报）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .pivots import extract_pivot_sequence
from .rules import (
    HS_HEAD_MIN_DEPTH_PCT,
    HS_NECK_ASYMMETRY_MAX,
    HS_NECK_COLLAPSE_FLOOR,
    HS_NECK_EXTRAP_HI_FRAC,
    HS_NECK_EXTRAP_LO_FRAC,
    HS_SHOULDER_TOL_PCT,
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


def _neck_at(
    n1_price: float,
    n1_i: int,
    n2_price: float,
    n2_i: int,
    bar_i: int,
) -> float:
    """斜颈线在 bar_i 处的价格（线性插值/外推）。"""
    if n2_i == n1_i:
        return float(n1_price)
    t = (float(bar_i) - float(n1_i)) / (float(n2_i) - float(n1_i))
    return float(n1_price) + t * (float(n2_price) - float(n1_price))


def _neck_ref_display(n1_price: float, n2_price: float, rs_neck: float) -> float:
    """崩塌后展示用参考颈：优先右肩日斜颈（若正），否则两颈点均值。"""
    if rs_neck == rs_neck and rs_neck > HS_NECK_COLLAPSE_FLOOR:
        return float(rs_neck)
    mid = (float(n1_price) + float(n2_price)) / 2.0
    return mid if mid == mid else float(n1_price)


def _slant_neck_collapsed(
    neck: float,
    n1_price: float,
    n2_price: float,
    *,
    is_top: bool,
) -> bool:
    """斜颈是否已外推失真（负值/近零，或相对颈点过分偏离）。

    顶/底均可因相对两颈点过低而崩塌；底另可因过高崩塌。
    """
    if neck != neck:  # NaN
        return True
    floor = float(HS_NECK_COLLAPSE_FLOOR)
    if neck <= floor:
        return True
    lo = min(float(n1_price), float(n2_price))
    hi = max(float(n1_price), float(n2_price))
    if lo > 0 and neck < lo * float(HS_NECK_EXTRAP_LO_FRAC):
        return True
    if (not is_top) and hi > 0 and neck > hi * float(HS_NECK_EXTRAP_HI_FRAC):
        return True
    return False


def _first_close_break_slanted(
    bars: Sequence[Dict[str, Any]],
    start_i: int,
    *,
    n1_price: float,
    n1_i: int,
    n2_price: float,
    n2_i: int,
    below: bool,
) -> Optional[Tuple[str, int, str, float]]:
    """右肩完成后：首次收盘有效破当日斜颈（顶=收盘<颈；底=收盘>颈）。

    返回 ("break", bar_index, date, neck_at_break) 或
    ("collapse", bar_index, date, neck_at) 当斜颈外推失真。
    """
    if start_i < 0:
        return None
    is_top = bool(below)
    for i in range(int(start_i) + 1, len(bars)):
        c = _bar_close(bars[i])
        if c is None:
            continue
        neck_i = _neck_at(n1_price, n1_i, n2_price, n2_i, i)
        if _slant_neck_collapsed(neck_i, n1_price, n2_price, is_top=is_top):
            return "collapse", i, _bar_date(bars[i]), neck_i
        if below and c < neck_i:
            return "break", i, _bar_date(bars[i]), neck_i
        if (not below) and c > neck_i:
            return "break", i, _bar_date(bars[i]), neck_i
    return None


def _shoulder_ok(ls_px: float, rs_px: float, *, tol: float) -> bool:
    mid_s = (ls_px + rs_px) / 2.0
    if mid_s <= 0:
        return False
    return abs(ls_px - rs_px) / mid_s <= float(tol)


def _neck_asymmetry_ok(n1: float, n2: float, *, max_asym: float) -> bool:
    mid = (n1 + n2) / 2.0
    if mid <= 0:
        return False
    return abs(n1 - n2) / mid <= float(max_asym)


def _head_depth_ok_bottom(head: float, ls: float, rs: float, *, depth: float) -> bool:
    """头须明显低于两肩：head <= shoulder × (1 − depth)。"""
    if head <= 0 or ls <= 0 or rs <= 0:
        return False
    thr = 1.0 - max(0.0, float(depth))
    return head <= ls * thr and head <= rs * thr


def _head_depth_ok_top(head: float, ls: float, rs: float, *, depth: float) -> bool:
    """头须明显高于两肩：head >= shoulder × (1 + depth)。"""
    if head <= 0 or ls <= 0 or rs <= 0:
        return False
    thr = 1.0 + max(0.0, float(depth))
    return head >= ls * thr and head >= rs * thr


def _detect_hs_top(
    pivots: List[Dict[str, Any]],
    bars: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """高-低-更高-低-高：左肩、头、右肩。"""
    if len(pivots) < 5:
        return None
    depth = HS_HEAD_MIN_DEPTH_PCT
    shoulder_tol = HS_SHOULDER_TOL_PCT
    neck_asym = HS_NECK_ASYMMETRY_MAX

    for end in range(len(pivots), 4, -1):
        win = pivots[end - 5 : end]
        kinds = [p["kind"] for p in win]
        if kinds != ["high", "low", "high", "low", "high"]:
            continue
        ls, n1, head, n2, rs = win
        if not _head_depth_ok_top(
            float(head["price"]), float(ls["price"]), float(rs["price"]), depth=depth
        ):
            continue
        if not _shoulder_ok(float(ls["price"]), float(rs["price"]), tol=shoulder_tol):
            continue
        n1_px, n2_px = float(n1["price"]), float(n2["price"])
        if not _neck_asymmetry_ok(n1_px, n2_px, max_asym=neck_asym):
            continue
        n1_i = _pivot_bar_index(bars, n1)
        n2_i = _pivot_bar_index(bars, n2)
        if n1_i < 0 or n2_i < 0:
            continue
        closes = _closes(bars)
        if not closes:
            return None
        last = closes[-1]
        last_i = len(bars) - 1
        head_px = float(head["price"])
        rs_i = _pivot_bar_index(bars, rs)
        rs_neck = _neck_at(n1_px, n1_i, n2_px, n2_i, rs_i if rs_i >= 0 else n2_i)
        raw_last = _neck_at(n1_px, n1_i, n2_px, n2_i, last_i if last_i >= 0 else n2_i)
        confirm_date: Optional[str] = None
        confirm_neck: Optional[float] = None
        collapse_note: Optional[str] = None
        if post_pivot_invalidate_top(bars, rs_i, head_px):
            status = "invalidated"
            conf = 0.2
        else:
            brk = _first_close_break_slanted(
                bars,
                rs_i,
                n1_price=n1_px,
                n1_i=n1_i,
                n2_price=n2_px,
                n2_i=n2_i,
                below=True,
            )
            if brk and brk[0] == "collapse":
                status = "invalidated"
                conf = 0.2
                collapse_note = (
                    f"失效:斜颈外推失真({round(brk[3], 4)})@{brk[2]}"
                )
            elif brk and brk[0] == "break":
                status = "confirmed"
                conf = 0.7
                confirm_date = brk[2]
                confirm_neck = brk[3]
            elif _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=True):
                status = "invalidated"
                conf = 0.2
                collapse_note = f"失效:末日斜颈外推失真({round(raw_last, 4)})"
            else:
                status = "forming"
                conf = 0.5
        if status == "confirmed" and confirm_neck is not None:
            neck_disp = float(confirm_neck)
        elif status == "invalidated" and (
            collapse_note
            or _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=True)
        ):
            neck_disp = _neck_ref_display(n1_px, n2_px, rs_neck)
        else:
            neck_disp = float(raw_last)
        neck_method = (
            "slanted_ref"
            if (
                collapse_note
                or (
                    status == "invalidated"
                    and _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=True)
                )
            )
            else "slanted"
        )
        if status != "invalidated" and rs["price"] <= ls["price"]:
            conf = min(1.0, conf + 0.05)
        reason = (
            f"头肩顶 {fmt_px('左肩', ls['price'], ls.get('date'))} "
            f"{fmt_px('头', head['price'], head.get('date'))} "
            f"{fmt_px('右肩', rs['price'], rs.get('date'))} "
            f"{fmt_px('斜颈', round(neck_disp, 4), approx=True)} "
            f"{fmt_px('峰1', round(n1_px, 4), n1.get('date'))} "
            f"{fmt_px('峰2', round(n2_px, 4), n2.get('date'))}"
        )
        if collapse_note:
            reason += f" {collapse_note}"
        elif status == "invalidated":
            thr = round(head_px * INVALIDATE_TOP_MULT, 4)
            reason += f" 失效:右肩后高点/收盘>头×{INVALIDATE_TOP_MULT}({thr})"
        elif status == "confirmed" and confirm_date:
            cn = confirm_neck if confirm_neck is not None else neck_disp
            if last >= cn:
                reason += f" 破颈确认:{confirm_date}（现价已反抽斜颈上方，状态仍锁存）"
            else:
                reason += f" 破颈确认:{confirm_date}"
        kl: Dict[str, Any] = {
            "left_shoulder": ls["price"],
            "head": head["price"],
            "right_shoulder": rs["price"],
            "neckline": round(neck_disp, 4),
            "neck_left": round(n1_px, 4),
            "neck_right": round(n2_px, 4),
            "neckline_method": neck_method,
            "last_close": round(last, 4),
        }
        if confirm_neck is not None and confirm_neck == confirm_neck:
            kl["confirm_neckline"] = round(float(confirm_neck), 4)
        return make_hit(
            pattern_family="head_shoulders",
            pattern_type="head_shoulders_top",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels=kl,
            pivots=[
                {"role": "LS", "date": ls.get("date"), "price": ls["price"]},
                {"role": "head", "date": head.get("date"), "price": head["price"]},
                {"role": "RS", "date": rs.get("date"), "price": rs["price"]},
                {"role": "neck1", "date": n1.get("date"), "price": round(n1_px, 4)},
                {"role": "neck2", "date": n2.get("date"), "price": round(n2_px, 4)},
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
    depth = HS_HEAD_MIN_DEPTH_PCT
    shoulder_tol = HS_SHOULDER_TOL_PCT
    neck_asym = HS_NECK_ASYMMETRY_MAX

    for end in range(len(pivots), 4, -1):
        win = pivots[end - 5 : end]
        kinds = [p["kind"] for p in win]
        if kinds != ["low", "high", "low", "high", "low"]:
            continue
        ls, n1, head, n2, rs = win
        if not _head_depth_ok_bottom(
            float(head["price"]), float(ls["price"]), float(rs["price"]), depth=depth
        ):
            continue
        if not _shoulder_ok(float(ls["price"]), float(rs["price"]), tol=shoulder_tol):
            continue
        n1_px, n2_px = float(n1["price"]), float(n2["price"])
        if not _neck_asymmetry_ok(n1_px, n2_px, max_asym=neck_asym):
            continue
        n1_i = _pivot_bar_index(bars, n1)
        n2_i = _pivot_bar_index(bars, n2)
        if n1_i < 0 or n2_i < 0:
            continue
        closes = _closes(bars)
        if not closes:
            return None
        last = closes[-1]
        last_i = len(bars) - 1
        head_px = float(head["price"])
        rs_i = _pivot_bar_index(bars, rs)
        rs_neck = _neck_at(n1_px, n1_i, n2_px, n2_i, rs_i if rs_i >= 0 else n2_i)
        raw_last = _neck_at(n1_px, n1_i, n2_px, n2_i, last_i if last_i >= 0 else n2_i)
        confirm_date: Optional[str] = None
        confirm_neck: Optional[float] = None
        collapse_note: Optional[str] = None
        if post_pivot_invalidate_bottom(bars, rs_i, head_px):
            status = "invalidated"
            conf = 0.2
        else:
            brk = _first_close_break_slanted(
                bars,
                rs_i,
                n1_price=n1_px,
                n1_i=n1_i,
                n2_price=n2_px,
                n2_i=n2_i,
                below=False,
            )
            if brk and brk[0] == "collapse":
                status = "invalidated"
                conf = 0.2
                collapse_note = (
                    f"失效:斜颈外推失真({round(brk[3], 4)})@{brk[2]}"
                )
            elif brk and brk[0] == "break":
                status = "confirmed"
                conf = 0.7
                confirm_date = brk[2]
                confirm_neck = brk[3]
            elif _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=False):
                status = "invalidated"
                conf = 0.2
                collapse_note = f"失效:末日斜颈外推失真({round(raw_last, 4)})"
            else:
                status = "forming"
                conf = 0.5
        if status == "confirmed" and confirm_neck is not None:
            neck_disp = float(confirm_neck)
        elif status == "invalidated" and (
            collapse_note
            or _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=False)
        ):
            neck_disp = _neck_ref_display(n1_px, n2_px, rs_neck)
        else:
            neck_disp = float(raw_last)
        neck_method = (
            "slanted_ref"
            if (
                collapse_note
                or (
                    status == "invalidated"
                    and _slant_neck_collapsed(raw_last, n1_px, n2_px, is_top=False)
                )
            )
            else "slanted"
        )
        if status != "invalidated" and rs["price"] >= ls["price"]:
            conf = min(1.0, conf + 0.05)
        reason = (
            f"头肩底 {fmt_px('左肩', ls['price'], ls.get('date'))} "
            f"{fmt_px('头', head['price'], head.get('date'))} "
            f"{fmt_px('右肩', rs['price'], rs.get('date'))} "
            f"{fmt_px('斜颈', round(neck_disp, 4), approx=True)} "
            f"{fmt_px('峰1', round(n1_px, 4), n1.get('date'))} "
            f"{fmt_px('峰2', round(n2_px, 4), n2.get('date'))}"
        )
        if collapse_note:
            reason += f" {collapse_note}"
        elif status == "invalidated":
            thr = round(head_px * INVALIDATE_BOTTOM_MULT, 4)
            reason += f" 失效:右肩后低点/收盘<头×{INVALIDATE_BOTTOM_MULT}({thr})"
        elif status == "confirmed" and confirm_date:
            cn = confirm_neck if confirm_neck is not None else neck_disp
            if last <= cn:
                reason += f" 破颈确认:{confirm_date}（现价已回落斜颈下方，状态仍锁存）"
            else:
                reason += f" 破颈确认:{confirm_date}"
        kl: Dict[str, Any] = {
            "left_shoulder": ls["price"],
            "head": head["price"],
            "right_shoulder": rs["price"],
            "neckline": round(neck_disp, 4),
            "neck_left": round(n1_px, 4),
            "neck_right": round(n2_px, 4),
            "neckline_method": neck_method,
            "last_close": round(last, 4),
        }
        if confirm_neck is not None and confirm_neck == confirm_neck:
            kl["confirm_neckline"] = round(float(confirm_neck), 4)
        return make_hit(
            pattern_family="head_shoulders",
            pattern_type="head_shoulders_bottom",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels=kl,
            pivots=[
                {"role": "LS", "date": ls.get("date"), "price": ls["price"]},
                {"role": "head", "date": head.get("date"), "price": head["price"]},
                {"role": "RS", "date": rs.get("date"), "price": rs["price"]},
                {"role": "neck1", "date": n1.get("date"), "price": round(n1_px, 4)},
                {"role": "neck2", "date": n2.get("date"), "price": round(n2_px, 4)},
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
