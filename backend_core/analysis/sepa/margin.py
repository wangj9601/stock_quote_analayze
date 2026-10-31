# -*- coding: utf-8 -*-
"""两融旁证：用杠杆资金行为给 SEPA 入场点加一层独立确认。

口径：数据表 stock_margin_daily（rzye 融资余额、rzmre 融资买入、rzche 融资偿还、
float_mv 流通市值），单位需一致；crowd = rzye / float_mv。非两融标的返回中性分，
既不奖励也不惩罚——避免把大量中小盘直接筛掉。

状态机：crowded(高位拥挤) -> clearing(出清中) -> steady(企稳) -> reflow(回流确认)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from backend_core.analysis.sepa.bars import _f
from backend_core.analysis.sepa.config import MARGIN_STATUS_LABELS, MarginConfig


def _sorted_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = [r for r in rows or [] if isinstance(r, dict)]
    out.sort(key=lambda r: str(r.get("trade_date") or r.get("date") or "")[:10])
    return out


def _consecutive_positive(values: Sequence[float]) -> int:
    n = 0
    for v in reversed(list(values)):
        if v is not None and v > 0:
            n += 1
        else:
            break
    return n


def assess_margin(
    margin_rows: Sequence[Dict[str, Any]],
    *,
    circ_mv: Optional[float] = None,
    cfg: Optional[MarginConfig] = None,
) -> Dict[str, Any]:
    """返回 {ok, status, status_label, score, drawdown_pct, reflow_pct, ...}。"""
    c = cfg or MarginConfig()
    rows = _sorted_rows(margin_rows)[-int(c.lookback):]
    rzye = [x for x in (_f(r.get("rzye")) for r in rows) if x is not None]
    if len(rzye) < 5:
        return {
            "ok": False,
            "status": "no_data",
            "status_label": MARGIN_STATUS_LABELS["no_data"],
            "score": float(c.neutral_score),
            "drawdown_pct": None,
            "reflow_pct": None,
            "net_buy_sum": None,
            "pos_days": 0,
            "crowd_pct": None,
            "notes": ["margin_data_insufficient"],
        }

    last = float(rzye[-1])
    peak = float(np.max(rzye))
    drawdown = last / peak - 1.0 if peak > 0 else float("nan")

    k = min(int(c.reflow_days), len(rzye) - 1)
    reflow = last / float(rzye[-1 - k]) - 1.0 if k > 0 and rzye[-1 - k] > 0 else float("nan")

    nets: List[float] = []
    for r in rows:
        rz_mre, rz_che = _f(r.get("rzmre")), _f(r.get("rzche"))
        if rz_mre is None and rz_che is None:
            continue
        nets.append((rz_mre or 0.0) - (rz_che or 0.0))
    recent = nets[-int(c.net_buy_days):] if nets else []
    net_sum = float(sum(recent)) if recent else float("nan")
    streak = _consecutive_positive(nets)

    mv = _f(circ_mv)
    if mv is None:
        for r in reversed(rows):
            mv = _f(r.get("float_mv")) or _f(r.get("circ_mv"))
            if mv:
                break
    crowd = last / mv if mv and mv > 0 else float("nan")

    notes: List[str] = []
    if np.isfinite(crowd) and crowd > c.crowd_max:
        status = "crowded"
        notes.append("crowding_over_limit")
    elif np.isfinite(reflow) and reflow > c.min_reflow_pct and streak >= 2:
        status = "reflow"
        notes.append("net_buy_streak")
    elif np.isfinite(drawdown) and drawdown <= -c.clear_drawdown:
        status = "steady" if (np.isfinite(reflow) and reflow > -0.01) else "clearing"
        notes.append("balance_washout")
    else:
        status = "steady" if (np.isfinite(reflow) and reflow > 0) else "clearing"

    score = _score(status, drawdown, reflow, streak, crowd, c)
    return {
        "ok": status in ("reflow", "steady"),
        "status": status,
        "status_label": MARGIN_STATUS_LABELS.get(status, status),
        "score": score,
        "drawdown_pct": round(drawdown * 100, 2) if np.isfinite(drawdown) else None,
        "reflow_pct": round(reflow * 100, 2) if np.isfinite(reflow) else None,
        "net_buy_sum": round(net_sum, 0) if np.isfinite(net_sum) else None,
        "pos_days": int(sum(1 for x in recent if x > 0)),
        "streak_days": int(streak),
        "crowd_pct": round(crowd * 100, 2) if np.isfinite(crowd) else None,
        "notes": notes,
    }


def _score(status: str, drawdown: float, reflow: float, streak: int,
           crowd: float, cfg: MarginConfig) -> float:
    """0~100：状态给基准分，出清越充分、回流越强加分；高位拥挤扣分。"""
    if status == "no_data":
        return float(cfg.neutral_score)
    base = {"reflow": 70.0, "steady": 55.0, "clearing": 40.0, "crowded": 15.0}.get(status, 40.0)
    add = 0.0
    if np.isfinite(drawdown) and drawdown < 0:
        add += min(15.0, (-drawdown / max(cfg.clear_drawdown, 1e-6)) * 15.0)
    if np.isfinite(reflow) and reflow > 0:
        add += min(10.0, reflow / 0.05 * 10.0)
    add += min(5.0, streak * 2.5)
    if np.isfinite(crowd) and crowd > cfg.crowd_max:
        add -= 10.0
    return round(float(min(100.0, max(0.0, base + add))), 1)
