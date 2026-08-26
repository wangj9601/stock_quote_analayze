# -*- coding: utf-8 -*-
"""杯底形态识别（O'Neil 带柄杯底增强版）。

forming：柄部形成未突破杯口；confirmed：收盘突破杯口且可选放量确认。
输出含 grade（A/B/C/X）、volume_score、quality_flags。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.chart_patterns.rules import breakout_down, breakout_up


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


def _series(bars: Sequence[Dict[str, Any]], key: str) -> List[float]:
    out: List[float] = []
    for b in bars:
        v = _f(b.get(key))
        if v is not None and v > 0:
            out.append(v)
        else:
            out.append(float("nan"))
    return out


def _volume_series(bars: Sequence[Dict[str, Any]]) -> List[float]:
    out: List[float] = []
    for b in bars:
        v = None
        for k in ("volume", "vol", "turnover_vol", "amount"):
            v = _f(b.get(k))
            if v is not None and v > 0:
                break
        out.append(v if v is not None and v > 0 else float("nan"))
    return out


def _rolling_mean(vals: Sequence[float], window: int) -> List[float]:
    w = max(1, int(window))
    out: List[float] = []
    for i in range(len(vals)):
        chunk = [v for v in vals[max(0, i - w + 1) : i + 1] if v == v and v > 0]
        out.append(sum(chunk) / len(chunk) if chunk else float("nan"))
    return out


def _parse_cfg(pattern_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = dict(pattern_cfg or {})
    vol = dict(cfg.get("volume") or {})
    return {
        "lookback_days": max(50, int(cfg.get("lookback_days") or 160)),
        "min_bars": max(30, int(cfg.get("min_bars") or 50)),
        "min_cup_bars": max(10, int(cfg.get("min_cup_bars") or 20)),
        "min_handle_bars": max(3, int(cfg.get("min_handle_bars") or 5)),
        "max_handle_bars": max(5, int(cfg.get("max_handle_bars") or 20)),
        "rim_rel_tol": float(cfg.get("rim_rel_tol") or 0.12),
        "cup_depth_min": float(cfg.get("cup_depth_min") or 0.12),
        "cup_depth_max": float(cfg.get("cup_depth_max") or 0.33),
        "handle_depth_min": float(cfg.get("handle_depth_min") or 0.05),
        "handle_depth_max": float(cfg.get("handle_depth_max") or 0.35),
        "handle_floor_frac": float(cfg.get("handle_floor_frac") or 0.50),
        "handle_retrace_of_rim_min": float(cfg.get("handle_retrace_of_rim_min") or 0.08),
        "handle_retrace_of_rim_max": float(cfg.get("handle_retrace_of_rim_max") or 0.18),
        "confirm_close_above": bool(cfg.get("confirm_close_above", True)),
        "confirm_buffer_pct": float(cfg.get("confirm_buffer_pct") or 0.005),
        "exclude_invalidated": bool(cfg.get("exclude_invalidated", True)),
        "use_low_for_bottom": bool(cfg.get("use_low_for_bottom", True)),
        "use_high_for_rim": bool(cfg.get("use_high_for_rim", True)),
        "invalidate_on_lower_low": bool(cfg.get("invalidate_on_lower_low", True)),
        "lower_low_tol_pct": float(cfg.get("lower_low_tol_pct") or 0.005),
        "prior_trend_min_pct": float(cfg.get("prior_trend_min_pct") or 0.30),
        "prior_trend_lookback": max(40, int(cfg.get("prior_trend_lookback") or 120)),
        "prior_trend_required": bool(cfg.get("prior_trend_required", True)),
        "cup_bottom_flat_bars": max(1, int(cfg.get("cup_bottom_flat_bars") or 3)),
        "cup_bottom_flat_pct": float(cfg.get("cup_bottom_flat_pct") or 0.03),
        "cup_symmetry_max_ratio": float(cfg.get("cup_symmetry_max_ratio") or 0.40),
        "cup_u_shape_required": bool(cfg.get("cup_u_shape_required", True)),
        "reject_upward_handle": bool(cfg.get("reject_upward_handle", True)),
        "extended_cup_bars": max(40, int(cfg.get("extended_cup_bars") or 60)),
        "grade_filter": str(cfg.get("grade_filter") or "all").strip().lower(),
        "volume_enabled": bool(vol.get("enabled", True)),
        "volume_ma_window": max(10, int(vol.get("ma_window") or 50)),
        "volume_bottom_shrink_ratio": float(vol.get("bottom_shrink_ratio") or 0.70),
        "volume_handle_shrink_ratio": float(vol.get("handle_shrink_ratio") or 0.65),
        "volume_breakout_expand_ratio": float(vol.get("breakout_expand_ratio") or 1.40),
        "volume_right_expand_min_days": max(1, int(vol.get("right_expand_min_days") or 3)),
        "volume_require_confirm": bool(vol.get("require_volume_confirm", False)),
        "volume_require_all": bool(vol.get("require_all", False)),
    }


def _lin_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den > 1e-12 else 0.0


def _no_lower_low(
    lows: Sequence[float],
    start: int,
    end: int,
    floor_px: float,
    tol_pct: float,
) -> bool:
    thr = floor_px * (1.0 - tol_pct)
    for k in range(start, min(end + 1, len(lows))):
        lk = lows[k]
        if lk == lk and lk < thr:
            return False
    return True


def _check_prior_trend(
    closes: Sequence[float],
    li: int,
    left: float,
    *,
    lookback: int,
    min_pct: float,
) -> bool:
    if li < 10:
        return False
    lo = max(0, li - lookback)
    seg = [c for c in closes[lo:li] if c == c and c > 0]
    if not seg:
        return False
    base = min(seg)
    if base <= 0:
        return False
    return (left / base - 1.0) >= min_pct


def _check_u_shape(
    closes: Sequence[float],
    lows: Sequence[float],
    li: int,
    bi: int,
    ri: int,
    depth: float,
    *,
    flat_bars: int,
    flat_pct: float,
    symmetry_max: float,
) -> Tuple[bool, bool]:
    """返回 (u_ok, extended_base_hint)。"""
    if depth <= 0 or ri <= bi or bi <= li:
        return False, False
    flat_thr = depth * flat_pct
    flat_n = 0
    lo = max(li + 1, bi - flat_bars)
    hi = min(ri - 1, bi + flat_bars)
    bottom_ref = lows[bi] if lows[bi] == lows[bi] else closes[bi]
    for k in range(lo, hi + 1):
        c = closes[k]
        if c == c and abs(c - bottom_ref) <= flat_thr:
            flat_n += 1
    u_flat = flat_n >= flat_bars
    left_len = bi - li
    right_len = ri - bi
    sym = abs(left_len - right_len) / max(left_len + right_len, 1)
    u_sym = sym <= symmetry_max
    left_slope = depth / max(left_len, 1)
    right_slope = depth / max(right_len, 1)
    slope_ratio = left_slope / right_slope if right_slope > 1e-9 else 999.0
    u_slope = 0.25 <= slope_ratio <= 4.0
    extended = (ri - li) >= 60
    return (u_flat and u_sym and u_slope), extended


def _volume_flags(
    volumes: Sequence[float],
    vol_ma: Sequence[float],
    li: int,
    bi: int,
    ri: int,
    hli: int,
    hei: int,
    confirm_i: Optional[int],
    cfg: Dict[str, Any],
) -> Dict[str, bool]:
    if not cfg["volume_enabled"]:
        return {
            "bottom_shrink": True,
            "right_expand": True,
            "handle_shrink": True,
            "breakout_expand": True,
        }
    bottom_shrink = False
    vb = volumes[bi] if bi < len(volumes) else float("nan")
    mab = vol_ma[bi] if bi < len(vol_ma) else float("nan")
    if vb == vb and mab == mab and mab > 0:
        bottom_shrink = vb <= mab * cfg["volume_bottom_shrink_ratio"]
    right_expand = 0
    for k in range(bi + 1, ri):
        vk, mk = volumes[k], vol_ma[k]
        if vk == vk and mk == mk and mk > 0 and vk > mk:
            right_expand += 1
    right_ok = right_expand >= cfg["volume_right_expand_min_days"]
    h0, h1 = ri + 1, min(hei + 1, len(volumes))
    hseg = [volumes[k] for k in range(h0, h1) if volumes[k] == volumes[k]]
    hm = vol_ma[hei] if hei < len(vol_ma) else float("nan")
    handle_shrink = False
    if hseg and hm == hm and hm > 0:
        handle_shrink = (sum(hseg) / len(hseg)) <= hm * cfg["volume_handle_shrink_ratio"]
    breakout_expand = True
    if confirm_i is not None and confirm_i < len(volumes):
        vc, mc = volumes[confirm_i], vol_ma[confirm_i]
        if vc == vc and mc == mc and mc > 0:
            breakout_expand = vc >= mc * cfg["volume_breakout_expand_ratio"]
    return {
        "bottom_shrink": bottom_shrink,
        "right_expand": right_ok,
        "handle_shrink": handle_shrink,
        "breakout_expand": breakout_expand,
    }


def _grade_from_flags(
    *,
    structure_ok: bool,
    vol_flags: Dict[str, bool],
    extended: bool,
    invalidated: bool,
    cfg: Dict[str, Any],
) -> str:
    if invalidated or not structure_ok:
        return "X"
    vol_pass = sum(1 for v in vol_flags.values() if v)
    if extended and vol_pass < 4:
        return "C"
    if vol_pass >= 3:
        return "A"
    if vol_pass >= 1:
        return "B"
    return "C"


def _find_candidates(
    seq: Sequence[Dict[str, Any]],
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    vol_ma: Sequence[float],
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    n = len(closes)
    lookback = min(n, cfg["lookback_days"])
    win_c = closes[-lookback:]
    win_h = highs[-lookback:]
    win_l = lows[-lookback:]
    win_v = volumes[-lookback:]
    win_ma = vol_ma[-lookback:]
    offset = n - lookback
    w = len(win_c)
    if w < cfg["min_bars"]:
        return []

    cands: List[Dict[str, Any]] = []
    search_lo = max(10, w // 5)
    search_hi = min(w - 15, (4 * w) // 5)
    if search_hi <= search_lo + cfg["min_cup_bars"]:
        return []

    rim_px = win_h if cfg["use_high_for_rim"] else win_c

    for bi in range(search_lo, search_hi + 1):
        bottom = win_l[bi] if cfg["use_low_for_bottom"] else win_c[bi]
        if bottom != bottom or bottom <= 0:
            continue
        left_slice = rim_px[:bi]
        if len(left_slice) < 8:
            continue
        li = max(range(len(left_slice)), key=lambda i: left_slice[i])
        left = left_slice[li]
        if left <= 0 or bi - li < 8:
            continue
        depth = left - bottom
        depth_pct = depth / left
        if depth_pct < cfg["cup_depth_min"] or depth_pct > cfg["cup_depth_max"]:
            continue
        deep_cup = depth_pct > 0.33

        if cfg["prior_trend_required"] and not _check_prior_trend(
            win_c,
            li,
            left,
            lookback=cfg["prior_trend_lookback"],
            min_pct=cfg["prior_trend_min_pct"],
        ):
            continue

        right_region = win_c[bi + 1 :]
        if len(right_region) < cfg["min_handle_bars"] + 5:
            continue
        ri_local = None
        right_px = None
        rim_frozen = False
        for j, px in enumerate(win_c[bi + 1 :]):
            abs_j = bi + 1 + j
            rh = win_h[abs_j] if cfg["use_high_for_rim"] else px
            near_rim = (
                abs(rh - left) / left <= cfg["rim_rel_tol"]
                and rh >= left * (1.0 - cfg["rim_rel_tol"])
            )
            if near_rim and not rim_frozen:
                if right_px is None or rh >= right_px:
                    right_px = rh
                    ri_local = abs_j
            if ri_local is not None and right_px is not None and not rim_frozen:
                if (right_px - px) / depth >= cfg["handle_depth_min"]:
                    rim_frozen = True
            if ri_local is not None and abs_j - ri_local > cfg["max_handle_bars"] + 5:
                break
        if ri_local is None or right_px is None:
            continue
        if ri_local - li < cfg["min_cup_bars"]:
            continue
        if abs(right_px - left) / left > cfg["rim_rel_tol"]:
            continue

        if cfg["invalidate_on_lower_low"] and not _no_lower_low(
            win_l,
            bi + 1,
            ri_local,
            bottom,
            cfg["lower_low_tol_pct"],
        ):
            continue

        after = win_c[ri_local + 1 :]
        if len(after) < cfg["min_handle_bars"]:
            continue
        handle_len = min(len(after), cfg["max_handle_bars"])
        cut = handle_len
        for k in range(handle_len):
            if after[k] > right_px * (1.0 + 0.002):
                cut = k if k >= cfg["min_handle_bars"] else cfg["min_handle_bars"]
                break
        handle_len = min(max(cut, cfg["min_handle_bars"]), len(after), cfg["max_handle_bars"])
        handle_seg_l = win_l[ri_local + 1 : ri_local + 1 + handle_len]
        hli_rel = min(range(len(handle_seg_l)), key=lambda i: handle_seg_l[i])
        handle_low = handle_seg_l[hli_rel]
        handle_low_i = ri_local + 1 + hli_rel
        handle_end_i = ri_local + handle_len

        if cfg["invalidate_on_lower_low"] and not _no_lower_low(
            win_l,
            ri_local + 1,
            handle_end_i,
            bottom,
            cfg["lower_low_tol_pct"],
        ):
            continue

        handle_retrace = right_px - handle_low
        if handle_retrace <= 0:
            continue
        retrace_frac = handle_retrace / depth
        hmax = cfg["handle_depth_max"]
        if deep_cup:
            hmax = max(hmax, 0.55)
        if retrace_frac < cfg["handle_depth_min"] or retrace_frac > hmax:
            continue
        floor_frac = cfg["handle_floor_frac"]
        rim_max = cfg["handle_retrace_of_rim_max"]
        if deep_cup:
            floor_frac = min(floor_frac, 0.35)
            rim_max = max(rim_max, 0.26)
        floor = bottom + depth * floor_frac
        if handle_low < floor:
            continue

        rim = max(left, right_px)
        rim_retrace = (rim - handle_low) / rim if rim > 0 else 0.0
        if rim_retrace < cfg["handle_retrace_of_rim_min"] or rim_retrace > rim_max:
            continue

        cup_len = ri_local - li
        if handle_len >= cup_len or handle_len < cfg["min_handle_bars"]:
            continue

        if cfg["reject_upward_handle"] and not deep_cup:
            xs = list(range(handle_len))
            ys = win_c[ri_local + 1 : ri_local + 1 + handle_len]
            if _lin_slope(xs, ys) > 0.002:
                continue

        u_ok, extended = _check_u_shape(
            win_c,
            win_l,
            li,
            bi,
            ri_local,
            depth,
            flat_bars=cfg["cup_bottom_flat_bars"],
            flat_pct=cfg["cup_bottom_flat_pct"],
            symmetry_max=cfg["cup_symmetry_max_ratio"],
        )
        extended = extended or deep_cup or (ri_local - li) >= cfg["extended_cup_bars"]
        if cfg["cup_u_shape_required"] and not u_ok and not extended:
            continue

        rim_align = 1.0 - abs(right_px - left) / left
        shallow = 1.0 - retrace_frac
        depth_score = 1.0 - abs(depth_pct - 0.25) / 0.25
        score = rim_align * 0.4 + shallow * 0.35 + max(0.0, depth_score) * 0.25

        cands.append(
            {
                "li": offset + li,
                "bi": offset + bi,
                "ri": offset + ri_local,
                "hli": offset + handle_low_i,
                "hei": offset + handle_end_i,
                "left": left,
                "bottom": bottom,
                "right": right_px,
                "handle_low": handle_low,
                "rim": rim,
                "score": score,
                "extended": extended,
                "deep_cup": deep_cup,
                "u_ok": u_ok,
            }
        )
    return cands


def _find_first_confirm(
    closes: Sequence[float],
    seq: Sequence[Dict[str, Any]],
    hei: int,
    rim: float,
    cfg: Dict[str, Any],
) -> Tuple[Optional[int], Optional[str]]:
    """柄部结束后首次收盘突破杯口（与当前 status 无关，用于历史确认日）。"""
    if rim <= 0 or hei >= len(closes) - 1:
        return None, None
    start = hei + 1
    if cfg["confirm_close_above"]:
        threshold = rim * (1.0 + cfg["confirm_buffer_pct"])
        for k in range(start, len(closes)):
            c = closes[k]
            if c == c and breakout_up(c, threshold):
                return k, _bar_date(seq[k])
        return None, None
    for k in range(start, len(closes)):
        c = closes[k]
        if c == c and c > rim:
            return k, _bar_date(seq[k])
    return None, None


def _pick_candidate(
    cands: List[Dict[str, Any]],
    lows: Sequence[float],
    cfg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not cands:
        return None
    # 重锚：优先柄部结束日最晚且柄后未破杯底的候选
    tol = cfg["lower_low_tol_pct"]
    valid: List[Dict[str, Any]] = []
    for c in cands:
        bottom = c["bottom"]
        hei = c["hei"]
        if cfg["invalidate_on_lower_low"] and not _no_lower_low(
            lows, hei + 1, len(lows) - 1, bottom, tol
        ):
            continue
        valid.append(c)
    pool = valid or cands
    pool.sort(key=lambda x: (x["hei"], x["score"]), reverse=True)
    return pool[0]


def detect_cup_bottom(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """从升序日线 bars 识别最近杯底形态。返回命中 dict 或 None。"""
    cfg = _parse_cfg(pattern_cfg)

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) > cfg["lookback_days"]:
        seq = list(seq[-cfg["lookback_days"] :])
    if len(seq) < cfg["min_bars"]:
        return None

    closes = _series(seq, "close")
    highs = _series(seq, "high")
    lows = _series(seq, "low")
    volumes = _volume_series(seq)
    if any(c != c for c in closes):
        aligned: List[Dict[str, Any]] = []
        closes, highs, lows, volumes = [], [], [], []
        for b in seq:
            c, h, l = _f(b.get("close")), _f(b.get("high")), _f(b.get("low"))
            if c is None or c <= 0:
                continue
            aligned.append(b)
            closes.append(c)
            highs.append(h if h and h > 0 else c)
            lows.append(l if l and l > 0 else c)
            volumes.append(next((v for v in (_f(b.get(k)) for k in ("volume", "vol")) if v), float("nan")))
        seq = aligned
    if len(closes) < cfg["min_bars"]:
        return None

    vol_ma = _rolling_mean(volumes, cfg["volume_ma_window"])
    cands = _find_candidates(seq, closes, highs, lows, volumes, vol_ma, cfg)
    found = _pick_candidate(cands, lows, cfg)
    if not found:
        return None

    li = found["li"]
    bi = found["bi"]
    ri = found["ri"]
    hli = found["hli"]
    hei = found["hei"]
    left = found["left"]
    bottom = found["bottom"]
    right = found["right"]
    handle_low = found["handle_low"]
    rim = found["rim"]
    last_c = closes[-1]
    depth = rim - bottom
    handle_retrace = rim - handle_low

    first_confirm_i, first_confirm_date = _find_first_confirm(closes, seq, hei, rim, cfg)
    ever_confirmed = first_confirm_date is not None

    confirm_i: Optional[int] = None
    confirm_date: Optional[str] = None
    superseded = cfg["invalidate_on_lower_low"] and not _no_lower_low(
        lows, hei + 1, len(lows) - 1, bottom, cfg["lower_low_tol_pct"]
    )

    if breakout_down(last_c, handle_low):
        status = "invalidated"
    elif superseded:
        status = "invalidated"
    elif cfg["confirm_close_above"] and breakout_up(last_c, rim * (1.0 + cfg["confirm_buffer_pct"])):
        status = "confirmed"
        confirm_i = first_confirm_i
        confirm_date = first_confirm_date
        if not confirm_date:
            confirm_i = len(closes) - 1
            confirm_date = _bar_date(seq[-1])
    elif not cfg["confirm_close_above"] and last_c > rim:
        status = "confirmed"
        confirm_i = first_confirm_i if first_confirm_i is not None else len(closes) - 1
        confirm_date = first_confirm_date or _bar_date(seq[-1])
    else:
        status = "forming"

    vol_flags = _volume_flags(volumes, vol_ma, li, bi, ri, hli, hei, confirm_i, cfg)
    vol_pass = sum(1 for v in vol_flags.values() if v)
    if status == "confirmed" and cfg["volume_require_confirm"] and not vol_flags["breakout_expand"]:
        status = "forming"
        confirm_date = None
        confirm_i = None
    if cfg["volume_require_all"] and vol_pass < 4:
        return None

    grade = _grade_from_flags(
        structure_ok=True,
        vol_flags=vol_flags,
        extended=bool(found.get("extended")),
        invalidated=status == "invalidated",
        cfg=cfg,
    )
    gf = cfg["grade_filter"]
    if gf not in ("all", "", "both") and grade != gf:
        return None
    if cfg["exclude_invalidated"] and status == "invalidated":
        return None

    return {
        "ok": True,
        "status": status,
        "grade": grade,
        "left_rim_date": _bar_date(seq[li]),
        "cup_bottom_date": _bar_date(seq[bi]),
        "right_rim_date": _bar_date(seq[ri]),
        "handle_low_date": _bar_date(seq[hli]),
        "handle_end_date": _bar_date(seq[min(hei, len(seq) - 1)]),
        "left_rim_price": round(left, 4),
        "cup_bottom_price": round(bottom, 4),
        "right_rim_price": round(right, 4),
        "handle_low_price": round(handle_low, 4),
        "rim": round(rim, 4),
        "last_close": round(last_c, 4),
        "confirm_date": confirm_date,
        "first_confirm_date": first_confirm_date,
        "ever_confirmed": ever_confirmed,
        "cup_depth_pct": round(depth / rim * 100, 2) if rim > 0 else None,
        "handle_retrace_pct": round(handle_retrace / depth * 100, 2) if depth > 0 else None,
        "handle_retrace_of_rim_pct": round(handle_retrace / rim * 100, 2) if rim > 0 else None,
        "volume_score": vol_pass,
        "volume_flags": vol_flags,
        "quality_flags": {
            "u_shape": bool(found.get("u_ok")),
            "extended_base": bool(found.get("extended")),
            "prior_trend_ok": True,
        },
        "lookback_used": len(seq),
        "score": round(float(found.get("score") or 0), 4),
    }
