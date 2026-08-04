# -*- coding: utf-8 -*-
"""URT 打分：连阳强度 + 量能超额 + 中期阳线/多头轻度加分 + 可选换手/量比。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .indicators import normalize_yang_medium_rules


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


def _yang_medium_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """中期阳线最多约 6 分：按各窗口相对阈值完成度等权平均。"""
    rules = normalize_yang_medium_rules(cfg)
    detail = ind.get("yang_medium_detail")
    by_window: Dict[int, int] = {}
    if isinstance(detail, list):
        for d in detail:
            if isinstance(d, dict) and d.get("window") is not None:
                try:
                    by_window[int(d["window"])] = int(d.get("count") or 0)
                except (TypeError, ValueError):
                    continue
    ratios: List[float] = []
    items: List[Dict[str, Any]] = []
    for rule in rules:
        w = int(rule["window"])
        need = max(1, int(rule["min_up_days"]))
        cnt = by_window.get(w)
        if cnt is None:
            key = f"yang_count_{w}"
            try:
                cnt = int(ind.get(key) or 0)
            except (TypeError, ValueError):
                cnt = 0
        ratio = min(1.0, float(cnt) / float(need))
        ratios.append(ratio)
        items.append({"window": w, "count": cnt, "min_up_days": need, "ratio": round(ratio, 4)})
    if not ratios:
        return 0.0, {"score": 0.0, "max": 6, "items": []}
    part = round(sum(ratios) / len(ratios) * 6.0, 2)
    return part, {
        "score": part,
        "max": 6,
        "ok": bool(ind.get("yang_medium_ok")),
        "items": items,
    }


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

    # 量能主分上限略降为 34，腾出中期阳线/多头空间（总分仍封顶 100）
    vm = float(ind.get("volume_multiple") or 0)
    need = float(cfg.get("volume_multiple") or 2.5)
    vol_raw = _volume_score(vm, need)
    vol_part = round(vol_raw * 34.0 / 40.0, 2)
    parts["volume"] = {
        "volume_multiple": vm,
        "threshold": need,
        "score": vol_part,
        "max": 34,
    }
    score += vol_part

    mid_part, mid_meta = _yang_medium_score(ind, cfg)
    parts["yang_medium"] = mid_meta
    score += mid_part

    bull_ok = bool(ind.get("ma_bull_ok"))
    bull_part = 4.0 if bull_ok else 0.0
    parts["ma_bull"] = {
        "ok": bull_ok,
        "score": bull_part,
        "max": 4,
        "periods": ind.get("ma_bull_periods") or [5, 10, 20],
        "values": ind.get("ma_bull_values"),
        "ma5": ind.get("ma5"),
        "ma10": ind.get("ma10"),
        "ma20_stack": ind.get("ma20_stack"),
        "hard_filter": bool(cfg.get("require_ma_bull")),
    }
    score += bull_part

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
            "ma5": ind.get("ma5"),
            "ma10": ind.get("ma10"),
            "yang_count_10": ind.get("yang_count_10"),
            "yang_count_15": ind.get("yang_count_15"),
            "yang_count_20": ind.get("yang_count_20"),
            "volume": ind.get("volume"),
            "avg_volume_20": ind.get("avg_volume_20"),
            "date": ind.get("date"),
        },
    }
    return total, detail


def compute_score(ind: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    total, _ = compute_score_breakdown(ind, cfg)
    return total
