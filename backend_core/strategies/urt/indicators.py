# -*- coding: utf-8 -*-
"""URT 指标计算：站上 MA、连阳数、中期阳线、多头排列、量能倍数、量比、换手。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def sma(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    window = values[:period]
    if any(v is None for v in window):
        return None
    return sum(float(v) for v in window) / float(period)


def yang_count(opens: List[float], closes: List[float], window: int) -> int:
    """bars 下标 0 为最新日；阳线：close > open。"""
    n = min(window, len(opens), len(closes))
    return sum(1 for i in range(n) if float(closes[i]) > float(opens[i]))


def avg_volume_prev(volumes: List[float], lookback: int) -> Optional[float]:
    """过去 lookback 个交易日均量（不含当日 volumes[0]）。"""
    if lookback <= 0 or len(volumes) < lookback + 1:
        return None
    window = volumes[1 : lookback + 1]
    if not window:
        return None
    return sum(float(v) for v in window) / float(lookback)


def volume_ratio_vs_prev(volumes: List[float]) -> Optional[float]:
    """量比近似：当日量 / 前日量。"""
    if len(volumes) < 2:
        return None
    prev = float(volumes[1] or 0)
    if prev <= 0:
        return None
    return float(volumes[0]) / prev


def default_yang_medium_rules() -> List[Dict[str, int]]:
    return [
        {"window": 10, "min_up_days": 6},
        {"window": 15, "min_up_days": 8},
        {"window": 20, "min_up_days": 10},
    ]


def normalize_yang_medium_rules(cfg: Dict[str, Any]) -> List[Dict[str, int]]:
    raw = cfg.get("yang_medium_rules")
    if not isinstance(raw, list) or not raw:
        return default_yang_medium_rules()
    out: List[Dict[str, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            w = int(item.get("window") or 0)
            m = int(item.get("min_up_days") or item.get("min_yang") or 0)
        except (TypeError, ValueError):
            continue
        if w <= 0:
            continue
        out.append({"window": w, "min_up_days": max(0, m)})
    return out or default_yang_medium_rules()


def normalize_ma_bull_periods(cfg: Dict[str, Any]) -> List[int]:
    raw = cfg.get("ma_bull_periods")
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return [5, 10, 20]
    periods: List[int] = []
    for p in raw:
        try:
            n = int(p)
        except (TypeError, ValueError):
            continue
        if n > 0:
            periods.append(n)
    return periods if len(periods) >= 2 else [5, 10, 20]


def min_bars_needed(cfg: Dict[str, Any]) -> int:
    """计算 URT 指标所需最少 K 线根数（含当日）。"""
    ma_period = int(cfg.get("ma_period") or 20)
    vol_lb = int(cfg.get("volume_lookback") or 20)
    rule_a = cfg.get("yang_rule_a") or {"window": 4, "min_up_days": 3}
    rule_b = cfg.get("yang_rule_b") or {"window": 5, "min_up_days": 4}
    mid_windows = [int(r.get("window", 0)) for r in normalize_yang_medium_rules(cfg)]
    bull_periods = normalize_ma_bull_periods(cfg)
    return max(
        ma_period,
        vol_lb + 1,
        int(rule_a.get("window", 4)),
        int(rule_b.get("window", 5)),
        max(mid_windows) if mid_windows else 20,
        max(bull_periods) if bull_periods else 20,
    )


def build_indicators(bars_desc: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    bars_desc: 日期 DESC，index0=基准日。
    返回指标字典；数据不足返回 None。
    """
    ma_period = int(cfg.get("ma_period") or 20)
    vol_lb = int(cfg.get("volume_lookback") or 20)
    rule_a = cfg.get("yang_rule_a") or {"window": 4, "min_up_days": 3}
    rule_b = cfg.get("yang_rule_b") or {"window": 5, "min_up_days": 4}
    mid_rules = normalize_yang_medium_rules(cfg)
    bull_periods = normalize_ma_bull_periods(cfg)
    need = min_bars_needed(cfg)
    if len(bars_desc) < need:
        return None

    opens = [float(b.get("open") or 0) for b in bars_desc]
    closes = [float(b.get("close") or 0) for b in bars_desc]
    volumes = [float(b.get("volume") or 0) for b in bars_desc]
    turnover = bars_desc[0].get("turnover_rate")

    ma20 = sma(closes, ma_period)
    if ma20 is None or ma20 <= 0:
        return None

    avg_vol = avg_volume_prev(volumes, vol_lb)
    if avg_vol is None or avg_vol <= 0:
        return None

    yang_a = yang_count(opens, closes, int(rule_a.get("window", 4)))
    yang_b = yang_count(opens, closes, int(rule_b.get("window", 5)))
    vol_mult = float(volumes[0]) / float(avg_vol)
    vratio = volume_ratio_vs_prev(volumes)

    # 中期阳线（默认 10/15/20）
    yang_by_window: Dict[int, int] = {}
    mid_oks: List[bool] = []
    for rule in mid_rules:
        w = int(rule["window"])
        cnt = yang_count(opens, closes, w)
        yang_by_window[w] = cnt
        mid_oks.append(cnt >= int(rule["min_up_days"]))
    yang_medium_ok = all(mid_oks) if mid_oks else True

    # 多头排列：默认 MA5 > MA10 > MA20
    ma_values: List[Optional[float]] = [sma(closes, p) for p in bull_periods]
    ma_bull_ok = False
    if all(v is not None and v > 0 for v in ma_values) and len(ma_values) >= 2:
        ma_bull_ok = all(
            float(ma_values[i]) > float(ma_values[i + 1])  # type: ignore[arg-type]
            for i in range(len(ma_values) - 1)
        )

    # 常用三根均线字段（便于展示；与 ma_period 主线并存）
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20_stack = sma(closes, 20)

    out: Dict[str, Any] = {
        "date": bars_desc[0].get("date"),
        "open": opens[0],
        "close": closes[0],
        "volume": volumes[0],
        "ma20": round(ma20, 4),
        "above_ma20": closes[0] >= ma20,
        "yang_count_4": yang_a,
        "yang_count_5": yang_b,
        "yang_count_10": yang_by_window.get(10, yang_count(opens, closes, 10)),
        "yang_count_15": yang_by_window.get(15, yang_count(opens, closes, 15)),
        "yang_count_20": yang_by_window.get(20, yang_count(opens, closes, 20)),
        "yang_medium_ok": yang_medium_ok,
        "yang_medium_detail": [
            {
                "window": int(r["window"]),
                "min_up_days": int(r["min_up_days"]),
                "count": yang_by_window.get(int(r["window"]), 0),
                "ok": yang_by_window.get(int(r["window"]), 0) >= int(r["min_up_days"]),
            }
            for r in mid_rules
        ],
        "ma5": round(ma5, 4) if ma5 is not None else None,
        "ma10": round(ma10, 4) if ma10 is not None else None,
        "ma20_stack": round(ma20_stack, 4) if ma20_stack is not None else None,
        "ma_bull_periods": bull_periods,
        "ma_bull_values": [
            round(float(v), 4) if v is not None else None for v in ma_values
        ],
        "ma_bull_ok": ma_bull_ok,
        "avg_volume_20": round(avg_vol, 2),
        "volume_multiple": round(vol_mult, 4),
        "volume_ratio": round(vratio, 4) if vratio is not None else None,
        "turnover_rate": float(turnover) if turnover is not None else None,
        "rule_a_ok": yang_a >= int(rule_a.get("min_up_days", 3)),
        "rule_b_ok": yang_b >= int(rule_b.get("min_up_days", 4)),
    }
    return out


