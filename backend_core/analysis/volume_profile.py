# -*- coding: utf-8 -*-
"""轻量日线 Volume Profile：固定回看 + POC / VAH / VAL（参考用，不作策略硬门槛）。

日线无分笔时：将每日成交量均匀分摊到当日 [low, high] 覆盖的价格桶。
价值区默认覆盖总成交量的 70%（自 POC 向两侧扩展）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_LOOKBACK = 60
DEFAULT_BIN_COUNT = 24
DEFAULT_VALUE_AREA_PCT = 0.70
PRICE_DECIMALS = 2
ALIGN_TOL_PCT = 0.015  # 与 KDE 价位「共振」相对阈值


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None  # NaN check
    except (TypeError, ValueError):
        return None


def _parse_bar(bar: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    h = _f(bar.get("high"))
    lo = _f(bar.get("low"))
    c = _f(bar.get("close"))
    vol = _f(bar.get("volume"))
    if h is None or lo is None or vol is None or vol <= 0:
        return None
    if h < lo:
        h, lo = lo, h
    if c is None:
        c = (h + lo) / 2.0
    return h, lo, c, vol


def compute_volume_profile_from_bars(
    bars: Sequence[Dict[str, Any]],
    *,
    last_close: Optional[float] = None,
    lookback: int = DEFAULT_LOOKBACK,
    bin_count: int = DEFAULT_BIN_COUNT,
    value_area_pct: float = DEFAULT_VALUE_AREA_PCT,
) -> Dict[str, Any]:
    """从日线 bars 计算 Volume Profile。

    返回 poc / vah / val、相对现价最近支撑压力，以及 bins 摘要（价位中点与量）。
    """
    def _bar_date(b: Dict[str, Any]) -> Optional[str]:
        raw = b.get("date") if b.get("date") is not None else b.get("trade_date")
        if raw is None:
            return None
        s = str(raw).strip()
        return s[:10] if s else None

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    lb = max(5, int(lookback or DEFAULT_LOOKBACK))
    if len(seq) > lb:
        seq = seq[-lb:]

    window_start = next((d for d in (_bar_date(b) for b in seq) if d), None)
    window_end = None
    for b in reversed(seq):
        d = _bar_date(b)
        if d:
            window_end = d
            break

    empty: Dict[str, Any] = {
        "ok": False,
        "reason": "insufficient_bars",
        "method": "daily_volume_profile",
        "lookback": int(lb),
        "bars_used": len(seq),
        "window_start": window_start,
        "window_end": window_end,
        "bin_count": int(bin_count),
        "value_area_pct": float(value_area_pct),
        "poc": None,
        "vah": None,
        "val": None,
        "nearest_support": None,
        "nearest_resistance": None,
        "support_note": None,
        "resistance_note": None,
        "last_close": None,
        "bins": [],
        "total_volume": 0.0,
    }
    parsed: List[Tuple[float, float, float, float]] = []
    for b in seq:
        t = _parse_bar(b)
        if t:
            parsed.append(t)
    if len(parsed) < 5:
        return empty

    price_lo = min(x[1] for x in parsed)
    price_hi = max(x[0] for x in parsed)
    if price_hi <= price_lo:
        empty["reason"] = "zero_range"
        return empty

    n_bins = max(8, min(48, int(bin_count or DEFAULT_BIN_COUNT)))
    width = (price_hi - price_lo) / n_bins
    if width <= 0:
        empty["reason"] = "zero_bin_width"
        return empty

    volumes = [0.0] * n_bins
    centers = [price_lo + (i + 0.5) * width for i in range(n_bins)]

    for h, lo, _c, vol in parsed:
        # 桶索引：覆盖 [lo, h]
        i0 = int((lo - price_lo) / width)
        i1 = int((h - price_lo) / width)
        i0 = max(0, min(n_bins - 1, i0))
        i1 = max(0, min(n_bins - 1, i1))
        if i1 < i0:
            i0, i1 = i1, i0
        span = i1 - i0 + 1
        share = float(vol) / float(span)
        for i in range(i0, i1 + 1):
            volumes[i] += share

    total = sum(volumes)
    if total <= 0:
        empty["reason"] = "zero_volume"
        return empty

    poc_i = max(range(n_bins), key=lambda i: volumes[i])
    poc = centers[poc_i]

    # 自 POC 向两侧扩展至价值区占比
    target = total * float(value_area_pct or DEFAULT_VALUE_AREA_PCT)
    if target <= 0:
        target = total * DEFAULT_VALUE_AREA_PCT
    left = right = poc_i
    covered = volumes[poc_i]
    while covered < target and (left > 0 or right < n_bins - 1):
        left_vol = volumes[left - 1] if left > 0 else -1.0
        right_vol = volumes[right + 1] if right < n_bins - 1 else -1.0
        if right_vol > left_vol:
            right += 1
            covered += volumes[right]
        elif left_vol >= 0:
            left -= 1
            covered += volumes[left]
        else:
            break

    val = price_lo + left * width
    vah = price_lo + (right + 1) * width
    # 价值区边界用桶边；展示价取两位
    d = PRICE_DECIMALS
    poc_r = round(poc, d)
    val_r = round(val, d)
    vah_r = round(vah, d)

    last_c = _f(last_close)
    if last_c is None:
        last_c = parsed[-1][2]

    # 参考支撑/压力：现价下取 VAL/POC 中最近；上方取 VAH/POC 中最近
    below = [x for x in (val_r, poc_r) if last_c is not None and x < last_c]
    above = [x for x in (vah_r, poc_r) if last_c is not None and x > last_c]
    nearest_s = max(below) if below else None
    nearest_r = min(above) if above else None

    used_n = len(seq)
    support_note = None
    resistance_note = None
    if last_c is not None:
        if nearest_r is None and vah_r is not None and last_c > vah_r:
            resistance_note = (
                f"已突破{used_n}日VAH({vah_r:.{d}f})，上方无{used_n}日筹码压制"
            )
        if nearest_s is None and val_r is not None and last_c < val_r:
            support_note = (
                f"已跌破{used_n}日VAL({val_r:.{d}f})，下方无{used_n}日筹码承接"
            )

    bins_out = [
        {"price": round(centers[i], d), "volume": round(volumes[i], 2)}
        for i in range(n_bins)
        if volumes[i] > 0
    ]

    return {
        "ok": True,
        "reason": "ok",
        "method": "daily_volume_profile",
        "lookback": lb,
        "bars_used": used_n,
        "window_start": window_start,
        "window_end": window_end,
        "bin_count": n_bins,
        "value_area_pct": float(value_area_pct or DEFAULT_VALUE_AREA_PCT),
        "poc": poc_r,
        "vah": vah_r,
        "val": val_r,
        "nearest_support": nearest_s,
        "nearest_resistance": nearest_r,
        "support_note": support_note,
        "resistance_note": resistance_note,
        "last_close": round(last_c, d) if last_c is not None else None,
        "bins": bins_out,
        "total_volume": round(total, 2),
        "price_low": round(price_lo, d),
        "price_high": round(price_hi, d),
    }


def compare_vp_with_kde(
    vp: Optional[Dict[str, Any]],
    *,
    kde_support: Optional[float],
    kde_resistance: Optional[float],
    price: Optional[float] = None,
    tol_pct: float = ALIGN_TOL_PCT,
) -> Dict[str, Any]:
    """KDE 最近支撑/压力 vs VP 最近支撑/压力（及 VAL/VAH）对比摘要。"""
    out: Dict[str, Any] = {
        "support": None,
        "resistance": None,
        "notes": [],
    }
    if not vp or not vp.get("ok"):
        out["notes"].append("volume_profile_unavailable")
        return out

    px = _f(price) or _f(vp.get("last_close"))
    ks = _f(kde_support)
    kr = _f(kde_resistance)
    vs = _f(vp.get("nearest_support"))
    vr = _f(vp.get("nearest_resistance"))
    val = _f(vp.get("val"))
    vah = _f(vp.get("vah"))
    poc = _f(vp.get("poc"))

    def _side_vp(*, below: bool) -> Optional[float]:
        """按现价分侧取 VP 对照位：优先 nearest_*，否则在 VAL/VAH/POC 中同侧兜底。"""
        preferred = vs if below else vr
        if preferred is not None:
            if px is None:
                return preferred
            if below and preferred < px:
                return preferred
            if (not below) and preferred > px:
                return preferred
        cands = [x for x in (val, vah, poc) if x is not None]
        if px is not None:
            if below:
                cands = [x for x in cands if x < px]
                return max(cands) if cands else None
            cands = [x for x in cands if x > px]
            return min(cands) if cands else None
        # 无现价时：支撑偏 VAL/POC，压力偏 VAH/POC
        if below:
            return preferred if preferred is not None else (val if val is not None else poc)
        return preferred if preferred is not None else (vah if vah is not None else poc)

    def _pair(kde_v: Optional[float], vp_v: Optional[float], label: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "kde": round(kde_v, PRICE_DECIMALS) if kde_v is not None else None,
            "vp": round(vp_v, PRICE_DECIMALS) if vp_v is not None else None,
            "diff": None,
            "diff_pct": None,
            "aligned": False,
        }
        if kde_v is None or vp_v is None:
            return row
        diff = float(vp_v) - float(kde_v)
        row["diff"] = round(diff, PRICE_DECIMALS)
        base = abs(float(kde_v)) if abs(float(kde_v)) > 1e-9 else (abs(px) if px else 1.0)
        pct = abs(diff) / base
        row["diff_pct"] = round(pct * 100.0, 2)
        row["aligned"] = pct <= float(tol_pct)
        if row["aligned"]:
            out["notes"].append(f"{label}_aligned")
        return row

    out["support"] = _pair(ks, _side_vp(below=True), "support")
    out["resistance"] = _pair(kr, _side_vp(below=False), "resistance")
    out["poc"] = round(poc, PRICE_DECIMALS) if poc is not None else None
    out["val"] = round(val, PRICE_DECIMALS) if val is not None else None
    out["vah"] = round(vah, PRICE_DECIMALS) if vah is not None else None

    used_n = int(vp.get("bars_used") or vp.get("lookback") or DEFAULT_LOOKBACK)
    d = PRICE_DECIMALS
    if out["resistance"] and out["resistance"].get("vp") is None:
        note = vp.get("resistance_note")
        if not note and px is not None and vah is not None and px > vah:
            note = f"已突破{used_n}日VAH({vah:.{d}f})，上方无{used_n}日筹码压制"
        if note:
            out["resistance"]["note"] = note
            out["notes"].append("resistance_above_vah")
    if out["support"] and out["support"].get("vp") is None:
        note = vp.get("support_note")
        if not note and px is not None and val is not None and px < val:
            note = f"已跌破{used_n}日VAL({val:.{d}f})，下方无{used_n}日筹码承接"
        if note:
            out["support"]["note"] = note
            out["notes"].append("support_below_val")
    return out
