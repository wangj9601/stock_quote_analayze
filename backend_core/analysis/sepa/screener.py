# -*- coding: utf-8 -*-
"""SEPA 编排层：单票评估 + 全市场批量筛选。

单票：evaluate_stock(bars, rs_rank=..., margin_rows=...) -> Dict
批量：screen_universe(bars_by_code, margin_by_code=...) -> List[Dict]（内部统一算相对强度）
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend_core.analysis.sepa.bars import rs_rank
from backend_core.analysis.sepa.config import DISCLAIMER, TIER_LABELS, SEPAConfig
from backend_core.analysis.sepa.margin import assess_margin
from backend_core.analysis.sepa.trend import compute_trend_template, momentum_of
from backend_core.analysis.sepa.vcp import detect_vcp

_STATUS_RANK = {"breakout": 3, "ready": 2, "forming": 1, "none": 0}


def _tier(vcp_status: str, margin_score: float) -> str:
    if vcp_status == "breakout":
        return "A" if margin_score >= 55 else "B"
    if vcp_status == "ready":
        return "B" if margin_score >= 55 else "C"
    return "C"


def evaluate_stock(
    bars: Sequence[Dict[str, Any]],
    *,
    code: str = "",
    name: str = "",
    rs_rank: Optional[float] = None,
    margin_rows: Optional[Sequence[Dict[str, Any]]] = None,
    circ_mv: Optional[float] = None,
    cfg: Optional[SEPAConfig] = None,
) -> Dict[str, Any]:
    """单票完整评估。趋势不过关时提前返回，省掉形态计算。"""
    c = cfg or SEPAConfig()

    trend = compute_trend_template(bars, rs_rank=rs_rank, cfg=c.trend)
    if not trend["ok"]:
        return {
            "ok": False,
            "code": code,
            "name": name,
            "tier": None,
            "tier_label": None,
            "score": 0.0,
            "reason": trend["reason"],
            "failed": trend["failed"],
            "trend": trend,
            "vcp": None,
            "margin": None,
            "flags": list(trend["failed"]),
            "disclaimer": DISCLAIMER,
        }

    vcp = detect_vcp(bars, cfg=c.vcp)
    margin = assess_margin(margin_rows or [], circ_mv=circ_mv, cfg=c.margin)

    score = (
        c.weight_vcp * float(vcp["score"])
        + c.weight_margin * float(margin["score"])
        + c.weight_trend * float(trend["metrics"].get("trend_quality") or 0.0)
    )

    flags: List[str] = []
    extended = trend["metrics"].get("extended_pct")
    if extended is not None and extended > 10:
        flags.append("偏离50日线过远")
    if margin["status"] == "crowded":
        flags.append("两融拥挤")
    flags.extend(vcp["notes"])

    tier = _tier(vcp["status"], float(margin["score"]))
    return {
        "ok": bool(vcp["ok"]),
        "code": code,
        "name": name,
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, tier),
        "score": round(float(score), 1),
        "reason": "" if vcp["ok"] else "vcp_not_actionable",
        "failed": [],
        "trend": trend,
        "vcp": vcp,
        "margin": margin,
        "flags": flags,
        "disclaimer": DISCLAIMER,
    }


def screen_universe(
    bars_by_code: Mapping[str, Sequence[Dict[str, Any]]],
    *,
    margin_by_code: Optional[Mapping[str, Sequence[Dict[str, Any]]]] = None,
    circ_mv_by_code: Optional[Mapping[str, float]] = None,
    names: Optional[Mapping[str, str]] = None,
    cfg: Optional[SEPAConfig] = None,
    top: Optional[int] = None,
    include_forming: bool = False,
) -> List[Dict[str, Any]]:
    """批量筛选。先横截面算相对强度，再逐票评估，最后按可执行度+得分排序。"""
    c = cfg or SEPAConfig()
    margin_by_code = margin_by_code or {}
    circ_mv_by_code = circ_mv_by_code or {}
    names = names or {}

    codes = [k for k, v in bars_by_code.items() if v]
    if not codes:
        return []

    momentum = {code: momentum_of(bars_by_code[code]) for code in codes}
    ranks = dict(zip(codes, rs_rank([momentum[k] for k in codes])))

    out: List[Dict[str, Any]] = []
    for code in codes:
        res = evaluate_stock(
            bars_by_code[code],
            code=code,
            name=names.get(code, ""),
            rs_rank=ranks.get(code),
            margin_rows=margin_by_code.get(code),
            circ_mv=circ_mv_by_code.get(code),
            cfg=c,
        )
        if not res["trend"]["ok"]:
            continue
        if res["vcp"] is None or res["vcp"]["status"] == "none":
            continue
        if not include_forming and res["vcp"]["status"] == "forming":
            continue
        out.append(res)

    out.sort(key=lambda r: (_STATUS_RANK.get(r["vcp"]["status"], 0), r["score"]), reverse=True)
    return out[: int(top or c.top)]


def to_table_rows(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """压平成表格行，便于接口层直接返回前端。"""
    rows: List[Dict[str, Any]] = []
    for r in results:
        vcp = r.get("vcp") or {}
        margin = r.get("margin") or {}
        trend = r.get("trend") or {}
        rows.append(
            {
                "code": r["code"],
                "name": r.get("name") or "",
                "tier": r.get("tier"),
                "tier_label": r.get("tier_label"),
                "score": r.get("score"),
                "vcp_status": vcp.get("status"),
                "vcp_status_label": vcp.get("status_label"),
                "vcp_count": vcp.get("count"),
                "pivot": vcp.get("pivot"),
                "dist_to_pivot_pct": vcp.get("dist_to_pivot_pct"),
                "vol_ratio": vcp.get("vol_ratio"),
                "margin_status": margin.get("status"),
                "margin_status_label": margin.get("status_label"),
                "margin_score": margin.get("score"),
                "crowd_pct": margin.get("crowd_pct"),
                "rs_rank": (trend.get("metrics") or {}).get("rs_rank"),
                "extended_pct": (trend.get("metrics") or {}).get("extended_pct"),
                "flags": "、".join(r.get("flags") or []),
            }
        )
    return rows