def hard_filter_pass(ind: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[bool, str]:
    if not ind.get("above_ma20"):
        return False, "未站上MA20"
    if not (ind.get("rule_a_ok") or ind.get("rule_b_ok")):
        return False, "连阳条件不满足"
    need_mult = float(cfg.get("volume_multiple") or 2.5)
    if float(ind.get("volume_multiple") or 0) < need_mult:
        return False, "量能倍数不足"
    if cfg.get("use_turnover"):
        min_to = float(cfg.get("min_turnover") or 0)
        to = ind.get("turnover_rate")
        if to is None or float(to) < min_to:
            return False, "换手率不足"
    if cfg.get("use_volume_ratio"):
        min_vr = float(cfg.get("min_volume_ratio") or 0)
        vr = ind.get("volume_ratio")
        if vr is None or float(vr) < min_vr:
            return False, "量比不足"
    if cfg.get("use_yang_medium"):
        if not ind.get("yang_medium_ok"):
            detail = ind.get("yang_medium_detail") or []
            bits = [
                f"{d.get('window')}日阳{d.get('count')}/{d.get('min_up_days')}"
                for d in detail
                if isinstance(d, dict)
            ]
            suffix = "（" + "，".join(bits) + "）" if bits else ""
            return False, f"中期阳线不足{suffix}"
    if cfg.get("require_ma_bull"):
        if not ind.get("ma_bull_ok"):
            periods = ind.get("ma_bull_periods") or [5, 10, 20]
            label = ">".join(f"MA{p}" for p in periods)
            return False, f"均线未多头排列（需 {label}）"
    return True, "ok"
