"""推荐评分、防追高、分散约束。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend_core.recommend.config import (
    ANTI_CHASE_ABOVE_ZONE_PCT,
    ANTI_CHASE_N_DAY_GAIN_PCT,
    MAX_PER_BOARD_EXECUTABLE,
    MAX_THEME_BOARDS_EXECUTABLE,
    ROLE_BONUS_LEADER,
    ROLE_BONUS_MID,
)


def role_bonus(role: Optional[str]) -> float:
    if role == "leader":
        return float(ROLE_BONUS_LEADER)
    if role == "mid":
        return float(ROLE_BONUS_MID)
    return 0.0


def pick_role_from_tags(role_tags: Any) -> Tuple[Optional[str], Optional[str]]:
    """返回 (role, label)。role in leader|mid|None。"""
    if not isinstance(role_tags, list) or not role_tags:
        return None, None
    for tag in role_tags:
        if not isinstance(tag, dict):
            continue
        role = (tag.get("role") or tag.get("board_role") or "").strip().lower()
        label = tag.get("label") or tag.get("name")
        if role in ("leader", "龙头"):
            return "leader", label or "龙头"
        if role in ("mid", "中军"):
            return "mid", label or "中军"
    for tag in role_tags:
        if not isinstance(tag, dict):
            continue
        label = str(tag.get("label") or "")
        if "龙头" in label:
            return "leader", label
        if "中军" in label:
            return "mid", label
    return None, None


def compute_recommend_score(
    *,
    strategies: List[str],
    best_score: Optional[float],
    advice_action: str,
    role: Optional[str],
    board_weak: bool,
) -> Tuple[float, Dict[str, Any]]:
    """返回 (总分, 明细)。

    明细字段便于前台展示得分构成，避免黑箱。
    """
    n_strat = len(strategies or [])
    resonance = float(n_strat) * 10.0
    quality = 0.0
    quality_raw = None
    if best_score is not None:
        try:
            quality_raw = float(best_score)
            quality = min(quality_raw, 100.0) * 0.3
        except (TypeError, ValueError):
            quality = 0.0
            quality_raw = None
    if advice_action == "buy":
        action_bonus = 15.0
        action_note = "立场买入 +15"
    elif advice_action == "watch":
        action_bonus = 5.0
        action_note = "立场观察 +5"
    else:
        action_bonus = 0.0
        action_note = "立场回避 +0"
    rb = role_bonus(role)
    role_note = {
        "leader": f"龙头 +{ROLE_BONUS_LEADER:g}",
        "mid": f"中军 +{ROLE_BONUS_MID:g}",
    }.get(role or "", "普通 +0")
    role_applied = rb
    role_zeroed = False
    if board_weak:
        if rb:
            role_zeroed = True
        role_applied = 0.0
        role_note = f"{role_note}（板弱不加分）"

    total = round(resonance + quality + action_bonus + role_applied, 2)
    detail = {
        "resonance": round(resonance, 2),
        "resonance_note": f"策略共振 {n_strat}×10",
        "strategies": list(strategies or []),
        "quality": round(quality, 2),
        "quality_raw": quality_raw,
        "quality_note": (
            f"主策略质量 min({quality_raw:g},100)×0.3"
            if quality_raw is not None
            else "主策略质量 无得分×0.3"
        ),
        "action_bonus": round(action_bonus, 2),
        "action_note": action_note,
        "role_bonus": round(role_applied, 2),
        "role_bonus_raw": round(rb, 2),
        "role_note": role_note,
        "role_zeroed_by_board_weak": role_zeroed,
        "total": total,
    }
    return total, detail


def apply_anti_chase(
    *,
    action: str,
    quote: Optional[Dict[str, Any]],
    advice: Optional[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """涨停或显著远离买区 → 降为观察。返回 (action, reasons)。"""
    reasons: List[str] = []
    if action != "buy":
        return action, reasons
    q = quote or {}
    if q.get("is_limit_up"):
        reasons.append("limit_up")
        return "watch", reasons
    n_gain = q.get("n_day_gain_pct")
    try:
        if n_gain is not None and float(n_gain) >= float(ANTI_CHASE_N_DAY_GAIN_PCT):
            reasons.append(f"n_day_gain>={ANTI_CHASE_N_DAY_GAIN_PCT}")
            return "watch", reasons
    except (TypeError, ValueError):
        pass

    close = q.get("close")
    buy_zone = (advice or {}).get("buy_zone") if isinstance(advice, dict) else None
    if close is not None and isinstance(buy_zone, dict):
        try:
            c = float(close)
            high = buy_zone.get("high")
            price = buy_zone.get("price")
            anchor = high if high is not None else price
            if anchor is not None:
                a = float(anchor)
                if a > 0 and (c - a) / a >= float(ANTI_CHASE_ABOVE_ZONE_PCT):
                    reasons.append("far_above_buy_zone")
                    return "watch", reasons
        except (TypeError, ValueError):
            pass
    return action, reasons


def apply_diversification(
    items: List[Dict[str, Any]],
    *,
    max_per_board: int = MAX_PER_BOARD_EXECUTABLE,
    max_theme_boards: int = MAX_THEME_BOARDS_EXECUTABLE,
) -> List[Dict[str, Any]]:
    """对 action=buy 的可执行候选施加分散上限；超出降为 watch。

    items 需已按分数降序。优先按 board_code；无代码时按 industry 名称分桶。
    """
    board_counts: Dict[str, int] = {}
    theme_boards: set = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        action = it.get("action")
        board = (it.get("board_code") or "").strip()
        if not board:
            board = (it.get("industry") or it.get("board_name") or "").strip() or "_none_"
        if action == "buy":
            demote = False
            if board != "_none_":
                if board_counts.get(board, 0) >= max_per_board:
                    demote = True
                    it = dict(it)
                    it["action"] = "watch"
                    it["stance"] = "观察"
                    reasons = list(it.get("constraint_reasons") or [])
                    reasons.append("per_board_cap")
                    it["constraint_reasons"] = reasons
                elif board not in theme_boards and len(theme_boards) >= max_theme_boards:
                    demote = True
                    it = dict(it)
                    it["action"] = "watch"
                    it["stance"] = "观察"
                    reasons = list(it.get("constraint_reasons") or [])
                    reasons.append("theme_board_cap")
                    it["constraint_reasons"] = reasons
            if not demote and board != "_none_":
                board_counts[board] = board_counts.get(board, 0) + 1
                theme_boards.add(board)
        out.append(it)
    return out


def action_to_stance(action: str) -> str:
    if action == "buy":
        return "买入"
    if action == "avoid":
        return "回避"
    return "观察"
