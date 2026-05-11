"""
3倍量缩量突破 — 核心判定（historical_data：最新在前，下标 0 为最近一日）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .config import VolumeShrinkBreakoutConfigManager

logger = logging.getLogger(__name__)


def _sma_at_index(closes: List[float], k: int, period: int) -> Optional[float]:
    """在 bar k 处的简单移动平均：使用 closes[k]..closes[k+period-1]（均为不晚于 k 的 bar）。"""
    if k + period > len(closes):
        return None
    chunk = closes[k : k + period]
    if any(x <= 0 for x in chunk):
        return None
    return sum(chunk) / period


def find_boom_index(
    volumes: List[float],
    *,
    volume_ratio: float,
    k_min: int,
    k_max: int,
) -> Optional[int]:
    """
    在 [k_min, k_max] 内寻找满足 volume[k] >= volume_ratio * volume[k+1] 的下标 k；
    k+1 为时间上更早一日（数据倒序）。多解时取最小 k（离今天最近的一次爆量）。
    """
    n = len(volumes)
    if n < k_max + 2:
        return None
    hi = min(k_max, n - 2)
    lo = max(1, k_min)
    if lo > hi:
        return None
    candidates: List[int] = []
    for k in range(lo, hi + 1):
        v = volumes[k]
        v_prev = volumes[k + 1]
        if v_prev <= 0:
            continue
        if v >= volume_ratio * v_prev:
            candidates.append(k)
    return min(candidates) if candidates else None


def pass_ma_bull_at_k(closes: List[float], k: int) -> bool:
    """爆量日 k：MA5 > MA10 > MA20（均用 k 及更早收盘价）。"""
    ma5 = _sma_at_index(closes, k, 5)
    ma10 = _sma_at_index(closes, k, 10)
    ma20 = _sma_at_index(closes, k, 20)
    if ma5 is None or ma10 is None or ma20 is None:
        return False
    return ma5 > ma10 > ma20


def pass_shrink_breakout(closes: List[float], volumes: List[float], k: int) -> bool:
    """最新日突破爆量日收盘，且最新日量小于爆量日量。"""
    if k >= len(closes) or k >= len(volumes):
        return False
    if closes[0] <= 0 or closes[k] <= 0:
        return False
    if volumes[k] <= 0:
        return False
    return closes[0] > closes[k] and volumes[0] < volumes[k]


def had_ma5_cross_above_ma10_in_window(closes: List[float], k: int, max_span: int = 18) -> bool:
    """
    在爆量日 k 及更早的若干根内，是否出现过 MA5 由下向上穿越 MA10（经典金叉）。
    数据倒序：t 增大为更早日；t+1 比 t 早一日。
    """
    upper = min(k + max_span, len(closes) - 1)
    for t in range(k, upper):
        a0 = _sma_at_index(closes, t, 5)
        b0 = _sma_at_index(closes, t, 10)
        a1 = _sma_at_index(closes, t + 1, 5)
        b1 = _sma_at_index(closes, t + 1, 10)
        if a0 is None or b0 is None or a1 is None or b1 is None:
            continue
        if a1 <= b1 and a0 > b0:
            return True
    return False


def had_pullback_below_boom_close(
    historical_data: List[Dict[str, Any]],
    closes: List[float],
    k: int,
    boom_close: float,
    *,
    dip_ratio: float = 0.985,
) -> bool:
    """
    最新日与爆量日之间（不含两端收盘比较日），最低价是否曾明显低于爆量日收盘，
    用于刻画「先高量、再回调、再缩量突破」节奏。
    """
    if k < 2 or boom_close <= 0:
        return False
    thr = boom_close * float(dip_ratio)
    for i in range(1, k):
        bar = historical_data[i]
        low = float(bar.get("low") or bar.get("close") or closes[i] or 0)
        if low > 0 and low < thr:
            return True
    return False


def build_buy_signal_bundle(
    *,
    volume_ratio_th: float,
    ratio_actual: Optional[float],
    ma5: Optional[float],
    ma10: Optional[float],
    ma20: Optional[float],
    boom_close: float,
    breakout_close: float,
    boom_vol: float,
    breakout_vol: float,
    k: int,
    chg: float,
    had_cross: bool,
    pullback: bool,
) -> Dict[str, Any]:
    """参考买点文案、0–100 强度、分级与提醒（非投资建议）。"""
    reminders: List[str] = []
    strength = 34.0

    if ratio_actual is not None and ratio_actual >= volume_ratio_th:
        strength += min(26.0, (ratio_actual - volume_ratio_th) * 8.0)

    if boom_close > 0:
        margin_pct = (breakout_close - boom_close) / boom_close * 100.0
        strength += min(22.0, max(0.0, margin_pct * 3.0))

    if boom_vol > 0 and breakout_vol >= 0:
        shrink = 1.0 - breakout_vol / boom_vol
        strength += min(20.0, max(0.0, shrink * 38.0))
        vr = breakout_vol / boom_vol
        if vr > 0.88:
            reminders.append("缩量不够充分，追价宜控制仓位")
        elif vr <= 0.42:
            reminders.append("缩量较为充分，量价配合相对理想")

    if ma5 is not None and ma10 is not None and ma20 is not None and ma10 > 0 and ma20 > 0:
        spread = (ma5 - ma10) / ma10 + (ma10 - ma20) / ma20
        strength += min(12.0, max(0.0, spread * 55.0))

    if had_cross:
        strength += 8.0
    else:
        reminders.append("未见典型 MA5 上穿 MA10 金叉，当前为均线多头排列；强度已相应扣分")

    if pullback:
        strength += 5.0
        reminders.append("爆量后曾有回踩/震荡，偏低量再突破，贴近「回调后突破」节奏")

    if chg >= 7.0:
        reminders.append("当日涨幅偏大，谨防短线过热与隔日抛压")
    elif chg <= -3.0:
        reminders.append("当日仍收跌，突破有效性需结合次日确认")

    if k >= 40:
        reminders.append("爆量日离当前较远，注意信号时效")

    strength_i = int(max(0, min(100, round(strength))))
    if strength_i >= 72:
        level = "强"
    elif strength_i >= 55:
        level = "中"
    else:
        level = "弱"

    if strength_i < 52 and len(reminders) < 6:
        reminders.append("综合强度偏弱，宜小仓或等待次日确认")

    if pullback:
        buy = "回踩后缩量突破高倍量日收盘 — 参考买点（模拟验证后再下单）"
    else:
        buy = "高倍量+短中期均线多头后，缩量突破爆量日收盘 — 参考买点（模拟验证后再下单）"

    return {
        "buy_signal": buy,
        "signal_strength": strength_i,
        "signal_strength_level": level,
        "signal_reminders": reminders[:6],
        "had_ma5_cross_above_ma10": had_cross,
        "had_pullback_below_boom_zone": pullback,
    }


def pass_phase1_ma5_cross_ma20_up(
    closes: List[float],
    s: int,
    *,
    trend_lb: int,
) -> bool:
    """阶段1：倍量外条件 — MA5 于 s 日上穿 MA20，且短中期均线向上（可配置回看）。"""
    if s + 1 >= len(closes):
        return False
    ma5_s = _sma_at_index(closes, s, 5)
    ma20_s = _sma_at_index(closes, s, 20)
    ma5_p = _sma_at_index(closes, s + 1, 5)
    ma20_p = _sma_at_index(closes, s + 1, 20)
    if ma5_s is None or ma20_s is None or ma5_p is None or ma20_p is None:
        return False
    if not (ma5_p <= ma20_p and ma5_s > ma20_s):
        return False
    if s + trend_lb + 20 > len(closes):
        return False
    ma20_far = _sma_at_index(closes, s + trend_lb, 20)
    if ma20_far is None or not (ma20_s > ma20_far):
        return False
    if s + 3 + 5 > len(closes):
        return False
    ma5_far = _sma_at_index(closes, s + 3, 5)
    if ma5_far is None or not (ma5_s > ma5_far):
        return False
    return True


def pass_phase1_volume_spike(volumes: List[float], s: int, *, volume_ratio: float) -> bool:
    if s + 1 >= len(volumes):
        return False
    v = volumes[s]
    v_prev = volumes[s + 1]
    if v_prev <= 0:
        return False
    return v >= volume_ratio * v_prev


def pass_phase2_ma_at_t(closes: List[float], t: int, *, flat_tol: float) -> bool:
    """阶段2均线：MA5>MA10>MA20，或 MA5 相对 t+3 走平且 MA5>=MA20。"""
    ma5 = _sma_at_index(closes, t, 5)
    ma10 = _sma_at_index(closes, t, 10)
    ma20 = _sma_at_index(closes, t, 20)
    if ma5 is None or ma20 is None:
        return False
    if ma10 is not None and ma5 > ma10 > ma20:
        return True
    ma5_old = _sma_at_index(closes, t + 3, 5)
    if ma5_old is None or ma5_old <= 0:
        return False
    if abs(ma5 - ma5_old) / ma5_old < flat_tol and ma5 >= ma20:
        return True
    return False


def validate_phase2_retracement(
    historical_data: List[Dict[str, Any]],
    closes: List[float],
    volumes: List[float],
    s: int,
    o_lim: float,
    l_lim: float,
    v_limit: float,
    *,
    eps: float,
    vol_half: float,
    flat_tol: float,
) -> bool:
    """阶段2：t∈[1,s-1]；s=1 时区间为空，视为通过。"""
    if v_limit <= 0:
        return False
    floor_px = min(o_lim, l_lim) * (1.0 - eps)
    thr_vol = v_limit * vol_half
    for t in range(1, s):
        bar = historical_data[t]
        c = float(bar.get("close") or closes[t] or 0)
        if c < floor_px:
            return False
        if volumes[t] >= thr_vol:
            return False
        if not pass_phase2_ma_at_t(closes, t, flat_tol=flat_tol):
            return False
    return True


def validate_phase3_entry(
    closes: List[float],
    volumes: List[float],
    c_limit: float,
    v_limit: float,
) -> bool:
    if c_limit <= 0 or v_limit <= 0:
        return False
    return closes[0] > c_limit and volumes[0] < v_limit


def _bar_ohlc(bar: Dict[str, Any], close_fallback: float) -> Tuple[float, float, float, float]:
    c = float(bar.get("close") or close_fallback or 0)
    h = float(bar.get("high") or c)
    o = float(bar.get("open") or c)
    l = float(bar.get("low") or c)
    return h, c, o, l


def build_buy_signal_bundle_three_phase(
    *,
    volume_ratio_th: float,
    ratio_actual: Optional[float],
    ma5: Optional[float],
    ma10: Optional[float],
    ma20: Optional[float],
    c_limit: float,
    breakout_close: float,
    v_limit: float,
    breakout_vol: float,
    s: int,
    chg: float,
    had_ma5_cross_ma10_window: bool,
    pullback_phase2: bool,
    max_retrace_vs_climit_pct: float,
    min_vol_headroom_half: float,
    breakout_vs_climit_pct: float,
) -> Dict[str, Any]:
    """三阶段路径下的强度与提醒（非投资建议）。"""
    reminders: List[str] = []
    strength = 36.0

    if ratio_actual is not None and ratio_actual >= volume_ratio_th:
        strength += min(24.0, (ratio_actual - volume_ratio_th) * 7.0)

    if c_limit > 0:
        strength += min(22.0, max(0.0, breakout_vs_climit_pct * 2.8))

    if v_limit > 0 and breakout_vol >= 0:
        shrink = 1.0 - breakout_vol / v_limit
        strength += min(22.0, max(0.0, shrink * 36.0))
        vr = breakout_vol / v_limit
        if vr > 0.88:
            reminders.append("触发日缩量不够充分，追价宜控制仓位")
        elif vr <= 0.42:
            reminders.append("触发日缩量较为充分，量价配合相对理想")

    if min_vol_headroom_half > 0:
        strength += min(10.0, max(0.0, min_vol_headroom_half * 120.0))

    if max_retrace_vs_climit_pct > 0.15:
        strength += min(8.0, max_retrace_vs_climit_pct * 18.0)
        reminders.append("回调段曾接近侦测日收盘但未有效跌破关键位，节奏偏「先回踩再突破」")

    if ma5 is not None and ma10 is not None and ma20 is not None and ma10 > 0 and ma20 > 0:
        spread = (ma5 - ma10) / ma10 + (ma10 - ma20) / ma20
        strength += min(10.0, max(0.0, spread * 48.0))

    if had_ma5_cross_ma10_window:
        strength += 6.0
    else:
        reminders.append("侦测窗口内未见典型 MA5 上穿 MA10，强度已略作调整")

    if pullback_phase2:
        strength += 5.0

    if chg >= 7.0:
        reminders.append("当日涨幅偏大，谨防短线过热与隔日抛压")
    elif chg <= -3.0:
        reminders.append("当日仍收跌，突破有效性需结合次日确认")

    if s >= 40:
        reminders.append("侦测日离当前较远，注意信号时效")

    strength_i = int(max(0, min(100, round(strength))))
    if strength_i >= 72:
        level = "强"
    elif strength_i >= 55:
        level = "中"
    else:
        level = "弱"

    if strength_i < 52 and len(reminders) < 6:
        reminders.append("综合强度偏弱，宜小仓或等待次日确认")

    buy = (
        "三阶段：侦测日放量+MA5上穿MA20 → 回调段守关键位且缩量 → 触发日突破侦测日收盘且缩量 "
        "— 参考买点（模拟验证后再下单）"
    )

    return {
        "buy_signal": buy,
        "signal_strength": strength_i,
        "signal_strength_level": level,
        "signal_reminders": reminders[:6],
        "had_ma5_cross_above_ma10": had_ma5_cross_ma10_window,
        "had_pullback_below_boom_zone": pullback_phase2,
    }


def _phase2_diagnostics(
    closes: List[float],
    volumes: List[float],
    s: int,
    c_limit: float,
    v_limit: float,
    *,
    vol_half: float,
) -> Tuple[float, float, bool, float]:
    """max_retrace_vs_climit_pct, min_vol_headroom(相对0.5阈值的余量比例), pullback_flag, breakout_vs_climit_pct."""
    thr_vol = v_limit * vol_half
    max_re = 0.0
    min_hr = 1.0
    touched = False
    if s > 1 and c_limit > 0 and v_limit > 0:
        for t in range(1, s):
            ct = closes[t]
            max_re = max(max_re, max(0.0, (c_limit - ct) / c_limit * 100.0))
            hr = (thr_vol - volumes[t]) / v_limit if v_limit > 0 else 0.0
            min_hr = min(min_hr, hr)
            if ct < c_limit * 1.002:
                touched = True
    breakout_vs_cl = ((closes[0] - c_limit) / c_limit * 100.0) if c_limit > 0 else 0.0
    pullback = bool(s > 1 and (touched or max_re > 0.08))
    return max_re, min_hr, pullback, breakout_vs_cl


def _evaluate_stock_legacy(
    historical_data: List[Dict[str, Any]],
    *,
    volume_ratio: float,
    boom_lookback_min: int,
    boom_lookback_max: int,
) -> Optional[Dict[str, Any]]:
    if not historical_data:
        return None
    closes = [float(b.get("close") or 0) for b in historical_data]
    volumes = [float(b.get("volume") or 0) for b in historical_data]
    n = len(closes)
    if n < boom_lookback_max + 20:
        return None

    k = find_boom_index(
        volumes,
        volume_ratio=volume_ratio,
        k_min=boom_lookback_min,
        k_max=boom_lookback_max,
    )
    if k is None:
        return None
    if not pass_ma_bull_at_k(closes, k):
        return None
    if not pass_shrink_breakout(closes, volumes, k):
        return None

    v_prev = volumes[k + 1] if k + 1 < len(volumes) else 0.0
    ratio_actual = (volumes[k] / v_prev) if v_prev > 0 else None
    ma5 = _sma_at_index(closes, k, 5)
    ma10 = _sma_at_index(closes, k, 10)
    ma20 = _sma_at_index(closes, k, 20)
    boom_bar = historical_data[k]
    latest = historical_data[0]

    chg = round(float(latest.get("change_percent") or 0), 2)
    boom_close_f = float(boom_bar.get("close") or 0)
    breakout_close_f = float(latest.get("close") or 0)
    boom_vol_f = float(boom_bar.get("volume") or 0)
    breakout_vol_f = float(latest.get("volume") or 0)
    had_cross = had_ma5_cross_above_ma10_in_window(closes, k)
    pullback = had_pullback_below_boom_close(historical_data, closes, k, boom_close_f)
    buy_bundle = build_buy_signal_bundle(
        volume_ratio_th=float(volume_ratio),
        ratio_actual=ratio_actual,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        boom_close=boom_close_f,
        breakout_close=breakout_close_f,
        boom_vol=boom_vol_f,
        breakout_vol=breakout_vol_f,
        k=k,
        chg=chg,
        had_cross=had_cross,
        pullback=pullback,
    )
    phase_state = {
        "strategy_phase": "legacy",
        "phase1_index": k,
        "phase1_date": boom_bar.get("date"),
    }
    return {
        "strategy_phase": "legacy",
        "phase_state": phase_state,
        "boom_date": boom_bar.get("date"),
        "boom_close": round(boom_close_f, 4),
        "boom_volume": round(boom_vol_f, 2),
        "boom_volume_ratio_vs_prev": round(ratio_actual, 4) if ratio_actual is not None else None,
        "ma5_at_boom": round(ma5, 4) if ma5 is not None else None,
        "ma10_at_boom": round(ma10, 4) if ma10 is not None else None,
        "ma20_at_boom": round(ma20, 4) if ma20 is not None else None,
        "breakout_date": latest.get("date"),
        "breakout_close": round(breakout_close_f, 4),
        "breakout_volume": round(breakout_vol_f, 2),
        "change_percent": chg,
        "current_change_percent": chg,
        **buy_bundle,
    }


def _evaluate_stock_three_phase(
    historical_data: List[Dict[str, Any]],
    *,
    volume_ratio: float,
    boom_lookback_min: int,
    boom_lookback_max: int,
    cfg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not historical_data:
        return None
    closes = [float(b.get("close") or 0) for b in historical_data]
    volumes = [float(b.get("volume") or 0) for b in historical_data]
    n = len(closes)
    trend_lb = max(1, int(cfg.get("trend_ma_lookback") or 5))
    eps = float(cfg.get("retracement_break_eps") or 0.005)
    flat_tol = float(cfg.get("ma_flat_tol") or 0.008)
    vol_half = float(cfg.get("retracement_volume_half_ratio") or 0.5)
    tail_need = max(25, trend_lb + 22, 28)
    if n < boom_lookback_max + tail_need:
        return None

    hi = min(boom_lookback_max, n - 2)
    lo = max(1, boom_lookback_min)
    if lo > hi:
        return None

    chosen_s: Optional[int] = None
    for s in range(lo, hi + 1):
        if not pass_phase1_volume_spike(volumes, s, volume_ratio=volume_ratio):
            continue
        if not pass_phase1_ma5_cross_ma20_up(closes, s, trend_lb=trend_lb):
            continue
        boom_bar = historical_data[s]
        bc = closes[s]
        h_lim, c_lim, o_lim, l_lim = _bar_ohlc(boom_bar, bc)
        v_lim = float(boom_bar.get("volume") or volumes[s] or 0)
        if not validate_phase2_retracement(
            historical_data,
            closes,
            volumes,
            s,
            o_lim,
            l_lim,
            v_lim,
            eps=eps,
            vol_half=vol_half,
            flat_tol=flat_tol,
        ):
            continue
        if not validate_phase3_entry(closes, volumes, c_lim, v_lim):
            continue
        chosen_s = s
        break

    if chosen_s is None:
        return None

    s = chosen_s
    boom_bar = historical_data[s]
    latest = historical_data[0]
    bc = closes[s]
    h_lim, c_lim, o_lim, l_lim = _bar_ohlc(boom_bar, bc)
    v_lim = float(boom_bar.get("volume") or volumes[s] or 0)
    v_prev = volumes[s + 1] if s + 1 < len(volumes) else 0.0
    ratio_actual = (volumes[s] / v_prev) if v_prev > 0 else None
    ma5 = _sma_at_index(closes, s, 5)
    ma10 = _sma_at_index(closes, s, 10)
    ma20 = _sma_at_index(closes, s, 20)
    chg = round(float(latest.get("change_percent") or 0), 2)
    breakout_close_f = float(latest.get("close") or 0)
    breakout_vol_f = float(latest.get("volume") or 0)
    had_cross = had_ma5_cross_above_ma10_in_window(closes, s)
    max_re, min_hr, pullback_p2, brk_pct = _phase2_diagnostics(
        closes, volumes, s, c_lim, v_lim, vol_half=vol_half
    )
    buy_bundle = build_buy_signal_bundle_three_phase(
        volume_ratio_th=float(volume_ratio),
        ratio_actual=ratio_actual,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        c_limit=c_lim,
        breakout_close=breakout_close_f,
        v_limit=v_lim,
        breakout_vol=breakout_vol_f,
        s=s,
        chg=chg,
        had_ma5_cross_ma10_window=had_cross,
        pullback_phase2=pullback_p2,
        max_retrace_vs_climit_pct=max_re,
        min_vol_headroom_half=min_hr,
        breakout_vs_climit_pct=brk_pct,
    )
    phase_state: Dict[str, Any] = {
        "strategy_phase": "three_phase_v1",
        "phase1_index": s,
        "phase1_date": boom_bar.get("date"),
        "phase2_ok": True,
        "entry_trigger_date": latest.get("date"),
        "H_limit": round(h_lim, 4),
        "C_limit": round(c_lim, 4),
        "O_limit": round(o_lim, 4),
        "L_limit": round(l_lim, 4),
        "V_limit": round(v_lim, 2),
        "retracement_bars": max(0, s - 1),
        "max_retrace_vs_climit_pct": round(max_re, 4),
        "min_volume_headroom_vs_half": round(min_hr, 4),
    }
    return {
        "strategy_phase": "three_phase_v1",
        "phase_state": phase_state,
        "boom_date": boom_bar.get("date"),
        "boom_close": round(c_lim, 4),
        "boom_volume": round(v_lim, 2),
        "boom_volume_ratio_vs_prev": round(ratio_actual, 4) if ratio_actual is not None else None,
        "ma5_at_boom": round(ma5, 4) if ma5 is not None else None,
        "ma10_at_boom": round(ma10, 4) if ma10 is not None else None,
        "ma20_at_boom": round(ma20, 4) if ma20 is not None else None,
        "breakout_date": latest.get("date"),
        "breakout_close": round(breakout_close_f, 4),
        "breakout_volume": round(breakout_vol_f, 2),
        "change_percent": chg,
        "current_change_percent": chg,
        **buy_bundle,
    }


def evaluate_stock(
    historical_data: List[Dict[str, Any]],
    *,
    volume_ratio: float,
    boom_lookback_min: int,
    boom_lookback_max: int,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    单股判定。historical_data 按日期 DESC。
    evaluation_mode：three_phase（默认）| legacy。
    """
    cfg = config if config is not None else VolumeShrinkBreakoutConfigManager().get_default_config()
    mode = str(cfg.get("evaluation_mode") or "three_phase").strip().lower()
    if mode == "legacy":
        return _evaluate_stock_legacy(
            historical_data,
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )
    return _evaluate_stock_three_phase(
        historical_data,
        volume_ratio=volume_ratio,
        boom_lookback_min=boom_lookback_min,
        boom_lookback_max=boom_lookback_max,
        cfg=cfg,
    )


