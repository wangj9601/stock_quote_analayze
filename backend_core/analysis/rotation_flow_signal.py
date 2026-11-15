"""资金流 × 相对轮动的交叉信号。

资金气泡回答"今天的钱往哪走"，相对轮动回答"相对强弱处在哪个阶段"，单看各有盲区：
领先象限但主力持续流出，往往是平滑指标滞后于真实资金；落后象限却有资金回流，才是左侧候选。

这里只做纯计算，不碰数据库：入参是气泡的 direction 与 RRG 的 quadrant。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

QUADRANT_LABELS: Dict[str, str] = {
    "leading": "领先",
    "weakening": "转弱",
    "lagging": "落后",
    "improving": "改善",
    "neutral": "中性",
}

# (象限, 资金方向) -> (信号键, 信号名, 强弱档, 一句话解释)
_SIGNALS: Dict[tuple, tuple] = {
    ("leading", "in"): (
        "main_uptrend",
        "主升确认",
        "strong",
        "领先象限仍在吸金，主线尚未松动",
    ),
    ("leading", "out"): (
        "reversal_alert",
        "兑现预警",
        "risk",
        "还在领先象限但主力已撤，平滑指标滞后于资金",
    ),
    ("weakening", "in"): (
        "weak_inflow",
        "转弱承接",
        "watch",
        "动量已掉头，仍有资金逆势承接",
    ),
    ("weakening", "out"): (
        "ebb_exit",
        "退潮离场",
        "risk",
        "动量与资金同向流出，优先减仓",
    ),
    ("lagging", "in"): (
        "left_ambush",
        "左侧潜伏",
        "watch",
        "仍落后但资金开始回流，等轨迹拐向改善",
    ),
    ("lagging", "out"): (
        "bleeding",
        "持续失血",
        "risk",
        "强弱与资金双弱，不抄底",
    ),
    ("improving", "in"): (
        "improve_bid",
        "改善承接",
        "strong",
        "轮动位置在修复且资金进场，左侧最优组合",
    ),
    ("improving", "out"): (
        "improve_hollow",
        "改善虚火",
        "watch",
        "位置在修复但资金没跟，等回抽确认",
    ),
    ("neutral", "in"): (
        "neutral_probe",
        "中性试盘",
        "watch",
        "贴着中轴，资金小幅流入",
    ),
    ("neutral", "out"): (
        "neutral_drift",
        "中性偏弱",
        "watch",
        "贴着中轴，资金小幅流出",
    ),
}

UNCOVERED_SIGNAL = {
    "signal_key": "uncovered",
    "signal_label": "未覆盖",
    "signal_level": "unknown",
    "signal_note": "该板块没有相对轮动数据",
}


def quadrant_label(quadrant: Optional[str]) -> Optional[str]:
    return QUADRANT_LABELS.get(str(quadrant or ""))


def classify_flow_rotation(
    quadrant: Optional[str],
    direction: Optional[str],
) -> Dict[str, str]:
    """象限 + 资金方向 -> 交叉信号。任一缺失都归到未覆盖，不猜。"""
    key = (str(quadrant or "").strip(), str(direction or "").strip())
    if key[0] not in QUADRANT_LABELS or key[1] not in ("in", "out"):
        return dict(UNCOVERED_SIGNAL)
    signal_key, label, level, note = _SIGNALS[key]
    return {
        "signal_key": signal_key,
        "signal_label": label,
        "signal_level": level,
        "signal_note": note,
    }


def _brief(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "board_code": item.get("board_code"),
        "board_name": item.get("board_name"),
        "main_net_yi": item.get("main_net_yi"),
        "change_percent": item.get("change_percent"),
        "rotation_quadrant": item.get("rotation_quadrant"),
        "rotation_label": item.get("rotation_label"),
        "signal_key": item.get("signal_key"),
        "signal_label": item.get("signal_label"),
    }


def summarize_flow_rotation(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """按象限计数，并抽出最该看的兑现预警与改善承接名单。"""
    rows: List[Dict[str, Any]] = [dict(item) for item in items]
    counts = {key: 0 for key in QUADRANT_LABELS}
    uncovered = 0
    alerts: List[Dict[str, Any]] = []
    supports: List[Dict[str, Any]] = []
    for row in rows:
        quadrant = str(row.get("rotation_quadrant") or "")
        direction = str(row.get("direction") or "")
        if quadrant in counts:
            counts[quadrant] += 1
        else:
            uncovered += 1
        level = str(row.get("signal_level") or "")
        if level == "risk" and direction == "out":
            alerts.append(_brief(row))
        elif level == "strong":
            supports.append(_brief(row))
    alerts.sort(key=lambda item: float(item.get("main_net_yi") or 0))
    supports.sort(key=lambda item: float(item.get("main_net_yi") or 0), reverse=True)
    return {
        "covered": sum(counts.values()),
        "uncovered": uncovered,
        "quadrant_counts": counts,
        "alerts": alerts[:6],
        "supports": supports[:6],
    }
