# -*- coding: utf-8 -*-
"""短线 / 中长线 raw 判定（未做确认粘性）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend_core.board_gates.config import (
    BOARD_RS_ALLOC_MIN,
    BOARD_RS_AVOID_MAX,
    BOARD_RS_EXPENSIVE_BYPASS,
    FUND_STAGES_BLOCK_MIDLONG,
    RAW_ALLOC,
    RAW_AVOID,
    RAW_WATCH,
    TREND_AVOID_MIDLONG,
    TREND_BLOCK_MIDLONG_ALLOC,
    VALUATION_EXPENSIVE_PCT,
)
from backend_core.board_metrics.sector_slope_store import SLOPE_SOURCE_EQUAL_WEIGHT


def _env_strong(env: Optional[str]) -> bool:
    return str(env or "") == "strong"


def _env_weak(env: Optional[str]) -> bool:
    return str(env or "") == "weak"


def _slope_nonneg(slope: Optional[float]) -> bool:
    return slope is not None and float(slope) >= 0


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_short_raw(
    *,
    board_kind: str,
    env5: Optional[str],
    slope5: Optional[float],
    env10: Optional[str],
    slope10: Optional[float],
    day_net: Optional[float],
    net_sum_5: Optional[float],
    inflow_streak: Optional[int] = None,
    pos_days_5: Optional[int] = None,
    outflow_streak: Optional[int] = None,
    sentiment_ok: bool = False,
    rotation_dropped: bool = False,
    v2: bool = True,
) -> Tuple[str, Dict[str, Any], List[str]]:
    """返回 (raw, evidence, degraded)。"""
    evidence: Dict[str, Any] = {}
    degraded: List[str] = []

    price_ok = (_env_strong(env5) and _slope_nonneg(slope5)) or (
        _env_strong(env10) and _slope_nonneg(slope10)
    )
    evidence["price_ok"] = price_ok
    evidence["env5"] = env5
    evidence["env10"] = env10

    fund_missing = day_net is None
    evidence["fund_missing"] = fund_missing
    volume_ok = False
    if not fund_missing:
        volume_ok = day_net is not None and day_net > 0 and (
            net_sum_5 is None or net_sum_5 >= 0
        )
        if v2 and volume_ok:
            streak_ok = (inflow_streak or 0) >= 2 or (pos_days_5 or 0) >= 3
            evidence["volume_streak_ok"] = streak_ok
            volume_ok = volume_ok and streak_ok
    evidence["volume_ok"] = volume_ok
    evidence["sentiment_ok"] = bool(sentiment_ok)

    # 回避
    both_weak = _env_weak(env5) and _env_weak(env10)
    fund_avoid = (
        day_net is not None
        and day_net < 0
        and net_sum_5 is not None
        and net_sum_5 < 0
    )
    concept_drop = (
        board_kind == "concept" and rotation_dropped and day_net is not None and day_net < 0
    )
    v2_outflow_avoid = False
    if v2 and (outflow_streak or 0) >= 3 and not price_ok:
        v2_outflow_avoid = True

    if both_weak or fund_avoid or concept_drop or v2_outflow_avoid:
        evidence["avoid_reasons"] = {
            "both_weak": both_weak,
            "fund_avoid": fund_avoid,
            "concept_drop": concept_drop,
            "v2_outflow": v2_outflow_avoid,
        }
        return RAW_AVOID, evidence, degraded

    # 可配：两端证据；缺资金禁止可配
    if fund_missing:
        degraded.append("short_fund_missing")
        return RAW_WATCH, evidence, degraded

    ends = sum(1 for x in (price_ok, volume_ok, sentiment_ok) if x)
    evidence["evidence_ends"] = ends
    if ends >= 2:
        return RAW_ALLOC, evidence, degraded
    return RAW_WATCH, evidence, degraded


def evaluate_midlong_raw(
    *,
    env60: Optional[str],
    slope60: Optional[float],
    env120: Optional[str],
    slope120: Optional[float],
    slope_source_60: Optional[str],
    net_sum_20: Optional[float],
    board_trend_label: Optional[str],
    fund_stage: Optional[str] = None,
    inflow_streak: Optional[int] = None,
    pos_days_20: Optional[int] = None,
    board_rs: Optional[int] = None,
    pe_pct: Optional[float] = None,
    pb_pct: Optional[float] = None,
    valuation_unknown: bool = True,
    v2: bool = True,
) -> Tuple[str, Dict[str, Any], List[str]]:
    evidence: Dict[str, Any] = {}
    degraded: List[str] = []

    # 无有效斜率 → 最高观望
    if slope60 is None and env60 in (None, "unknown"):
        degraded.append("midlong_slope_missing")
        return RAW_WATCH, evidence, degraded

    price_strong_60 = _env_strong(env60)
    # 120：走强或至少非走弱（斜率>=0）；假强(strong_low_r2→neutral)不当走强
    long_ok = _env_strong(env120) or (
        not _env_weak(env120) and _slope_nonneg(slope120)
    )
    # 若无 120 数据，保守：不给可配价条件
    if slope120 is None and env120 in (None, "unknown"):
        long_ok = False
        degraded.append("midlong_slope120_missing")

    evidence["price_strong_60"] = price_strong_60
    evidence["long_ok"] = long_ok
    evidence["env60"] = env60
    evidence["env120"] = env120
    evidence["board_trend_label"] = board_trend_label

    # 回避（v1）
    both_long_weak = _env_weak(env60) and _env_weak(env120)
    weak60_fund = _env_weak(env60) and net_sum_20 is not None and net_sum_20 < 0
    trend_avoid = (board_trend_label or "") in TREND_AVOID_MIDLONG

    # v2 回避
    v2_avoid = False
    if v2 and fund_stage == "decline" and not price_strong_60:
        v2_avoid = True
    rs_for_gate = board_rs
    if v2 and rs_for_gate is not None and rs_for_gate <= BOARD_RS_AVOID_MAX:
        if _env_weak(env60) or fund_stage == "decline":
            v2_avoid = True
            evidence["rs_avoid"] = True
    expensive = False
    if v2 and not valuation_unknown:
        pe = _f(pe_pct)
        pb = _f(pb_pct)
        expensive = (pe is not None and pe >= VALUATION_EXPENSIVE_PCT) or (
            pb is not None and pb >= VALUATION_EXPENSIVE_PCT
        )
        evidence["valuation_expensive"] = expensive
        if expensive and fund_stage == "distribute":
            v2_avoid = True
            evidence["valuation_avoid"] = True

    if both_long_weak or weak60_fund or trend_avoid or v2_avoid:
        evidence["avoid_reasons"] = {
            "both_long_weak": both_long_weak,
            "weak60_fund": weak60_fund,
            "trend_avoid": trend_avoid,
            "v2_avoid": v2_avoid,
        }
        return RAW_AVOID, evidence, degraded

    # 可配价量结构
    trend_block = (board_trend_label or "") in TREND_BLOCK_MIDLONG_ALLOC
    evidence["trend_block"] = trend_block

    fund_ok = net_sum_20 is not None and net_sum_20 >= 0
    if slope_source_60 == SLOPE_SOURCE_EQUAL_WEIGHT:
        fund_ok = net_sum_20 is not None and net_sum_20 > 0
        evidence["equal_weight_stricter"] = True
    evidence["fund_ok"] = fund_ok

    if not (price_strong_60 and long_ok and fund_ok and not trend_block):
        return RAW_WATCH, evidence, degraded

    # v2 加硬
    if v2:
        if not fund_stage:
            degraded.append("midlong_fund_stage_missing")
            return RAW_WATCH, evidence, degraded
        if fund_stage in FUND_STAGES_BLOCK_MIDLONG:
            evidence["fund_stage_block"] = fund_stage
            return RAW_WATCH, evidence, degraded
        fund_persist = (pos_days_20 or 0) >= 8 or (inflow_streak or 0) >= 3
        evidence["fund_persist"] = fund_persist
        if not fund_persist:
            return RAW_WATCH, evidence, degraded

        if rs_for_gate is None:
            degraded.append("midlong_board_rs_missing")
            return RAW_WATCH, evidence, degraded
        evidence["board_rs"] = rs_for_gate
        if rs_for_gate < BOARD_RS_ALLOC_MIN:
            return RAW_WATCH, evidence, degraded

        if not valuation_unknown and expensive:
            if rs_for_gate < BOARD_RS_EXPENSIVE_BYPASS:
                evidence["valuation_cap"] = True
                return RAW_WATCH, evidence, degraded
        # valuation_unknown → 跳过估值层，不阻塞

    return RAW_ALLOC, evidence, degraded
