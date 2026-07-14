# -*- coding: utf-8 -*-
"""URT 打分：连阳强度 + 量能超额 + 可选换手/量比。"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def _yang_score(ya: int, yb: int) -> float:
    if yb >= 5:
        return 40.0
    if yb >= 4:
        return 36.0
    if ya >= 4:
        return 34.0
    if ya >= 3:
        return 30.0
    return max(0.0, ya * 8.0)


def _volume_score(vm: float, need: float) -> float:
    need = max(need, 0.1)
    if vm >= need:
        return 30.0 + min(10.0, (vm - need) / need * 10.0)
    return max(0.0, vm / need * 30.0)


def compute_score_breakdown(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """返回 (总分, 分项明细)。"""
    parts: Dict[str, Any] = {}
    score = 0.0

    above = bool(ind.get("above_ma20"))
    ma_part = 10.0 if above else 0.0
    parts["above_ma20"] = {"ok": above, "score": ma_part, "max": 10}
    score += ma_part

    ya = int(ind.get("yang_count_4") or 0)
    yb = int(ind.get("yang_count_5") or 0)
    yang_part = _yang_score(ya, yb)
    parts["yang"] = {
        "yang_count_4": ya,
        "yang_count_5": yb,
        "score": yang_part,
        "max": 40,
    }
    score += yang_part

    vm = float(ind.get("volume_multiple") or 0)
    need = float(cfg.get("volume_multiple") or 2.5)
    vol_part = _volume_score(vm, need)
    parts["volume"] = {
        "volume_multiple": vm,
        "threshold": need,
        "score": round(vol_part, 2),
        "max": 40,
    }
    score += vol_part

    use_to = bool(cfg.get("use_turnover"))
    use_vr = bool(cfg.get("use_volume_ratio"))
    to_part = 0.0
    if use_to:
        to = ind.get("turnover_rate")
        if to is not None:
            to_part = min(5.0, max(0.0, float(to) / 8.0 * 5.0))
    parts["turnover"] = {
        "enabled": use_to,
        "turnover_rate": ind.get("turnover_rate"),
        "score": round(to_part, 2),
        "max": 5 if use_to else 0,
    }
    score += to_part

    vr_part = 0.0
    if use_vr:
        vr = ind.get("volume_ratio")
        if vr is not None:
            vr_part = min(5.0, max(0.0, float(vr) / 3.0 * 5.0))
    parts["volume_ratio"] = {
        "enabled": use_vr,
        "volume_ratio": ind.get("volume_ratio"),
        "score": round(vr_part, 2),
        "max": 5 if use_vr else 0,
    }
    score += vr_part

    total = round(min(100.0, score), 2)
    detail = {
        "total": total,
        "min_score": float(cfg.get("min_score") or 70),
        "parts": parts,
        "inputs": {
            "close": ind.get("close"),
            "open": ind.get("open"),
            "ma20": ind.get("ma20"),
            "volume": ind.get("volume"),
            "avg_volume_20": ind.get("avg_volume_20"),
            "date": ind.get("date"),
        },
    }
    return total, detail


def compute_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    total, _ = compute_score_breakdown(ind, cfg)
    return total
