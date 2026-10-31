# -*- coding: utf-8 -*-
"""VCP（Volatility Contraction Pattern）识别与枢轴点突破。

实现要点
--------
1. 摆动点直接复用 analysis.swing_zigzag：Williams 分形找候选点，再用
   max(收盘价*2.5%, ATR*1.5) 作为深度门槛过滤噪音——比固定百分比更适配不同波动率个股。
2. 把 ZigZag 链上相邻的"高->低"配对成回调腿，计算幅度与均量。
3. 从最后一腿往回吞并，只要"幅度递减 + 低点抬高 + 量能递减"都成立就继续，
   得到最长有效收缩序列（VCP 的嵌套定义）。
4. 枢轴点 = 最后一腿的高点。可执行买点必须至少两段收缩：
   就位（枢轴下方紧凑）、未放量越过、放量突破（距枢轴不超过 chase_distance）。
   突破日会撑开振幅，紧凑度看突破前的 N 根，不把当日算进去。

注意：不做"预测"，只描述当前形态位置；形态失败（跌破最后收缩低点）会自然退出 gate。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from backend_core.analysis.sepa.bars import parse_bars
from backend_core.analysis.sepa.config import VCP_STATUS_LABELS, VCPConfig
from backend_core.analysis.swing_zigzag import (
    ATR_DEPTH_MULT,
    MIN_DEPTH_PCT,
    find_fractal_pivots,
    wilder_atr,
    zigzag_from_fractals,
)


def _depth_gate(close: float, atr: Optional[float], cfg: VCPConfig) -> float:
    base = abs(close) * float(cfg.min_depth_pct or MIN_DEPTH_PCT)
    if atr is not None and close > 0:
        base = max(base, float(atr) * float(cfg.atr_mult or ATR_DEPTH_MULT))
    return base


def _legs(zz: Sequence[Dict[str, Any]], vol: np.ndarray) -> List[Dict[str, Any]]:
    """相邻峰谷配成回调腿（仅取 高->低）。"""
    legs: List[Dict[str, Any]] = []
    for a, b in zip(zz, zz[1:]):
        if a.get("kind") != "high" or b.get("kind") != "low":
            continue
        hi_i, lo_i = int(a["index"]), int(b["index"])
        hi_p, lo_p = float(a["price"]), float(b["price"])
        if hi_p <= 0 or lo_i <= hi_i:
            continue
        legs.append(
            {
                "hi_index": hi_i,
                "hi": hi_p,
                "hi_date": a.get("date"),
                "lo_index": lo_i,
                "lo": lo_p,
                "lo_date": b.get("date"),
                "depth": (hi_p - lo_p) / hi_p,
                "days": lo_i - hi_i,
                "avg_vol": float(np.mean(vol[hi_i: lo_i + 1])) if vol.size else 0.0,
            }
        )
    return legs


def _trailing_sequence(legs: List[Dict[str, Any]], cfg: VCPConfig) -> List[Dict[str, Any]]:
    """从最后一腿往回吞并，返回时间升序的收缩序列。"""
    if not legs:
        return []
    seq = [legs[-1]]
    for leg in reversed(legs[:-1]):
        cur = seq[0]
        depth_ok = leg["depth"] >= cur["depth"] * (1.0 - cfg.depth_tolerance)
        high_ok = leg["hi"] >= cur["hi"] * 0.98          # 高点不显著上移（允许微升）
        low_ok = leg["lo"] <= cur["lo"] * 1.01           # 低点必须抬高
        vol_ok = leg["avg_vol"] >= cur["avg_vol"] * (1.0 + cfg.min_vol_decay)
        if depth_ok and high_ok and low_ok and vol_ok:
            seq.insert(0, leg)
        else:
            break
    return seq


def _score(seq: List[Dict[str, Any]], tight_range: float, vol_ratio: float,
           status: str, cfg: VCPConfig) -> float:
    """0~100 形态质量分：次数 40、末次深度 20、量能衰减 20、末端紧凑度 20。"""
    if not seq:
        return 10.0 if status == "forming" else 0.0
    count_score = min(len(seq), 3) / 3.0 * 40.0
    depth_score = max(0.0, 1.0 - seq[-1]["depth"] / max(cfg.max_last_depth, 1e-6)) * 20.0
    decay = 1.0 - seq[-1]["avg_vol"] / seq[0]["avg_vol"] if seq[0]["avg_vol"] > 0 else 0.0
    vol_score = min(max(decay, 0.0), 1.0) * 20.0
    if np.isfinite(tight_range) and cfg.max_tight_range > 0:
        tight_score = max(0.0, 1.0 - tight_range / cfg.max_tight_range) * 20.0
    else:
        tight_score = 0.0
    total = count_score + depth_score + vol_score + tight_score
    # 量比 1.0~1.5 的前瞻收益几乎无差别，3 倍量偏负，不再给放量额外加分。
    del vol_ratio, status
    return round(min(total, 100.0), 1)


def detect_vcp(
    bars: Sequence[Dict[str, Any]],
    *,
    cfg: Optional[VCPConfig] = None,
) -> Dict[str, Any]:
    """返回 {ok, status, status_label, count, contractions, pivot, dist_to_pivot_pct, ...}。"""
    c = cfg or VCPConfig()
    data = parse_bars(bars)
    n = len(data["close"])
    if n < 60:
        return {
            "ok": False,
            "status": "none",
            "status_label": VCP_STATUS_LABELS["none"],
            "count": 0,
            "contractions": [],
            "pivot": None,
            "close": None,
            "dist_to_pivot_pct": None,
            "vol_ratio": None,
            "tight_range_pct": None,
            "base_tight_range_pct": None,
            "invalidation": None,
            "score": 0.0,
            "notes": ["k_bars_insufficient"],
        }

    start = max(0, n - int(c.lookback))
    parsed = data["parsed"][start:]
    vol = data["volume"][start:]
    close = float(data["close"][-1])
    high = data["high"][start:]
    low = data["low"][start:]

    atr = wilder_atr(parsed)
    gate = _depth_gate(close, atr, c)
    pivots = find_fractal_pivots(parsed, left=c.fractal_left, right=c.fractal_right)
    zz = zigzag_from_fractals(pivots, depth=gate)

    legs = _legs(zz, vol)
    seq = _trailing_sequence(legs, c)

    notes: List[str] = []
    if not seq:
        notes.append("no_pullback_leg")

    count = len(seq)
    pivot = float(seq[-1]["hi"]) if seq else float("nan")
    dist = (close / pivot - 1.0) if np.isfinite(pivot) and pivot > 0 else float("nan")

    vol_ma_win = min(int(c.vol_ma), vol.size)
    vol_ma = float(np.mean(vol[-vol_ma_win:])) if vol_ma_win > 0 else float("nan")
    vol_ratio = float(vol[-1] / vol_ma) if np.isfinite(vol_ma) and vol_ma > 0 else float("nan")

    tight_win = min(int(c.tight_days), len(low))
    t_low = float(np.min(low[-tight_win:])) if tight_win else float("nan")
    t_high = float(np.max(high[-tight_win:])) if tight_win else float("nan")
    tight_range = (t_high - t_low) / t_low if t_low > 0 else float("nan")
    # 突破日当天会把振幅撑开。放量突破 / 未放量越过的紧凑度看突破前 N 根。
    if tight_win > 0 and len(low) > tight_win:
        b_low = float(np.min(low[-(tight_win + 1):-1]))
        b_high = float(np.max(high[-(tight_win + 1):-1]))
        base_tight = (b_high - b_low) / b_low if b_low > 0 else float("nan")
    else:
        base_tight = tight_range

    count_ok = count >= c.min_contractions
    tight_now = bool(np.isfinite(tight_range) and tight_range <= c.max_tight_range)
    tight_base = bool(np.isfinite(base_tight) and base_tight <= c.max_tight_range)
    vol_ok = bool(np.isfinite(vol_ratio) and vol_ratio >= c.breakout_vol_multiple)
    depth_ok = (not seq) or float(seq[-1]["depth"]) <= c.max_last_depth or not c.enforce_last_depth
    entry_hi = min(float(c.chase_distance), float(c.max_breakout_distance))
    ready_band = bool(np.isfinite(dist) and -c.ready_distance <= dist < c.breakout_buffer)
    entry_band = bool(np.isfinite(dist) and c.breakout_buffer <= dist <= entry_hi)
    extended_band = bool(np.isfinite(dist) and entry_hi < dist <= c.max_breakout_distance)
    beyond = bool(np.isfinite(dist) and dist > c.max_breakout_distance)

    if beyond:
        # 突破早已发生、股价远离枢轴：既不是入场点，也不该算"收缩中"
        status = "none"
        notes.append("extended_from_pivot")
    elif count_ok and depth_ok and tight_now and ready_band:
        status = "ready"
    elif count_ok and depth_ok and tight_base and entry_band and vol_ok:
        status = "breakout"
    elif count_ok and depth_ok and tight_base and entry_band:
        status = "quiet"
    elif count_ok and extended_band:
        status = "extended"
        notes.append("chase_risk")
    elif count >= c.min_contractions:
        status = "forming"
    elif tight_now:
        status = "forming"
        notes.append("tight_without_full_sequence")
    else:
        status = "none"

    if seq and seq[-1]["depth"] > c.max_last_depth:
        notes.append("last_contraction_too_deep")
        # 末次收缩过深说明浮筹没吸收干净。深度不够时上面的 depth_ok 已挡住可执行状态；
        # 这里再收一次，避免 enforce 开关与分支顺序不一致时漏网。
        if c.enforce_last_depth and status in ("breakout", "ready", "quiet"):
            status = "forming"

    return {
        "ok": status in ("breakout", "ready", "quiet"),
        "status": status,
        "status_label": VCP_STATUS_LABELS.get(status, status),
        "count": count,
        "contractions": [
            {
                "depth_pct": round(x["depth"] * 100, 2),
                "days": x["days"],
                "hi": round(x["hi"], 2),
                "lo": round(x["lo"], 2),
                "hi_date": x["hi_date"],
                "lo_date": x["lo_date"],
            }
            for x in seq
        ],
        "pivot": round(pivot, 2) if np.isfinite(pivot) else None,
        "close": round(close, 2),
        "dist_to_pivot_pct": round(dist * 100, 2) if np.isfinite(dist) else None,
        "vol_ratio": round(vol_ratio, 2) if np.isfinite(vol_ratio) else None,
        "tight_range_pct": round(tight_range * 100, 2) if np.isfinite(tight_range) else None,
        "base_tight_range_pct": round(base_tight * 100, 2) if np.isfinite(base_tight) else None,
        "invalidation": round(float(seq[-1]["lo"]), 2) if seq else None,
        "score": _score(seq, tight_range, vol_ratio, status, c),
        "notes": notes,
    }
