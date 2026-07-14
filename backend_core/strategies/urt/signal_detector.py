# -*- coding: utf-8 -*-
"""URT 买点检测；卖点规则对象化供回测扩展。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .indicators import build_indicators, hard_filter_pass
from .scoring import compute_score_breakdown


def evaluate_buy_signal(
    bars_desc: list,
    cfg: Dict[str, Any],
    *,
    require_pass: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    对截至最新日的 DESC K 线判定 URT 买点。
    require_pass=True：仅硬筛+得分通过才返回；False：始终返回指标与得分明细（供明细页）。
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

    return {
        "signal_date": ind.get("date"),
        "close": ind.get("close"),
        "open": ind.get("open"),
        "ma20": ind.get("ma20"),
        "above_ma20": ind.get("above_ma20"),
        "yang_count_4": ind.get("yang_count_4"),
        "yang_count_5": ind.get("yang_count_5"),
        "yang_rule": yang_rule,
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
    }


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
