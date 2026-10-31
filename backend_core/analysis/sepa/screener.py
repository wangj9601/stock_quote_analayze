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
from backend_core.analysis.sepa.trend import CONDITION_LABELS, compute_trend_template, momentum_of
from backend_core.analysis.sepa.vcp import detect_vcp

def _rank_map(prefer_ready: bool) -> Dict[str, int]:
    """排序权重。prefer_ready 时就位优先，其次未放量越过，再次放量突破。"""
    if prefer_ready:
        return {"ready": 5, "quiet": 4, "breakout": 3, "extended": 2, "forming": 1, "none": 0}
    return {"breakout": 5, "quiet": 4, "ready": 3, "extended": 2, "forming": 1, "none": 0}


_ACTIONABLE = ("breakout", "ready", "quiet")
_DEFAULT_STATUSES = ("ready", "quiet", "breakout")


def _tier(vcp_status: str, margin: Mapping[str, Any]) -> str:
    """可执行形态里，只有两融拥挤降到观察。没有两融数据保持可执行。"""
    if vcp_status not in _ACTIONABLE:
        return "C"
    if margin.get("status") == "crowded":
        return "B"
    if margin.get("status") == "no_data":
        return "A"
    score = float(margin.get("score") or 0.0)
    return "A" if score >= 55 else "B"


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

    tier = _tier(vcp["status"], margin)
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
    include_extended: bool = False,
    statuses: Optional[Sequence[str]] = None,
    tiers: Optional[Sequence[str]] = None,
    stats: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """批量筛选。先横截面算相对强度，再逐票评估，最后按可执行度+得分排序。

    stats 传入 dict 时会原地写入漏斗计数，供接口层展示每层淘汰了多少。
    statuses 给定时只保留这些形态；缺省为就位 / 未放量越过 / 放量突破，
    include_forming / include_extended 再把对应形态加进来。分级过滤在截断 top 之前做。
    """
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
    if statuses is None:
        allowed = set(_DEFAULT_STATUSES)
    else:
        allowed = {str(s).strip() for s in statuses if str(s).strip()}
    if include_forming:
        allowed.add("forming")
    if include_extended:
        allowed.add("extended")
    tier_wanted = {str(t).strip().upper() for t in (tiers or []) if str(t).strip()}

    funnel: Dict[str, int] = {
        "universe": len(codes),
        "trend_pass": 0,
        "vcp_any": 0,
        "breakout": 0,
        "quiet": 0,
        "ready": 0,
        "extended": 0,
        "forming": 0,
    }
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
        funnel["trend_pass"] += 1
        if res["vcp"] is None or res["vcp"]["status"] == "none":
            continue
        funnel["vcp_any"] += 1
        status = res["vcp"]["status"]
        if status in funnel:
            funnel[status] += 1
        if status not in allowed:
            continue
        out.append(res)

    if stats is not None:
        stats.update(funnel)

    rank = _rank_map(c.prefer_ready)
    out.sort(key=lambda r: (rank.get(r["vcp"]["status"], 0), r["score"]), reverse=True)
    if tier_wanted:
        out = [r for r in out if (r.get("tier") or "").upper() in tier_wanted]
    return out[: int(top or c.top)]


def screen_report(
    bars_by_code: Mapping[str, Sequence[Dict[str, Any]]],
    **kwargs: Any,
) -> Dict[str, Any]:
    """screen_universe 的带统计版本：返回 {rows, stats}，供接口层展示漏斗。"""
    stats: Dict[str, int] = {}
    rows = screen_universe(bars_by_code, stats=stats, **kwargs)
    return {"rows": rows, "stats": stats}


def to_table_rows(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """压平成表格行，便于接口层直接返回前端。"""
    rows: List[Dict[str, Any]] = []
    for r in results:
        vcp = r.get("vcp") or {}
        margin = r.get("margin") or {}
        trend = r.get("trend") or {}
        metrics = trend.get("metrics") or {}
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
                "close": vcp.get("close"),
                "vol_ratio": vcp.get("vol_ratio"),
                "tight_range_pct": vcp.get("tight_range_pct"),
                "base_tight_range_pct": vcp.get("base_tight_range_pct"),
                "invalidation": vcp.get("invalidation"),
                "contractions": vcp.get("contractions") or [],
                "vcp_notes": vcp.get("notes") or [],
                "margin_status": margin.get("status"),
                "margin_status_label": margin.get("status_label"),
                "margin_score": margin.get("score"),
                "crowd_pct": margin.get("crowd_pct"),
                "drawdown_pct": margin.get("drawdown_pct"),
                "reflow_pct": margin.get("reflow_pct"),
                "margin_notes": margin.get("notes") or [],
                "rs_rank": metrics.get("rs_rank"),
                "extended_pct": metrics.get("extended_pct"),
                "off_high_pct": metrics.get("off_high_pct"),
                "off_low_pct": metrics.get("off_low_pct"),
                "ma50": metrics.get("ma50"),
                "ma150": metrics.get("ma150"),
                "ma200": metrics.get("ma200"),
                "trend_checks": [
                    {"id": k, "label": CONDITION_LABELS[k], "ok": bool((trend.get("conditions") or {}).get(k))}
                    for k in range(1, 9)
                ],
                "flags": "、".join(r.get("flags") or []),
            }
        )
    return rows
