# -*- coding: utf-8 -*-
"""带柄茶杯形态（Cup with Handle）启发式检测。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .pivots import extract_pivot_sequence
from .rules import consolidation_status
from .schema import fmt_px, make_hit

# 杯身 / 柄部几何阈值（可随回归微调）
_MIN_BARS = 50
_MIN_CUP_BARS = 20
_MIN_HANDLE_BARS = 5
_MAX_HANDLE_BARS = 40
_RIM_REL_TOL = 0.12  # 左右沿相对差
_CUP_DEPTH_MIN = 0.12  # 相对左沿深度下限
_CUP_DEPTH_MAX = 0.50  # 相对左沿深度上限
_HANDLE_DEPTH_MIN = 0.05  # 柄回撤 / 杯深
_HANDLE_DEPTH_MAX = 0.35
_HANDLE_FLOOR_FRAC = 0.40  # 柄低不得跌破 杯底 + 40%*杯深


def _closes(bars: Sequence[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for b in bars:
        try:
            c = float(b.get("close"))
            if c == c and c > 0:
                out.append(c)
        except (TypeError, ValueError):
            continue
    return out


def _bar_date(bars: Sequence[Dict[str, Any]], idx: int) -> str:
    if idx < 0 or idx >= len(bars):
        return ""
    return str(bars[idx].get("date") or "")[:10]


def _find_cup_and_handle(
    closes: Sequence[float],
) -> Optional[Tuple[int, int, int, int, int]]:
    """
    返回 (left_rim_i, cup_bottom_i, right_rim_i, handle_low_i, handle_end_i)。
    索引相对 closes；失败返回 None。
    """
    n = len(closes)
    if n < _MIN_BARS:
        return None

    # 在近端窗口内搜索（保留足够历史形成杯身）
    win = closes[-min(n, 160) :]
    offset = n - len(win)
    w = len(win)
    if w < _MIN_BARS:
        return None

    best: Optional[Tuple[float, Tuple[int, int, int, int, int]]] = None

    # 杯底：窗口中段附近的最低点
    search_lo = max(10, w // 5)
    search_hi = min(w - 15, (4 * w) // 5)
    if search_hi <= search_lo + _MIN_CUP_BARS:
        return None

    for bi in range(search_lo, search_hi + 1):
        bottom = win[bi]
        # 左沿：杯底左侧最高点
        left_slice = win[:bi]
        if len(left_slice) < 8:
            continue
        li = max(range(len(left_slice)), key=lambda i: left_slice[i])
        left = left_slice[li]
        if left <= 0 or bi - li < 8:
            continue
        depth = left - bottom
        depth_pct = depth / left
        if depth_pct < _CUP_DEPTH_MIN or depth_pct > _CUP_DEPTH_MAX:
            continue

        # 右沿：杯底右侧回到左沿附近的高点；一旦出现够深的柄回撤则冻结右沿，
        # 避免后续突破新高把右沿「抬走」导致柄部消失。
        right_region = win[bi + 1 :]
        if len(right_region) < _MIN_HANDLE_BARS + 5:
            continue
        ri_local = None
        right_px = None
        rim_frozen = False
        for j, px in enumerate(right_region):
            abs_j = bi + 1 + j
            near_rim = (
                abs(px - left) / left <= _RIM_REL_TOL
                and px >= left * (1.0 - _RIM_REL_TOL)
            )
            if near_rim and not rim_frozen:
                if right_px is None or px >= right_px:
                    right_px = px
                    ri_local = abs_j
            # 相对已锁定右沿回撤达到柄深下限 → 冻结，后续再创新高也不抬沿
            if ri_local is not None and right_px is not None and not rim_frozen:
                if (right_px - px) / depth >= _HANDLE_DEPTH_MIN:
                    rim_frozen = True
            if ri_local is not None and abs_j - ri_local > _MAX_HANDLE_BARS + 5:
                break
        if ri_local is None or right_px is None:
            continue
        if ri_local - li < _MIN_CUP_BARS:
            continue
        if abs(right_px - left) / left > _RIM_REL_TOL:
            continue

        # 柄部：右沿之后、至多 MAX_HANDLE_BARS；首次明显站上右沿视为柄结束
        after = win[ri_local + 1 :]
        if len(after) < _MIN_HANDLE_BARS:
            continue
        handle_len = min(len(after), _MAX_HANDLE_BARS)
        cut = handle_len
        for k in range(handle_len):
            if after[k] > right_px * (1.0 + 0.002):
                # 突破点本身不算柄；至少保留 MIN 根柄 K
                cut = k if k >= _MIN_HANDLE_BARS else _MIN_HANDLE_BARS
                break
        handle_len = min(max(cut, _MIN_HANDLE_BARS), len(after), _MAX_HANDLE_BARS)
        handle_seg = after[:handle_len]
        hli_rel = min(range(len(handle_seg)), key=lambda i: handle_seg[i])
        handle_low = handle_seg[hli_rel]
        handle_low_i = ri_local + 1 + hli_rel
        handle_end_i = ri_local + handle_len

        handle_retrace = right_px - handle_low
        if handle_retrace <= 0:
            continue
        retrace_frac = handle_retrace / depth
        if retrace_frac < _HANDLE_DEPTH_MIN or retrace_frac > _HANDLE_DEPTH_MAX:
            continue
        # 柄不能破坏杯底结构
        floor = bottom + depth * _HANDLE_FLOOR_FRAC
        if handle_low < floor:
            continue
        # 柄长须短于杯身
        cup_len = ri_local - li
        if handle_len >= cup_len:
            continue
        if handle_len < _MIN_HANDLE_BARS:
            continue

        # 评分：左右沿更齐、柄更浅、杯深适中优先
        rim_align = 1.0 - abs(right_px - left) / left
        shallow = 1.0 - retrace_frac
        depth_score = 1.0 - abs(depth_pct - 0.25) / 0.25
        score = rim_align * 0.4 + shallow * 0.35 + max(0.0, depth_score) * 0.25
        cand = (
            offset + li,
            offset + bi,
            offset + ri_local,
            offset + handle_low_i,
            offset + handle_end_i,
        )
        if best is None or score > best[0]:
            best = (score, cand)

    return None if best is None else best[1]


def detect_cup_with_handle(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """检测带柄茶杯；无命中返回空列表。"""
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    closes = _closes(seq)
    if len(closes) < _MIN_BARS or len(closes) != len(seq):
        # closes 与 bars 索引可能因坏点错位：退化为按 bars 重算对齐索引
        aligned: List[Dict[str, Any]] = []
        closes = []
        for b in seq:
            try:
                c = float(b.get("close"))
            except (TypeError, ValueError):
                continue
            if c != c or c <= 0:
                continue
            aligned.append(b)
            closes.append(c)
        seq = aligned
    if len(closes) < _MIN_BARS:
        return []

    # pivots 预留：当前算法以收盘序列为主；保留参数与其它检测器签名一致
    _ = pivots if pivots is not None else extract_pivot_sequence(seq)

    found = _find_cup_and_handle(closes)
    if not found:
        return []
    li, bi, ri, hli, hei = found
    left = closes[li]
    bottom = closes[bi]
    right = closes[ri]
    handle_low = closes[hli]
    rim = max(left, right)
    last_c = closes[-1]
    upper = rim
    lower = handle_low

    status, st_note = consolidation_status(
        last_c, upper, lower, expect_up=True
    )
    if status == "confirmed":
        conf = 0.60
    elif status == "invalidated":
        conf = 0.22
    else:
        conf = 0.46

    depth = rim - bottom
    handle_retrace = rim - handle_low
    reason = (
        f"带柄茶杯 "
        f"{fmt_px('左沿', round(left, 4), _bar_date(seq, li))} "
        f"{fmt_px('杯底', round(bottom, 4), _bar_date(seq, bi))} "
        f"{fmt_px('右沿', round(right, 4), _bar_date(seq, ri))} "
        f"{fmt_px('柄低', round(handle_low, 4), _bar_date(seq, hli))} "
        f"杯深={round(depth / rim * 100, 1)}% "
        f"柄回撤={round(handle_retrace / depth * 100, 1)}%杯深"
    )
    if st_note:
        reason = f"{reason} {st_note}"

    return [
        make_hit(
            pattern_family="cup_handle",
            pattern_type="cup_with_handle",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels={
                "upper": round(upper, 4),
                "lower": round(lower, 4),
                "rim": round(rim, 4),
                "cup_bottom": round(bottom, 4),
                "left_rim": round(left, 4),
                "right_rim": round(right, 4),
                "handle_low": round(handle_low, 4),
                "last_close": round(last_c, 4),
                "cup_depth_pct": round(depth / rim * 100, 2),
                "handle_retrace_pct_of_cup": round(handle_retrace / depth * 100, 2)
                if depth > 0
                else None,
            },
            pivots=[
                {"role": "left_rim", "date": _bar_date(seq, li), "price": left},
                {"role": "cup_bottom", "date": _bar_date(seq, bi), "price": bottom},
                {"role": "right_rim", "date": _bar_date(seq, ri), "price": right},
                {"role": "handle_low", "date": _bar_date(seq, hli), "price": handle_low},
            ],
            extra={
                "simplified": True,
                "handle_end_date": _bar_date(seq, min(hei, len(seq) - 1)),
            },
        )
    ]
