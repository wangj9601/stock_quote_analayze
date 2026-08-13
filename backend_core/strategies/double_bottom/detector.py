# -*- coding: utf-8 -*-
"""经典 W 双底识别：forming（形态成立未突破）/ confirmed（收盘突破颈线）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _bar_date(bar: Dict[str, Any]) -> str:
    raw = bar.get("date") if bar.get("date") is not None else bar.get("trade_date")
    return str(raw or "")[:10]


def _local_troughs(
    lows: Sequence[float],
    *,
    left: int,
    right: int,
) -> List[int]:
    """返回局部低点下标（升序）。"""
    n = len(lows)
    L = max(1, int(left))
    R = max(1, int(right))
    out: List[int] = []
    for i in range(L, n - R):
        lo = lows[i]
        ok = True
        for j in range(i - L, i):
            if lows[j] < lo:
                ok = False
                break
        if not ok:
            continue
        for j in range(i + 1, i + R + 1):
            if lows[j] < lo:
                ok = False
                break
        if ok:
            out.append(i)
    return out


def detect_double_bottom(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """从升序日线 bars 识别最近一对双底。

    返回命中 dict，或 None。
    """
    cfg = dict(pattern_cfg or {})
    lookback = max(30, int(cfg.get("lookback_days") or 120))
    swing_left = int(cfg.get("swing_left") or 3)
    swing_right = int(cfg.get("swing_right") or 3)
    min_gap = max(2, int(cfg.get("min_trough_gap_bars") or 8))
    max_gap = max(min_gap, int(cfg.get("max_trough_gap_bars") or 60))
    tol = float(cfg.get("trough_tol_pct") or 0.03)
    min_rise = float(cfg.get("min_rise_to_neck_pct") or 0.05)
    # 深度上限：谷到颈线过大视为伪双底（默认 15%；传极大值可关闭）
    max_rise = float(cfg.get("max_rise_to_neck_pct") if cfg.get("max_rise_to_neck_pct") is not None else 0.15)
    confirm_close = bool(cfg.get("confirm_close_above", True))
    buffer_pct = float(cfg.get("confirm_buffer_pct") or 0.0)
    require_vol = bool(cfg.get("require_volume_expand", False))
    vol_lb = max(5, int(cfg.get("volume_lookback") or 20))
    vol_ratio = float(cfg.get("volume_expand_ratio") or 1.2)

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) > lookback:
        seq = list(seq[-lookback:])
    if len(seq) < min_gap + swing_left + swing_right + 5:
        return None

    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    vols: List[Optional[float]] = []
    for b in seq:
        h = _f(b.get("high"))
        lo = _f(b.get("low"))
        c = _f(b.get("close"))
        if h is None or lo is None or c is None:
            return None
        if h < lo:
            h, lo = lo, h
        highs.append(h)
        lows.append(lo)
        closes.append(c)
        vols.append(_f(b.get("volume")))

    troughs = _local_troughs(lows, left=swing_left, right=swing_right)
    if len(troughs) < 2:
        return None

    # 从最近低点往前找合法 L1/L2（L2 更新）
    best: Optional[Tuple[int, int]] = None
    for j in range(len(troughs) - 1, 0, -1):
        i2 = troughs[j]
        for i in range(j - 1, -1, -1):
            i1 = troughs[i]
            gap = i2 - i1
            if gap < min_gap or gap > max_gap:
                continue
            p1, p2 = lows[i1], lows[i2]
            mid = (p1 + p2) / 2.0
            if mid <= 0:
                continue
            if abs(p1 - p2) / mid > tol:
                continue
            # 中间颈线
            if i2 - i1 < 2:
                continue
            neck_slice = highs[i1 + 1 : i2]
            if not neck_slice:
                continue
            neck = max(neck_slice)
            neck_rel = i1 + 1 + neck_slice.index(neck)
            base = min(p1, p2)
            if base <= 0:
                continue
            depth = (neck - base) / base
            if depth < min_rise:
                continue
            if max_rise > 0 and depth > max_rise:
                continue  # 硬否决过深伪形态
            # 第二底之后不应再明显破底（容差内）
            after_lows = lows[i2 + 1 :]
            if after_lows and min(after_lows) < base * (1.0 - tol):
                continue
            best = (i1, i2)
            break
        if best:
            break

    if not best:
        return None

    i1, i2 = best
    p1, p2 = lows[i1], lows[i2]
    neck_slice = highs[i1 + 1 : i2]
    neck = max(neck_slice)
    neck_rel = i1 + 1 + neck_slice.index(neck)
    last_close = closes[-1]
    threshold = neck * (1.0 + buffer_pct)

    confirmed = False
    confirm_date = None
    if confirm_close:
        # 第二底之后任一收盘突破；记录首次突破日
        for k in range(i2 + 1, len(closes)):
            if closes[k] > threshold:
                # 可选量能
                if require_vol:
                    win = [v for v in vols[max(0, k - vol_lb) : k] if v is not None and v > 0]
                    cur_v = vols[k]
                    if not win or cur_v is None or cur_v <= 0:
                        continue
                    avg_v = sum(win) / len(win)
                    if avg_v <= 0 or cur_v < avg_v * vol_ratio:
                        continue
                confirmed = True
                confirm_date = _bar_date(seq[k])
                break
    else:
        confirmed = last_close > threshold
        if confirmed:
            confirm_date = _bar_date(seq[-1])

    status = "confirmed" if confirmed else "forming"
    base = min(p1, p2)
    return {
        "ok": True,
        "status": status,
        "l1_index": i1,
        "l2_index": i2,
        "l1_date": _bar_date(seq[i1]),
        "l2_date": _bar_date(seq[i2]),
        "l1_price": round(p1, 4),
        "l2_price": round(p2, 4),
        "neckline": round(neck, 4),
        "neck_date": _bar_date(seq[neck_rel]),
        "last_close": round(last_close, 4),
        "confirm_date": confirm_date,
        "trough_tol_pct": tol,
        "trough_gap_bars": i2 - i1,
        "rise_to_neck_pct": round((neck - base) / base, 4) if base > 0 else None,
        "lookback_used": len(seq),
    }
