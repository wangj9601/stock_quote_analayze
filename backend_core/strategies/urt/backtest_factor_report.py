# -*- coding: utf-8 -*-
"""URT 回测：因子分扁平化、分项分桶、同信号集 hit_rate 对照。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# 导出列：分项得分
PART_SCORE_FIELDS: List[Tuple[str, str, str]] = [
    ("above_ma20", "f_above_ma20", "MA20趋势分"),
    ("yang", "f_yang", "连阳分"),
    ("yang_quality", "f_yang_quality", "阳线质量分"),
    ("volume", "f_volume", "量能分"),
    ("yang_medium", "f_yang_medium", "中期阳线分"),
    ("ma_bull", "f_ma_bull", "均线多头分"),
    ("turnover", "f_turnover", "换手分"),
    ("volume_ratio", "f_volume_ratio", "量比分"),
    ("structure_position", "f_structure_position", "结构位分"),
    ("overheat_penalty", "f_overheat_penalty", "过热扣分"),
]

# 导出列：原始量，便于分层而不是只看合成分
RAW_HEADER_ZH: Dict[str, str] = {
    "volume_multiple": "量能倍数",
    "yang_count_5": "5日连阳",
    "structure_rr": "结构盈亏比",
    "dist_to_support_pct": "距支撑(%)",
    "proximity_reason": "贴近支撑原因",
    "turnover_rate": "换手率(%)",
    "turnover_relative": "换手相对中位",
    "ma_bull_depth": "均线多头深度",
    "overheat_intensity": "过热强度",
    "ret_from_low_n": "近低点涨幅",
    "horizon_pnl_pct": "满观察期盈亏(%)",
    "horizon_exit_price": "满观察期收盘",
}

FACTOR_HEADER_ZH: Dict[str, str] = {
    **{col: zh for _part, col, zh in PART_SCORE_FIELDS},
    **RAW_HEADER_ZH,
}


def _f(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _round(v: Optional[float], n: int = 4) -> Optional[float]:
    if v is None:
        return None
    return round(v, n)


def _part(parts: Dict[str, Any], key: str) -> Dict[str, Any]:
    raw = parts.get(key)
    return raw if isinstance(raw, dict) else {}


def flatten_score_factors(sig: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从买点 score_detail.parts 抽出逐笔因子分与原始量。"""
    out: Dict[str, Any] = {}
    sig = sig if isinstance(sig, dict) else {}
    sd = sig.get("score_detail")
    if not isinstance(sd, dict):
        sd = {}
    parts = sd.get("parts") if isinstance(sd.get("parts"), dict) else {}
    inputs = sd.get("inputs") if isinstance(sd.get("inputs"), dict) else {}

    for part_key, col, _zh in PART_SCORE_FIELDS:
        out[col] = _round(_f(_part(parts, part_key).get("score")), 2)

    vol = _part(parts, "volume")
    yang = _part(parts, "yang")
    st = _part(parts, "structure_position")
    to = _part(parts, "turnover")
    oh = _part(parts, "overheat_penalty")
    bull = _part(parts, "ma_bull")

    out["volume_multiple"] = _round(_f(vol.get("volume_multiple") or sig.get("volume_multiple")), 4)
    out["yang_count_5"] = yang.get("yang_count_5")
    if out["yang_count_5"] is None:
        out["yang_count_5"] = sig.get("yang_count_5")

    rr = st.get("structure_rr")
    if rr is None:
        rr = sig.get("structure_rr")
    out["structure_rr"] = _round(_f(rr), 4)

    close = _f(st.get("close") or inputs.get("close") or sig.get("close"))
    support = _f(st.get("nearest_support") or sig.get("nearest_support"))
    dist = None
    if close is not None and close > 0 and support is not None:
        dist = (close - support) / close * 100.0
    out["dist_to_support_pct"] = _round(dist, 2)
    out["proximity_reason"] = st.get("proximity_reason") or ""

    out["turnover_rate"] = _round(_f(to.get("turnover_rate") or inputs.get("turnover_rate")), 4)
    out["turnover_relative"] = _round(_f(to.get("relative")), 4)

    depth = bull.get("depth")
    try:
        out["ma_bull_depth"] = int(depth) if depth is not None else None
    except (TypeError, ValueError):
        out["ma_bull_depth"] = depth

    out["overheat_intensity"] = _round(_f(oh.get("intensity")), 4)
    ret = oh.get("ret_from_low_n")
    if ret is None:
        ret = inputs.get("ret_from_low_n")
    out["ret_from_low_n"] = _round(_f(ret), 4)
    return out


