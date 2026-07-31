# -*- coding: utf-8 -*-
"""URT 买点检测；卖点规则对象化供回测扩展。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .indicators import build_indicators, hard_filter_pass
from .scoring import compute_score_breakdown


def history_calendar_days_for_fetch(cfg: Dict[str, Any]) -> int:
    """
    拉历史 K 线用日历跨度：至少覆盖策略 history_calendar_days，
    并保证足以支撑 KDE 最大回看（交易日 ×1.6 近似换算）。
    """
    hist = int(cfg.get("history_calendar_days") or 120)
    kde_max = int(cfg.get("kde_lookback_max") or 750)
    kde_cal = int(kde_max * 1.6) + 40
    return max(hist, kde_cal)


def _compute_structure_levels(
    bars_desc: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    *,
    price: Optional[float],
) -> Dict[str, Any]:
    """
    成交量加权 KDE 支撑/阻力（与 RPE / 个股关键价位同口径）。
    bars_desc 为日期 DESC（最新在前）；内部转为升序喂给 KDE。
    """
    empty = {
        "support_levels": [],
        "resistance_levels": [],
        "nearest_support": None,
        "nearest_resistance": None,
        "kde_ok": False,
        "kde_reason": "insufficient_samples",
        "kde_bw": None,
        "kde_lookback_used": 0,
        "kde_lookback_expanded": False,
    }
    if not bars_desc or price is None:
        return empty
    try:
        px = float(price)
    except (TypeError, ValueError):
        return empty
    if px <= 0:
        return empty

    # DESC → ASC
    asc = list(reversed(bars_desc))
    closes: List[float] = []
    volumes: List[float] = []
    for b in asc:
        try:
            c = float(b.get("close") or 0)
            v = float(b.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        if c > 0:
            closes.append(c)
            volumes.append(v if v > 0 else 0.0)
    if len(closes) < 20:
        return empty

    from backend_core.strategies.rpe.kde_levels import (
        extract_kde_levels_expand_support,
        nearest_levels,
    )

    init_lb = int(cfg.get("kde_lookback_days") or cfg.get("kde_lookback_initial") or 250)
    step = int(cfg.get("kde_lookback_step") or 250)
    max_lb = int(cfg.get("kde_lookback_max") or 750)
    base = float(cfg.get("kde_base_factor") or 1.0)
    grid = int(cfg.get("kde_grid_points") or 200)

    kde = extract_kde_levels_expand_support(
        closes,
        volumes,
        price=px,
        initial_lookback=init_lb,
        step=step,
        max_lookback=max_lb,
        base_factor=base,
        grid_points=grid,
    )
    supports = [round(float(x), 2) for x in (kde.get("support_levels") or [])[:8]]
    resists = [round(float(x), 2) for x in (kde.get("resistance_levels") or [])[:8]]
    near = nearest_levels(px, supports, resists)
    ns = near.get("nearest_support")
    nr = near.get("nearest_resistance")
    return {
        "support_levels": supports,
        "resistance_levels": resists,
        "nearest_support": round(float(ns), 2) if ns is not None else None,
        "nearest_resistance": round(float(nr), 2) if nr is not None else None,
        "kde_ok": bool(kde.get("ok")),
        "kde_reason": kde.get("reason") or ("ok" if kde.get("ok") else "no_peaks"),
        "kde_bw": kde.get("bw"),
        "kde_lookback_used": int(kde.get("lookback_used") or 0),
        "kde_lookback_expanded": bool(kde.get("lookback_expanded")),
    }


def build_buy_logic(detail: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    结构化买点判断逻辑（供信号明细页展示）。
    买点 = 硬筛全部通过 AND 得分 ≥ min_score。
    """
    rule_a = cfg.get("yang_rule_a") or {}
    rule_b = cfg.get("yang_rule_b") or {}
    ma_period = int(cfg.get("ma_period") or 20)
    vol_need = float(cfg.get("volume_multiple") or 2.5)
    min_score = float(cfg.get("min_score") or 70)
    use_turnover = bool(cfg.get("use_turnover"))
    use_volume_ratio = bool(cfg.get("use_volume_ratio"))
    min_turn = float(cfg.get("min_turnover") or 0) if use_turnover else None
    min_vr = float(cfg.get("min_volume_ratio") or 0) if use_volume_ratio else None
    a_w = int(rule_a.get("window") or 4)
    a_n = int(rule_a.get("min_up_days") or rule_a.get("min_yang") or 3)
    b_w = int(rule_b.get("window") or 5)
    b_n = int(rule_b.get("min_up_days") or rule_b.get("min_yang") or 4)

    close = detail.get("close")
    ma20 = detail.get("ma20")
    if detail.get("above_ma20") is not None:
        above = bool(detail.get("above_ma20"))
    elif close is not None and ma20 is not None:
        try:
            above = float(close) >= float(ma20)
        except (TypeError, ValueError):
            above = False
    else:
        above = False
    ya = int(detail.get("yang_count_4") or 0)
    yb = int(detail.get("yang_count_5") or 0)
    rule_a_ok = bool(detail.get("rule_a_ok")) if detail.get("rule_a_ok") is not None else (ya >= a_n)
    rule_b_ok = bool(detail.get("rule_b_ok")) if detail.get("rule_b_ok") is not None else (yb >= b_n)
    yang_ok = rule_a_ok or rule_b_ok
    vm = detail.get("volume_multiple")
    try:
        vm_f = float(vm) if vm is not None else None
    except (TypeError, ValueError):
        vm_f = None
    volume_ok = vm_f is not None and vm_f >= vol_need
    turnover = detail.get("turnover_rate")
    volume_ratio = detail.get("volume_ratio")
    turnover_ok = True
    if use_turnover:
        try:
            turnover_ok = turnover is not None and float(turnover) >= float(min_turn)
        except (TypeError, ValueError):
            turnover_ok = False
    vr_ok = True
    if use_volume_ratio:
        try:
            vr_ok = volume_ratio is not None and float(volume_ratio) >= float(min_vr)
        except (TypeError, ValueError):
            vr_ok = False

    filter_ok = detail.get("filter_ok")
    if filter_ok is None:
        filter_ok = bool(above and yang_ok and volume_ok and turnover_ok and vr_ok)
    else:
        filter_ok = bool(filter_ok)
    score = float(detail.get("score") or 0)
    score_ok = bool(detail.get("score_ok")) if detail.get("score_ok") is not None else (score >= min_score)
    buy = bool(detail.get("buy_signal")) if detail.get("buy_signal") is not None else (filter_ok and score_ok)

    steps = [
        {
            "id": "above_ma",
            "name": f"站上MA{ma_period}",
            "rule": f"收盘价 ≥ MA{ma_period}",
            "actual": (
                f"收盘={close}，MA{ma_period}={ma20}"
                if close is not None and ma20 is not None
                else "—"
            ),
            "pass": above,
            "required": True,
        },
        {
            "id": "yang",
            "name": "连阳确认",
            "rule": f"{a_w}日≥{a_n}阳 或 {b_w}日≥{b_n}阳",
            "actual": f"{a_w}日阳线={ya}，{b_w}日阳线={yb}",
            "pass": yang_ok,
            "required": True,
            "detail": {
                "rule_a": f"{a_w}日≥{a_n}阳 → {'通过' if rule_a_ok else '未通过'}",
                "rule_b": f"{b_w}日≥{b_n}阳 → {'通过' if rule_b_ok else '未通过'}",
            },
        },
        {
            "id": "volume_multiple",
            "name": "放量确认",
            "rule": f"当日量 / MA{ma_period}均量 ≥ {vol_need}",
            "actual": f"量比倍数={vm_f if vm_f is not None else '—'}",
            "pass": volume_ok,
            "required": True,
        },
    ]
    if use_turnover:
        steps.append(
            {
                "id": "turnover",
                "name": "换手率下限",
                "rule": f"换手率 ≥ {min_turn}%",
                "actual": f"换手率={turnover if turnover is not None else '—'}",
                "pass": turnover_ok,
                "required": True,
            }
        )
    if use_volume_ratio:
        steps.append(
            {
                "id": "volume_ratio",
                "name": "量比下限",
                "rule": f"量比 ≥ {min_vr}",
                "actual": f"量比={volume_ratio if volume_ratio is not None else '—'}",
                "pass": vr_ok,
                "required": True,
            }
        )
    steps.append(
        {
            "id": "min_score",
            "name": "最低得分门槛",
            "rule": f"综合得分 ≥ {min_score}",
            "actual": f"得分={score}",
            "pass": score_ok,
            "required": True,
            "note": "须在硬筛全部通过后再判定",
        }
    )

    return {
        "formula": "买点 = 硬筛全部通过 AND 得分≥最低得分",
        "formula_detail": (
            f"硬筛：站上MA{ma_period} ∧ 连阳({a_w}≥{a_n}∨{b_w}≥{b_n}) ∧ 放量≥{vol_need}"
            + (f" ∧ 换手≥{min_turn}" if use_turnover else "")
            + (f" ∧ 量比≥{min_vr}" if use_volume_ratio else "")
            + f"；再要求得分≥{min_score}"
        ),
        "min_score": min_score,
        "score": score,
        "filter_ok": filter_ok,
        "score_ok": score_ok,
        "buy_signal": buy,
        "filter_reason": detail.get("filter_reason") or "",
        "steps": steps,
    }


