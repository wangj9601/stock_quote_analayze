# -*- coding: utf-8 -*-
"""URT 结构盈亏比风险提示（软标签，不改得分、不硬筛）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def enrich_structure_with_rr(
    structure: Optional[Dict[str, Any]],
    *,
    price: Optional[float],
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为 structure 补写 rr / rr_reason，并生成 risk_tags。"""
    cfg = cfg or {}
    st = dict(structure or {})
    from backend_core.strategies.gms.structure_levels import compute_structure_rr

    info = compute_structure_rr(price, st.get("nearest_support"), st.get("nearest_resistance"))
    st["rr"] = info.get("rr")
    st["rr_reason"] = info.get("reason")
    tags = build_structure_rr_risk_tags(st, cfg, price=price, rr_info=info)
    return {"structure": st, "risk_tags": tags}


def build_structure_rr_risk_tags(
    structure: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    price: Optional[float] = None,
    rr_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    基于 KDE 最近支撑/阻力生成 risk_tags。
    复用 GMS compute_structure_rr 口径；无阻力 / 无支撑 / KDE 失败不提示。
    """
    cfg = cfg or {}
    if cfg.get("structure_rr_warn_enabled") is False:
        return []

    st = structure if isinstance(structure, dict) else {}
    if rr_info is None:
        from backend_core.strategies.gms.structure_levels import compute_structure_rr

        px = price
        rr_info = compute_structure_rr(px, st.get("nearest_support"), st.get("nearest_resistance"))

    rr = rr_info.get("rr") if rr_info else st.get("rr")
    reason = (rr_info.get("reason") if rr_info else None) or st.get("rr_reason") or ""
    should = rr_info.get("should_penalize") if rr_info else None

    try:
        min_rr = float(cfg.get("structure_rr_min_rr") or 1.5)
    except (TypeError, ValueError):
        min_rr = 1.5

    tags: List[Dict[str, str]] = []
    if should is True:
        if reason in ("below_or_no_support", "zero_downside"):
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "破位支撑",
                    "level": "danger",
                    "reason": f"现价不高于最近支撑（结构盈亏比要求 ≥{min_rr:g}）",
                }
            )
        elif reason == "at_resistance":
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "贴/超阻力",
                    "level": "danger",
                    "reason": f"上行空间不足 RR={rr if rr is not None else 0}（要求 ≥{min_rr:g}）",
                }
            )
        else:
            tags.append(
                {
                    "id": "poor_structure_rr",
                    "label": "结构盈亏比偏低",
                    "level": "warn",
                    "reason": f"结构盈亏比异常（{reason}）",
                }
            )
        return tags

    if should is False:
        return []

    if rr is None:
        return []
    try:
        rr_f = float(rr)
    except (TypeError, ValueError):
        return []
    if rr_f < min_rr:
        tags.append(
            {
                "id": "poor_structure_rr",
                "label": "结构盈亏比偏低",
                "level": "warn",
                "reason": f"结构盈亏比 RR={rr_f:.2f} < {min_rr:g}",
            }
        )
    return tags