def attach_horizon_metrics(
    row: Dict[str, Any],
    future: Sequence[Dict[str, Any]],
    entry_price: float,
) -> Dict[str, Any]:
    """同一观察窗：若持有到末日收盘的对照盈亏（与实际出场无关）。"""
    if not future or not entry_price:
        return row
    last = future[-1]
    close = last.get("close")
    if close is None:
        close = last.get("open")
    try:
        px = float(close) if close is not None else None
    except (TypeError, ValueError):
        px = None
    if px is None or px <= 0:
        return row
    row["horizon_exit_price"] = round(px, 4)
    row["horizon_pnl_pct"] = round((px / float(entry_price) - 1.0) * 100.0, 2)
    return row


def enrich_detail_with_factors(
    row: Dict[str, Any],
    sig: Optional[Dict[str, Any]],
    future: Sequence[Dict[str, Any]],
    entry_price: float,
) -> Dict[str, Any]:
    row.update(flatten_score_factors(sig))
    attach_horizon_metrics(row, future, entry_price)
    return row


def _metrics_for_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    if not n:
        return {
            "total": 0,
            "hit": 0,
            "hit_rate": 0.0,
            "win_count": 0,
            "win_rate": 0.0,
            "avg_pnl_pct": 0.0,
            "avg_max_gain_pct": 0.0,
            "avg_horizon_pnl_pct": None,
        }
    hits = sum(1 for r in rows if r.get("hit_target"))
    wins = sum(1 for r in rows if _f(r.get("pnl_pct")) is not None and float(r.get("pnl_pct")) > 0)
    avg_pnl = sum(_f(r.get("pnl_pct")) or 0.0 for r in rows) / n
    avg_gain = sum(_f(r.get("max_gain_pct")) or 0.0 for r in rows) / n
    hz_vals = [_f(r.get("horizon_pnl_pct")) for r in rows]
    hz_ok = [v for v in hz_vals if v is not None]
    return {
        "total": n,
        "hit": hits,
        "hit_rate": round(hits / n, 4),
        "win_count": wins,
        "win_rate": round(wins / n, 4),
        "avg_pnl_pct": round(avg_pnl, 2),
        "avg_max_gain_pct": round(avg_gain, 2),
        "avg_horizon_pnl_pct": round(sum(hz_ok) / len(hz_ok), 2) if hz_ok else None,
    }