def evaluate_buy_signal(
    bars_desc: list,
    cfg: Dict[str, Any],
    *,
    require_pass: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    对截至最新日的 DESC K 线判定 URT 买点。
    require_pass=True：仅硬筛+得分通过才返回；False：始终返回指标与得分明细（供明细页）。
    同时计算成交量加权 KDE 支撑/阻力（展示用，不参与硬筛）。
    """
    ind = build_indicators(bars_desc, cfg)
    if not ind:
        return None
    ok, reason = hard_filter_pass(ind, cfg)
    score, score_detail = compute_score_breakdown(ind, cfg)
    min_score = float(cfg.get("min_score") or 70)
    score_ok = score >= min_score
    buy = bool(ok and score_ok)

    if require_pass and not buy:
        return None

    yang_rule = "4d3" if ind.get("rule_a_ok") else "5d4"
    if ind.get("rule_a_ok") and ind.get("rule_b_ok"):
        yang_rule = "4d3+5d4"
    elif not ind.get("rule_a_ok") and not ind.get("rule_b_ok"):
        yang_rule = "none"

    structure = _compute_structure_levels(bars_desc, cfg, price=ind.get("close"))
    # 持久化进 score_detail，预计算重读无需改表
    if isinstance(score_detail, dict):
        score_detail = dict(score_detail)
        score_detail["structure"] = {
            "support_levels": structure["support_levels"],
            "resistance_levels": structure["resistance_levels"],
            "nearest_support": structure["nearest_support"],
            "nearest_resistance": structure["nearest_resistance"],
            "kde_ok": structure["kde_ok"],
            "kde_reason": structure["kde_reason"],
            "kde_bw": structure["kde_bw"],
            "kde_lookback_used": structure["kde_lookback_used"],
            "kde_lookback_expanded": structure["kde_lookback_expanded"],
            "method": "kde_volume_weighted",
        }

    payload = {
        "signal_date": ind.get("date"),
        "close": ind.get("close"),
        "open": ind.get("open"),
        "ma20": ind.get("ma20"),
        "above_ma20": ind.get("above_ma20"),
        "yang_count_4": ind.get("yang_count_4"),
        "yang_count_5": ind.get("yang_count_5"),
        "yang_rule": yang_rule,
        "rule_a_ok": ind.get("rule_a_ok"),
        "rule_b_ok": ind.get("rule_b_ok"),
        "avg_volume_20": ind.get("avg_volume_20"),
        "volume": ind.get("volume"),
        "volume_multiple": ind.get("volume_multiple"),
        "volume_ratio": ind.get("volume_ratio"),
        "turnover_rate": ind.get("turnover_rate"),
        "score": score,
        "signal_strength": score,
        "score_detail": score_detail,
        "buy_signal": buy,
        "filter_ok": ok,
        "filter_reason": reason,
        "score_ok": score_ok,
        "support_levels": structure["support_levels"],
        "resistance_levels": structure["resistance_levels"],
        "nearest_support": structure["nearest_support"],
        "nearest_resistance": structure["nearest_resistance"],
        "kde_ok": structure["kde_ok"],
        "kde_reason": structure["kde_reason"],
        "kde_lookback_used": structure["kde_lookback_used"],
        "kde_lookback_expanded": structure["kde_lookback_expanded"],
    }
    payload["buy_logic"] = build_buy_logic(payload, cfg)
    return payload


def evaluate_exit_rules(
    *,
    entry_price: float,
    closes: list,
    peak_price: float,
    cfg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    卖出纪律（供回测）：
    - 价格止损：亏损达 stop_loss_pct
    - 时间止损：连续下跌 N 日
    - 回撤止盈：涨幅达警惕区后，自高点回撤 trailing_drawdown_pct
    closes: 持仓以来收盘价序列（时间正序，含最新）。
    """
    risk = cfg.get("risk") or {}
    if entry_price <= 0 or not closes:
        return None
    last = float(closes[-1])
    pnl_pct = (last - entry_price) / entry_price * 100.0

    stop_max = float(risk.get("stop_loss_pct_max") or 10)
    if pnl_pct <= -stop_max:
        return {"exit_reason": "price_stop", "pnl_pct": round(pnl_pct, 2)}

    down_days = int(risk.get("time_stop_down_days") or 3)
    if len(closes) >= down_days + 1:
        streak = 0
        for i in range(len(closes) - 1, 0, -1):
            if float(closes[i]) < float(closes[i - 1]):
                streak += 1
            else:
                break
        if streak >= down_days:
            return {"exit_reason": "time_stop", "pnl_pct": round(pnl_pct, 2), "down_days": streak}

    alert_min = float(risk.get("take_profit_alert_pct_min") or 25)
    trail = float(risk.get("trailing_drawdown_pct") or 5)
    peak = max(float(peak_price), max(float(c) for c in closes))
    gain_from_entry = (peak - entry_price) / entry_price * 100.0
    if gain_from_entry >= alert_min and peak > 0:
        dd = (peak - last) / peak * 100.0
        if dd >= trail:
            return {
                "exit_reason": "trailing_take_profit",
                "pnl_pct": round(pnl_pct, 2),
                "peak_drawdown_pct": round(dd, 2),
            }
    return None
