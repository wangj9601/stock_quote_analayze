"""当日候选池质量分 Min-Max 归一化。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def map_rpe_z_to_raw(z: float) -> float:
    """RPE z_score → 近似 0~100 原始分。"""
    return max(0.0, min(100.0, 50.0 + float(z) * 10.0))


def _minmax(values: List[float]) -> Dict[float, float]:
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi <= lo:
        return {v: 50.0 for v in values}
    return {v: (v - lo) / (hi - lo) * 100.0 for v in values}


def normalize_strategy_scores(
    by_strategy: Dict[str, List[Dict[str, Any]]],
    *,
    default_missing: float = 50.0,
) -> Dict[str, List[Dict[str, Any]]]:
    """就地为每行写入 quality_raw / quality_norm，返回同一结构。"""
    from backend_core.recommend.config import QUALITY_DEFAULT_MISSING

    miss = float(default_missing if default_missing is not None else QUALITY_DEFAULT_MISSING)
    out: Dict[str, List[Dict[str, Any]]] = {}
    for strat, rows in (by_strategy or {}).items():
        mapped: List[Dict[str, Any]] = []
        raws: List[float] = []
        for row in rows or []:
            r = dict(row)
            sc = r.get("score")
            raw: Optional[float] = None
            if sc is not None:
                try:
                    f = float(sc)
                    if strat == "rpe":
                        raw = map_rpe_z_to_raw(f)
                    else:
                        raw = f
                except (TypeError, ValueError):
                    raw = None
            if raw is None and strat == "sbbr":
                raw = miss
            r["quality_raw"] = raw
            if raw is not None:
                raws.append(raw)
            mapped.append(r)
        # 唯一值映射
        uniq = list({round(x, 6): x for x in raws}.values()) if raws else []
        mm = _minmax(uniq)
        for r in mapped:
            raw = r.get("quality_raw")
            if raw is None:
                r["quality_norm"] = miss
            else:
                # 找最近 key
                key = min(mm.keys(), key=lambda k: abs(k - float(raw))) if mm else None
                r["quality_norm"] = round(mm[key], 4) if key is not None else miss
        out[strat] = mapped
    return out


def apply_normalized_best_score(
    merged: Dict[str, Dict[str, Any]],
    *,
    regime_weights: Optional[Dict[str, float]] = None,
) -> None:
    """根据各策略 quality_norm（可加权）更新 bucket.best_score / best_score_raw。"""
    weights = regime_weights or {}
    for bucket in (merged or {}).values():
        best = None
        best_raw = None
        rows = bucket.get("strategy_rows") or {}
        for strat, row in rows.items():
            if not isinstance(row, dict):
                continue
            qn = row.get("quality_norm")
            if qn is None:
                continue
            try:
                w = float(weights.get(strat, 1.0))
                val = float(qn) * w
            except (TypeError, ValueError):
                continue
            if best is None or val > best:
                best = val
                try:
                    best_raw = float(row.get("quality_raw")) if row.get("quality_raw") is not None else float(qn)
                except (TypeError, ValueError):
                    best_raw = float(qn)
        if best is not None:
            bucket["best_score"] = round(min(best, 100.0), 4)
            bucket["best_score_raw"] = best_raw
            bucket["quality_norm"] = round(min(best, 100.0), 4)
