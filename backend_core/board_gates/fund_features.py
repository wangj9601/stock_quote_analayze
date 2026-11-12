# -*- coding: utf-8 -*-
"""v2.1 板块资金持续度 / fund_stage。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text

from backend_core.board_gates.config import DEFAULT_BOARD_CODE_SOURCE

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_streaks_and_sums(
    nets_asc: Sequence[Optional[float]],
) -> Dict[str, Any]:
    """nets_asc：按日期升序的主力净流入序列（可含 None）。"""
    vals = list(nets_asc)
    day_net = _f(vals[-1]) if vals else None

    inflow_streak = 0
    outflow_streak = 0
    if vals:
        # 从末尾往前数连续正/负
        for v in reversed(vals):
            x = _f(v)
            if x is None:
                break
            if x > 0:
                if outflow_streak > 0:
                    break
                inflow_streak += 1
            elif x < 0:
                if inflow_streak > 0:
                    break
                outflow_streak += 1
            else:
                break

    def _window(n: int) -> Tuple[Optional[float], Optional[int]]:
        if not vals:
            return None, None
        chunk = vals[-n:]
        nums = [_f(x) for x in chunk]
        present = [x for x in nums if x is not None]
        if not present:
            return None, None
        s = sum(present)
        pos = sum(1 for x in present if x > 0)
        return float(s), int(pos)

    net5, pos5 = _window(5)
    net20, pos20 = _window(20)
    return {
        "day_net": day_net,
        "inflow_streak": int(inflow_streak),
        "outflow_streak": int(outflow_streak),
        "pos_days_5": pos5,
        "pos_days_20": pos20,
        "net_sum_5": net5,
        "net_sum_20": net20,
    }


def classify_fund_stage(
    feat: Dict[str, Any],
    *,
    short_strong: bool,
    mid_weak: bool,
) -> str:
    """根据资金特征 + 短/中窗强弱判 fund_stage。"""
    inflow = int(feat.get("inflow_streak") or 0)
    outflow = int(feat.get("outflow_streak") or 0)
    net20 = _f(feat.get("net_sum_20"))

    if outflow >= 3 or (net20 is not None and net20 < 0 and mid_weak):
        return "decline"
    if outflow >= 2 and (short_strong or not mid_weak):
        # 价仍强或平 + 连续流出 → 分流
        return "distribute"
    if inflow >= 2 and short_strong:
        return "markup"
    if inflow >= 3 and (net20 is None or net20 >= 0) and not short_strong:
        return "accumulate"
    return "churn"


def load_fund_net_series(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str,
    trade_date: str,
    lookback: int = 40,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, List[Optional[float]]]:
    """批量加载各板截至 asof 近 lookback 日主力净流入（升序）。"""
    codes = [str(c).strip() for c in board_codes if c]
    out: Dict[str, List[Optional[float]]] = {c: [] for c in codes}
    if not codes:
        return out
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, trade_date, main_net_inflow
                FROM board_fund_flow_daily
                WHERE board_kind = :kind
                  AND board_code_source = :src
                  AND trade_date <= CAST(:td AS date)
                  AND board_code IN :codes
                ORDER BY board_code, trade_date DESC
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {
                "kind": board_kind,
                "src": board_code_source,
                "td": trade_date[:10],
                "codes": codes,
            },
        ).fetchall()
    except Exception as e:
        logger.warning("load_fund_net_series failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return out

    buckets: Dict[str, List[Tuple[str, Optional[float]]]] = {c: [] for c in codes}
    for code, td, net in rows:
        c = str(code or "").strip()
        if c not in buckets:
            continue
        if len(buckets[c]) >= lookback:
            continue
        buckets[c].append((str(td)[:10], _f(net)))

    for c, items in buckets.items():
        items.reverse()  # 升序
        out[c] = [n for _, n in items]
    return out


def build_fund_feature_rows(
    db,
    board_codes: Sequence[str],
    *,
    board_kind: str,
    trade_date: str,
    short_strong_by_code: Optional[Dict[str, bool]] = None,
    mid_weak_by_code: Optional[Dict[str, bool]] = None,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> List[Dict[str, Any]]:
    series = load_fund_net_series(
        db,
        board_codes,
        board_kind=board_kind,
        trade_date=trade_date,
        board_code_source=board_code_source,
    )
    short_map = short_strong_by_code or {}
    mid_map = mid_weak_by_code or {}
    rows: List[Dict[str, Any]] = []
    for code, nets in series.items():
        feat = compute_streaks_and_sums(nets)
        stage = classify_fund_stage(
            feat,
            short_strong=bool(short_map.get(code)),
            mid_weak=bool(mid_map.get(code)),
        )
        rows.append(
            {
                "board_kind": board_kind,
                "board_code_source": board_code_source,
                "board_code": code,
                "trade_date": trade_date[:10],
                "inflow_streak": feat["inflow_streak"],
                "outflow_streak": feat["outflow_streak"],
                "pos_days_5": feat["pos_days_5"],
                "pos_days_20": feat["pos_days_20"],
                "net_sum_5": feat["net_sum_5"],
                "net_sum_20": feat["net_sum_20"],
                "day_net": feat["day_net"],
                "fund_stage": stage,
            }
        )
    return rows
