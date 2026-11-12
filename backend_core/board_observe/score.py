# -*- coding: utf-8 -*-
"""观察池候选计分与入/出资格（不含粘性）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend_core.board_gates.config import TREND_AVOID_MIDLONG
from backend_core.board_metrics.sector_slope_store import SLOPE_SOURCE_EQUAL_WEIGHT
from backend_core.board_observe.config import (
    IN_SCORE_THRESHOLD,
    LOCK_EXCLUDE,
    LOCK_INCLUDE,
    MIN_HIST_BARS,
    RS_SCORE_MIN,
    RS_VETO_MAX,
)


def _env_strong(env: Optional[str]) -> bool:
    return str(env or "") == "strong"


def _env_weak(env: Optional[str]) -> bool:
    return str(env or "") == "weak"


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def score_board(
    *,
    env60: Optional[str],
    slope60: Optional[float],
    env120: Optional[str],
    slope120: Optional[float],
    slope_source_60: Optional[str],
    net_sum_20: Optional[float],
    board_rs: Optional[int],
    mainline_or_focus: bool,
    bars: int,
    board_trend_label: Optional[str],
    fund_stage: Optional[str],
    observe_lock: str,
    in_formal_pool: bool,
) -> Tuple[int, Dict[str, Any], List[str], bool, bool, bool]:
    """
    返回: score, evidence, vetoes, hard_exclude, in_eligible, out_eligible
    """
    evidence: Dict[str, Any] = {
        "env60": env60,
        "slope60": slope60,
        "env120": env120,
        "slope120": slope120,
        "slope_source_60": slope_source_60,
        "net_sum_20": net_sum_20,
        "board_rs": board_rs,
        "mainline_or_focus": bool(mainline_or_focus),
        "bars": int(bars),
        "board_trend_label": board_trend_label,
        "fund_stage": fund_stage,
        "points": {},
    }
    vetoes: List[str] = []
    lock = (observe_lock or "follow").strip().lower() or "follow"
    hard_exclude = False

    if lock == LOCK_EXCLUDE:
        hard_exclude = True
        vetoes.append("lock_exclude")

    if not _env_strong(env60) and not _env_weak(env60) and slope60 is None:
        hard_exclude = True
        vetoes.append("slope60_missing")
    elif env60 in (None, "", "unknown", "insufficient"):
        # 无有效环境且无斜率
        if slope60 is None:
            hard_exclude = True
            vetoes.append("env60_unavailable")

    if int(bars) < MIN_HIST_BARS:
        hard_exclude = True
        vetoes.append("hist_bars_lt_120")

    score = 0
    pts = evidence["points"]

    # 价·中：真走强（假强不计：env 不为 strong）
    if _env_strong(env60):
        score += 1
        pts["price_60"] = 1
    else:
        pts["price_60"] = 0

    # 价·长：走强或斜率>=0 且非走弱
    if _env_strong(env120) or (
        slope120 is not None and float(slope120) >= 0 and not _env_weak(env120)
    ):
        score += 1
        pts["price_120"] = 1
    else:
        pts["price_120"] = 0

    # 量
    net20 = _f(net_sum_20)
    eq = str(slope_source_60 or "") == SLOPE_SOURCE_EQUAL_WEIGHT
    if net20 is not None:
        if (eq and net20 > 0) or (not eq and net20 >= 0):
            score += 1
            pts["fund_20"] = 1
        else:
            pts["fund_20"] = 0
    else:
        pts["fund_20"] = 0

    # RS
    if board_rs is not None and int(board_rs) >= RS_SCORE_MIN:
        score += 1
        pts["board_rs"] = 1
    else:
        pts["board_rs"] = 0

    # 主线/焦点
    if mainline_or_focus:
        score += 1
        pts["mainline_focus"] = 1
    else:
        pts["mainline_focus"] = 0

    evidence["score"] = score

    # 一票否决（仅影响 suggest_in）
    trend = str(board_trend_label or "").strip()
    if trend in TREND_AVOID_MIDLONG:
        vetoes.append("trend_long_weak")
    weak60 = _env_weak(env60)
    if fund_stage in ("decline", "distribute") and weak60:
        vetoes.append("fund_stage_weak60")
    if board_rs is not None and int(board_rs) <= RS_VETO_MAX and weak60:
        vetoes.append("rs_low_weak60")

    in_veto = any(
        v in vetoes
        for v in (
            "lock_exclude",
            "slope60_missing",
            "env60_unavailable",
            "hist_bars_lt_120",
            "trend_long_weak",
            "fund_stage_weak60",
            "rs_low_weak60",
        )
    )
    in_eligible = (
        (not hard_exclude)
        and (not in_veto)
        and score >= IN_SCORE_THRESHOLD
        and lock != LOCK_EXCLUDE
    )

    # 移出：仅正式池（lock=include 仍可标出资格，但采纳时拦截）
    out_eligible = False
    if in_formal_pool:
        out_reasons: List[str] = []
        if weak60 and _env_weak(env120):
            out_reasons.append("both_windows_weak")
        if score < 1:
            out_reasons.append("score_lt_1")
        if fund_stage == "decline" and weak60:
            out_reasons.append("decline_weak60")
        if (
            board_rs is not None
            and int(board_rs) <= RS_VETO_MAX
            and net20 is not None
            and net20 < 0
        ):
            out_reasons.append("rs_low_fund_neg")
        if out_reasons:
            out_eligible = True
            evidence["out_reasons"] = out_reasons
        if lock == LOCK_INCLUDE:
            evidence["out_blocked_by_lock"] = True

    evidence["in_eligible"] = bool(in_eligible)
    evidence["out_eligible"] = bool(out_eligible)
    evidence["in_score_threshold"] = IN_SCORE_THRESHOLD

    return score, evidence, vetoes, hard_exclude, in_eligible, out_eligible