def assign_score_buckets(details: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """总分分桶，附带命中率/胜率/均盈亏/均最大涨幅。"""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in details:
        sv = _f(r.get("score"))
        if sv is None:
            bucket = "未知"
        elif sv < 60:
            bucket = "[0,60)"
        elif sv < 70:
            bucket = "[60,70)"
        elif sv < 80:
            bucket = "[70,80)"
        elif sv < 90:
            bucket = "[80,90)"
        else:
            bucket = "[90,100]"
        grouped.setdefault(bucket, []).append(r)
    return {name: _metrics_for_rows(rows) for name, rows in grouped.items()}


def _bin_value(v: Optional[float], edges: Sequence[Tuple[Optional[float], Optional[float], str]]) -> Optional[str]:
    if v is None:
        return None
    for lo, hi, label in edges:
        if lo is not None and v < lo:
            continue
        if hi is not None and v >= hi:
            continue
        return label
    return None


# (字段, 中文名, 分箱)
_FACTOR_BIN_SPECS: List[Tuple[str, str, List[Tuple[Optional[float], Optional[float], str]]]] = [
    ("volume_multiple", "量能倍数", [(None, 3.5, "<3.5"), (3.5, 5.0, "[3.5,5)"), (5.0, None, "≥5")]),
    ("f_volume", "量能分", [(None, 12.0, "<12"), (12.0, 18.0, "[12,18)"), (18.0, None, "≥18")]),
    ("f_yang", "连阳分", [(None, 10.0, "<10"), (10.0, 14.0, "[10,14)"), (14.0, None, "≥14")]),
    ("f_yang_quality", "阳线质量分", [(None, 5.0, "<5"), (5.0, 8.0, "[5,8)"), (8.0, None, "≥8")]),
    ("f_structure_position", "结构位分", [(None, 8.0, "<8"), (8.0, 14.0, "[8,14)"), (14.0, None, "≥14")]),
    ("structure_rr", "结构盈亏比", [(None, 1.5, "<1.5"), (1.5, 2.5, "[1.5,2.5)"), (2.5, None, "≥2.5")]),
    ("dist_to_support_pct", "距支撑(%)", [(None, 2.0001, "≤2%"), (2.0001, 5.0001, "(2%,5%]"), (5.0001, None, ">5%")]),
    ("f_turnover", "换手分", [(None, 0.0, "<0"), (0.0, 5.0, "[0,5)"), (5.0, None, "≥5")]),
    ("f_ma_bull", "均线多头分", [(None, 4.0, "<4"), (4.0, 7.0, "[4,7)"), (7.0, None, "≥7")]),
    ("f_overheat_penalty", "过热扣分", [(None, -6.0, "<-6"), (-6.0, 0.0, "[-6,0)"), (0.0, None, "0")]),
]


def build_factor_buckets(details: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """按因子分箱统计命中率与盈亏，用于优化信号因子。"""
    out: Dict[str, Any] = {}
    for field, label, edges in _FACTOR_BIN_SPECS:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        missing = 0
        for r in details:
            name = _bin_value(_f(r.get(field)), edges)
            if name is None:
                missing += 1
                continue
            grouped.setdefault(name, []).append(r)
        if not grouped:
            continue
        bins = []
        for edge in edges:
            name = edge[2]
            rows = grouped.get(name) or []
            if not rows:
                continue
            m = _metrics_for_rows(rows)
            m["bucket"] = name
            bins.append(m)
        out[field] = {
            "label": label,
            "field": field,
            "missing": missing,
            "bins": bins,
        }
    return out


def build_hit_rate_compare(details: Sequence[Dict[str, Any]], exit_mode: str) -> Dict[str, Any]:
    """同批信号：路径命中/最大涨幅 vs 实际出场 vs 持有满观察期。"""
    n = len(details)
    hits = sum(1 for r in details if r.get("hit_target"))
    avg_gain = sum(_f(r.get("max_gain_pct")) or 0.0 for r in details) / n if n else 0.0
    actual_pnl = sum(_f(r.get("pnl_pct")) or 0.0 for r in details) / n if n else 0.0
    actual_wins = sum(1 for r in details if (_f(r.get("pnl_pct")) or 0) > 0)
    actual_bars = sum(int(r.get("bars_held") or 0) for r in details) / n if n else 0.0

    hz = [_f(r.get("horizon_pnl_pct")) for r in details]
    hz_ok = [v for v in hz if v is not None]
    hz_pnl = sum(hz_ok) / len(hz_ok) if hz_ok else None
    hz_wins = sum(1 for v in hz_ok if v > 0)
    hz_win_rate = round(hz_wins / len(hz_ok), 4) if hz_ok else None

    note = (
        "同一批成交信号对照：命中率与均最大涨幅按观察期内最高价统计，与出场无关；"
        "「满观察期」盈亏按末日收盘、不触发止损/止盈。"
        "去重窗口若按实际出场日缩短，独立再跑 hit_rate 任务的信号集可能不同。"
    )
    return {
        "sample": "same_trades",
        "note": note,
        "exit_mode": exit_mode,
        "total": n,
        "hit_count": hits,
        "hit_rate": round(hits / n, 4) if n else 0.0,
        "avg_max_gain_pct": round(avg_gain, 2) if n else 0.0,
        "actual": {
            "win_count": actual_wins,
            "win_rate": round(actual_wins / n, 4) if n else 0.0,
            "avg_pnl_pct": round(actual_pnl, 2) if n else 0.0,
            "avg_bars_held": round(actual_bars, 2) if n else 0.0,
        },
        "horizon_hold": {
            "win_count": hz_wins if hz_ok else 0,
            "win_rate": hz_win_rate,
            "avg_pnl_pct": round(hz_pnl, 2) if hz_pnl is not None else None,
            "coverage": len(hz_ok),
        },
        "max_gain_vs_actual_pnl_gap": round(avg_gain - actual_pnl, 2) if n else 0.0,
        "horizon_vs_actual_pnl_gap": (
            round(hz_pnl - actual_pnl, 2) if hz_pnl is not None and n else None
        ),
    }
