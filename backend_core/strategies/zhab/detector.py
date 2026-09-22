# -*- coding: utf-8 -*-
"""ZHAB 日线结构判定：涨停锚点 → 高位蓄势 → 再突破 / 失效。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.board_roles.classify import is_limit_up


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


def _true_range(h: float, lo: float, prev_close: Optional[float]) -> float:
    if prev_close is None or prev_close <= 0:
        return max(0.0, h - lo)
    return max(h - lo, abs(h - prev_close), abs(lo - prev_close))


def atr_series(bars: Sequence[Dict[str, Any]], period: int) -> List[Optional[float]]:
    """与 bars 等长的 ATR；不足 period 处为 None。bars 升序。"""
    n = len(bars)
    out: List[Optional[float]] = [None] * n
    if n == 0 or period <= 0:
        return out
    trs: List[float] = []
    prev_c: Optional[float] = None
    for i, b in enumerate(bars):
        h = _f(b.get("high"))
        lo = _f(b.get("low"))
        c = _f(b.get("close"))
        if h is None or lo is None:
            trs.append(0.0)
            prev_c = c if c is not None else prev_c
            continue
        if h < lo:
            h, lo = lo, h
        trs.append(_true_range(h, lo, prev_c))
        prev_c = c if c is not None else prev_c
        if i + 1 >= period:
            chunk = trs[i + 1 - period : i + 1]
            out[i] = sum(chunk) / float(period)
    return out


def long_upper_shadow(
    bar: Dict[str, Any],
    *,
    shadow_ratio: float = 0.5,
    vs_body: float = 2.0,
) -> bool:
    o, h, lo, c = (_f(bar.get(k)) for k in ("open", "high", "low", "close"))
    if None in (o, h, lo, c) or c <= 0:
        return False
    if h < lo:
        h, lo = lo, h
    rng = h - lo
    if rng <= 0:
        return False
    upper = h - max(o, c)
    body = abs(c - o)
    return upper / rng >= shadow_ratio and upper >= body * vs_body and upper / c >= 0.02


def env_allows_executable(
    *,
    season: Any,
    gates_passed: Any,
    gates_total: Any,
    cold_seasons: Sequence[str],
    gates_pass_ratio_min: float,
) -> Tuple[bool, str]:
    season_s = str(season or "").strip()
    if season_s in {str(x) for x in cold_seasons}:
        return False, f"情绪周期「{season_s}」偏退潮，突破仅观察"
    try:
        passed = int(gates_passed or 0)
        total = int(gates_total or 0)
    except (TypeError, ValueError):
        passed, total = 0, 0
    if total > 0 and passed / float(total) < float(gates_pass_ratio_min):
        return False, f"硬门槛 {passed}/{total} 未过半，突破仅观察"
    return True, ""


def _score_structure(
    *,
    dims_ok: Dict[str, bool],
    consol_days: int,
    best_lo: int,
    best_hi: int,
    vol_ratio: Optional[float],
    atr_ratio: Optional[float],
    space_ok: bool,
    breakout: bool,
    breakout_vol_ratio: Optional[float],
) -> float:
    base = sum(15.0 for k, ok in dims_ok.items() if k != "space" and ok)
    if dims_ok.get("space"):
        base += 10.0
    elif space_ok is False:
        base += 3.0
    if best_lo <= consol_days <= best_hi:
        base += 8.0
    if vol_ratio is not None and vol_ratio <= 0.70:
        base += min(10.0, (0.70 - vol_ratio) * 20.0)
    if atr_ratio is not None and atr_ratio <= 1.0:
        base += min(8.0, (1.0 - atr_ratio) * 16.0)
    if breakout and breakout_vol_ratio is not None:
        base += min(15.0, max(0.0, (breakout_vol_ratio - 1.5) * 10.0 + 8.0))
    return round(min(100.0, max(0.0, base)), 2)


def evaluate_zhab_bars(
    bars: Sequence[Dict[str, Any]],
    *,
    code: str,
    asof_date: str,
    zt_dates: Optional[Sequence[str]] = None,
    in_mainline: bool = True,
    require_mainline: bool = True,
    season: Any = None,
    gates_passed: Any = None,
    gates_total: Any = None,
    structure_cfg: Optional[Dict[str, Any]] = None,
    env_cfg: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    bars 升序（旧→新），末根日期应为 asof_date（或包含 asof）。
    返回 setup / breakout / invalid 命中 dict；不满足候选条件返回 None。
    """
    scfg = dict(structure_cfg or {})
    ecfg = dict(env_cfg or {})
    consol_min = int(scfg.get("consol_days_min", 1))
    consol_max = int(scfg.get("consol_days_max", 6))
    best_lo = int(scfg.get("consol_days_best_lo", 2))
    best_hi = int(scfg.get("consol_days_best_hi", 4))
    vol_zt_max = float(scfg.get("consol_vol_vs_zt_max", 0.70))
    bo_vol_min = float(scfg.get("breakout_vol_vs_consol_min", 1.5))
    atr_period = int(scfg.get("atr_period", 3))
    atr_conv_max = float(scfg.get("atr_converge_max_ratio", 1.0))
    space_lb = int(scfg.get("space_lookback_days", 120))
    space_pct = float(scfg.get("space_vacuum_pct", 0.20))
    shadow_ratio = float(scfg.get("false_break_upper_shadow_ratio", 0.50))
    shadow_vs_body = float(scfg.get("false_break_upper_vs_body", 2.0))
    cold = list(ecfg.get("cold_seasons") or ["秋", "冬"])
    gates_ratio = float(ecfg.get("gates_pass_ratio_min", 0.5))
    req_ml = bool(ecfg.get("require_mainline", require_mainline))

    asof = str(asof_date or "")[:10]
    if not bars or not asof:
        return None

    # 定位 asof 下标
    idx_asof = None
    for i, b in enumerate(bars):
        if _bar_date(b) == asof:
            idx_asof = i
    if idx_asof is None:
        return None
    if idx_asof < consol_min + 1:
        return None

    zt_set = {str(d)[:10] for d in (zt_dates or []) if d}
    # 在 [idx_asof - consol_max, idx_asof - consol_min] 内找最近涨停日
    lo_i = max(0, idx_asof - consol_max)
    hi_i = idx_asof - consol_min
    zt_idx: Optional[int] = None
    for i in range(hi_i, lo_i - 1, -1):
        b = bars[i]
        d = _bar_date(b)
        chg = _f(b.get("change_percent"))
        hit = d in zt_set
        if not hit and chg is not None:
            hit = is_limit_up(code, chg)
        if hit:
            zt_idx = i
            break
    if zt_idx is None:
        return None

    consol_days = idx_asof - zt_idx
    if consol_days < consol_min or consol_days > consol_max:
        return None

    zt_bar = bars[zt_idx]
    zt_high = _f(zt_bar.get("high"))
    zt_low = _f(zt_bar.get("low"))
    zt_close = _f(zt_bar.get("close"))
    zt_vol = _f(zt_bar.get("volume"))
    if None in (zt_high, zt_low, zt_close) or zt_close <= 0:
        return None
    if zt_high < zt_low:
        zt_high, zt_low = zt_low, zt_high
    zt_mid = (zt_high + zt_low) / 2.0
    zt_vol = zt_vol if zt_vol and zt_vol > 0 else None

    consol_bars = list(bars[zt_idx + 1 : idx_asof + 1])
    consol_before_today = list(bars[zt_idx + 1 : idx_asof])
    today = bars[idx_asof]
    today_close = _f(today.get("close"))
    today_high = _f(today.get("high"))
    today_low = _f(today.get("low"))
    today_vol = _f(today.get("volume"))
    if today_close is None or today_close <= 0:
        return None

    # ---- 维度 1：强势区域（收盘在涨停日中点上方）----
    dim_zone = today_close >= zt_mid * 0.999

    # ---- 维度 3/4：箱体与低点抬高（基于涨停后至昨日）----
    # 整理箱体：优先用涨停后至昨日；仅 1 日整理时用涨停日实体上沿/下沿作箱体
    box_bars = list(consol_before_today)
    lows: List[float] = []
    highs: List[float] = []
    vols: List[float] = []
    for b in box_bars:
        lo = _f(b.get("low"))
        hi = _f(b.get("high"))
        v = _f(b.get("volume"))
        if lo is not None:
            lows.append(lo)
        if hi is not None:
            highs.append(hi)
        if v is not None and v > 0:
            vols.append(v)
    if lows and highs:
        box_low = min(lows)
        box_high = max(highs)
    else:
        box_low = float(zt_low)
        box_high = float(zt_high)
    # 支撑不低于涨停日最低的深破（允许轻微）
    support = max(float(box_low), float(zt_low) * 0.995)
    higher_lows = True
    if len(lows) >= 2:
        # 允许最后低点不低于前期最低的 98%
        higher_lows = lows[-1] >= min(lows[:-1]) * 0.98
    dim_support = higher_lows and today_low is not None and today_low >= support * 0.985

    # ---- 维度 2：量价收敛（整理段，不含突破日放量）----
    shrink_vols = vols
    if not consol_before_today and today_vol and zt_vol:
        # 仅 1 日整理：用今日量相对涨停日
        shrink_vols = [today_vol]
    max_consol_vol = max(shrink_vols) if shrink_vols else None
    avg_consol_vol = (sum(shrink_vols) / len(shrink_vols)) if shrink_vols else None
    vol_ratio = None
    if zt_vol and max_consol_vol is not None:
        vol_ratio = max_consol_vol / zt_vol
    dim_volume = vol_ratio is not None and vol_ratio <= vol_zt_max

    atrs = atr_series(bars[: idx_asof + 1], atr_period)
    # 整理段 ATR（不含当日突破日）：窗口过短时跳过收敛硬门槛，仅看量能
    atr_window = [atrs[i] for i in range(zt_idx + 1, idx_asof) if atrs[i] is not None]
    atr_ratio = None
    dim_atr = True
    if len(atr_window) >= 3:
        mid = max(1, len(atr_window) // 2)
        first = atr_window[:mid]
        second = atr_window[mid:]
        m1 = sum(first) / len(first)
        m2 = sum(second) / len(second)
        if m1 > 0:
            atr_ratio = m2 / m1
            dim_atr = atr_ratio <= atr_conv_max
    dim_volume_atr = dim_volume and dim_atr

    # 蓄势日也要求当日量不超过涨停日 70%（突破日放量另判）
    if today_vol and zt_vol and today_vol / zt_vol > vol_zt_max:
        # 若当日已放量且收盘未破上沿，视为滞涨而非蓄势
        if not (today_close > float(box_high) * 1.001):
            dim_volume_atr = False
            vol_ratio = max(vol_ratio or 0.0, today_vol / zt_vol)

    # ---- 维度 5：板块共振 ----
    dim_sector = bool(in_mainline) if req_ml else True

    # ---- 维度 6：空间真空（软）----
    look_start = max(0, zt_idx - space_lb)
    prior_highs = []
    for b in bars[look_start:zt_idx]:
        hi = _f(b.get("high"))
        if hi is not None:
            prior_highs.append(hi)
    prior_max = max(prior_highs) if prior_highs else None
    space_room = None
    if prior_max is not None and today_close > 0:
        space_room = (prior_max - today_close) / today_close
    # 创阶段新高（上方无压制）视为空间合格
    dim_space = prior_max is None or prior_max <= today_close * 1.001 or (
        space_room is not None and space_room >= space_pct
    )

    dims_ok = {
        "zone": dim_zone,
        "volume_atr": dim_volume_atr,
        "consol_days": consol_min <= consol_days <= consol_max,
        "support": dim_support,
        "sector": dim_sector,
        "space": dim_space,
    }

    # ---- 失效 ----
    broken = today_close < support or today_close < float(zt_low) * 0.995
    stagnant = consol_days >= consol_max and today_close < zt_mid and not (
        today_high is not None and today_high > box_high and today_close > box_high
    )
    if broken or (stagnant and not dim_zone):
        return {
            "code": code,
            "name": name,
            "date": asof,
            "signal_type": "invalid",
            "setup_ok": False,
            "entry_signal": False,
            "score": 0.0,
            "zt_date": _bar_date(zt_bar),
            "consol_days": consol_days,
            "zt_mid": round(zt_mid, 4),
            "box_low": round(float(support), 4),
            "box_high": round(float(box_high), 4),
            "close": today_close,
            "detail": {
                "reason": "broken_support" if broken else "stagnant_timeout",
                "dims": dims_ok,
                "vol_ratio": vol_ratio,
                "atr_ratio": atr_ratio,
                "space_room": space_room,
            },
        }

    hard_dims = ("zone", "volume_atr", "consol_days", "support", "sector")
    structure_ok = all(dims_ok[k] for k in hard_dims)
    if not structure_ok:
        return None

    # ---- 突破判定（相对整理上沿）----
    cleared = today_close > float(box_high) * 1.001
    bo_vol_ratio = None
    ref_vol = avg_consol_vol
    if ref_vol is None and zt_vol:
        ref_vol = zt_vol * 0.5
    if ref_vol and today_vol and ref_vol > 0:
        bo_vol_ratio = today_vol / ref_vol
    vol_ok = bo_vol_ratio is not None and bo_vol_ratio >= bo_vol_min
    # 刺穿收回：盘中破上沿但收盘回到箱内 → 非突破
    pierce_fail = (
        today_high is not None
        and today_high > float(box_high)
        and today_close <= float(box_high)
    )
    # 收盘站上但长上影 → 假突破嫌疑，不进可执行
    long_shadow_break = cleared and long_upper_shadow(
        today, shadow_ratio=shadow_ratio, vs_body=shadow_vs_body
    )
    is_breakout = cleared and vol_ok and not pierce_fail and not long_shadow_break
    false_bo = pierce_fail or long_shadow_break

    env_ok, env_note = env_allows_executable(
        season=season,
        gates_passed=gates_passed,
        gates_total=gates_total,
        cold_seasons=cold,
        gates_pass_ratio_min=gates_ratio,
    )

    score = _score_structure(
        dims_ok=dims_ok,
        consol_days=consol_days,
        best_lo=best_lo,
        best_hi=best_hi,
        vol_ratio=vol_ratio,
        atr_ratio=atr_ratio,
        space_ok=dim_space,
        breakout=is_breakout,
        breakout_vol_ratio=bo_vol_ratio,
    )

    if is_breakout:
        signal_type = "breakout"
        entry = bool(env_ok)
        if not env_ok:
            score = min(score, 72.0)
    else:
        signal_type = "setup"
        entry = False

    return {
        "code": code,
        "name": name,
        "date": asof,
        "signal_type": signal_type,
        "setup_ok": True,
        "entry_signal": entry,
        "score": score,
        "zt_date": _bar_date(zt_bar),
        "consol_days": consol_days,
        "zt_mid": round(zt_mid, 4),
        "box_low": round(float(support), 4),
        "box_high": round(float(box_high), 4),
        "close": today_close,
        "close_price": today_close,
        "open": _f(today.get("open")),
        "high": today_high,
        "low": today_low,
        "volume": today_vol,
        "detail": {
            "dims": dims_ok,
            "vol_ratio": None if vol_ratio is None else round(vol_ratio, 4),
            "atr_ratio": None if atr_ratio is None else round(atr_ratio, 4),
            "breakout_vol_ratio": None if bo_vol_ratio is None else round(bo_vol_ratio, 4),
            "space_room": None if space_room is None else round(space_room, 4),
            "env_ok": env_ok,
            "env_note": env_note,
            "false_breakout": false_bo or pierce_fail,
            "in_mainline": bool(in_mainline),
            "zt_high": zt_high,
            "zt_low": zt_low,
            "zt_volume": zt_vol,
        },
    }