class VolumeShrinkBreakoutStrategyEngine:
    """全市场/指定池扫描。"""

    def __init__(self, loader: Any, config: Dict[str, Any]):
        self.loader = loader
        self.config = config

    def screen_universe(
        self,
        stock_rows: List[Tuple[str, str]],
        *,
        as_of_end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cal_days = int(self.config.get("history_calendar_days", 180))
        start_date, end_date = self.loader.default_date_window(cal_days, end_anchor=as_of_end_date)
        vr = float(self.config["volume_ratio"])
        kmin = int(self.config["boom_lookback_min"])
        kmax = int(self.config["boom_lookback_max"])

        results: List[Dict[str, Any]] = []
        errors = 0
        for idx, (code, name) in enumerate(stock_rows):
            if idx % 500 == 0 and idx > 0:
                logger.info("VSB 进度 %s/%s 命中=%s err=%s", idx, len(stock_rows), len(results), errors)
            try:
                hist = self.loader.fetch_historical_desc(code, start_date=start_date, end_date=end_date)
                detail = evaluate_stock(
                    hist,
                    volume_ratio=vr,
                    boom_lookback_min=kmin,
                    boom_lookback_max=kmax,
                    config=self.config,
                )
                if not detail:
                    continue
                row = {
                    "code": str(code),
                    "name": name,
                    **detail,
                }
                results.append(row)
            except Exception:
                errors += 1
                logger.debug("VSB 单股失败 code=%s", code, exc_info=True)

        logger.info("VSB 扫描完成 总数=%s 命中=%s err=%s", len(stock_rows), len(results), errors)
        return results
