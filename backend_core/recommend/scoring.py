"""推荐评分、防追高、分散约束。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend_core.recommend.config import (
    ANTI_CHASE_ABOVE_ZONE_PCT,
    ANTI_CHASE_N_DAY_GAIN_PCT,
    FORMULA_VERSION,
    MAX_PER_BOARD_EXECUTABLE,
    MAX_THEME_BOARDS_EXECUTABLE,
    ROLE_BONUS_LEADER,
    ROLE_BONUS_MID,
    SCORE_W_BASE,
    SCORE_W_SR,
    THEME_ALIGN_BONUS,
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
    e_slope: float = 1.0,
    s_sr: float = 0.0,
    theme_align: bool = False,
    e_slope_floor_hit: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    """返回 (总分, 明细)。

    S_base = resonance + quality + action + role (+ theme)
    S_total = max(0, (w_base * S_base + w_sr * S_sr) * E_slope)
    """
    n_strat = len(strategies or [])
    resonance = float(n_strat) * 10.0
    quality = 0.0
    quality_raw = None
    quality_norm = None
    if best_score is not None:
        try:
            quality_norm = float(best_score)
            quality_raw = quality_norm
            quality = min(quality_norm, 100.0) * 0.3
        except (TypeError, ValueError):
            quality = 0.0
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
    if board_weak or e_slope_floor_hit:
        if rb:
            role_zeroed = True
        role_applied = 0.0
        role_note = f"{role_note}（板弱/E地板不加分）"

    theme_bonus = float(THEME_ALIGN_BONUS) if theme_align else 0.0
    theme_note = f"主题对齐 +{THEME_ALIGN_BONUS:g}" if theme_align else "主题对齐 +0"

    s_base = round(resonance + quality + action_bonus + role_applied + theme_bonus, 2)
    try:
        e = float(e_slope)
    except (TypeError, ValueError):
        e = 1.0
    try:
        sr = max(0.0, min(100.0, float(s_sr or 0.0)))
    except (TypeError, ValueError):
        sr = 0.0
    w_base = float(SCORE_W_BASE)
    w_sr = float(SCORE_W_SR)
    blended = w_base * s_base + w_sr * sr
    total = round(max(0.0, blended * e), 2)

    detail = {
        "resonance": round(resonance, 2),
        "resonance_note": f"策略共振 {n_strat}×10",
        "strategies": list(strategies or []),
        "quality": round(quality, 2),
        "quality_raw": quality_raw,
        "quality_norm": quality_norm,
        "quality_note": (
            f"主策略质量 min({quality_norm:g},100)×0.3"
            if quality_norm is not None
            else "主策略质量 无得分×0.3"
        ),
        "action_bonus": round(action_bonus, 2),
        "action_note": action_note,
        "role_bonus": round(role_applied, 2),
        "role_bonus_raw": round(rb, 2),
        "role_note": role_note,
        "role_zeroed_by_board_weak": role_zeroed,
        "theme_bonus": round(theme_bonus, 2),
        "theme_note": theme_note,
        "s_base": s_base,
        "s_sr": round(sr, 2),
        "s_sr_note": f"筹码峰贴合 {sr:g}",
        "e_slope": round(e, 4),
        "e_slope_note": f"环境乘数 E={e:g}",
        "w_base": w_base,
        "w_sr": w_sr,
        "formula_version": FORMULA_VERSION,
        "total": total,
    }
    return total, detail


def apply_anti_chase(
    *,
    action: str,
    quote: Optional[Dict[str, Any]],
    advice: Optional[Dict[str, Any]],
    strategies: Optional[List[str]] = None,
    primary_strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    if action != "buy":
        return action, reasons
    q = quote or {}
    # 涨停当日仍不追
    if q.get("is_limit_up"):
        reasons.append("limit_up")
        return "watch", reasons

    strat_set = {str(s).lower() for s in (strategies or []) if s}
    if primary_strategy:
        strat_set.add(str(primary_strategy).lower())
    # ZHAB 突破确认：豁免 N 日涨幅 / 远离买区（结构突破常伴随短线大涨）
    zhab_breakout_exempt = "zhab" in strat_set and str(signal_type or "").lower() == "breakout"

    try:
        gain = q.get("n_day_gain_pct")
        if (
            not zhab_breakout_exempt
            and gain is not None
            and float(gain) >= float(ANTI_CHASE_N_DAY_GAIN_PCT)
        ):
            reasons.append(f"n_day_gain>={ANTI_CHASE_N_DAY_GAIN_PCT}")
            return "watch", reasons
    except (TypeError, ValueError):
        pass
    if zhab_breakout_exempt:
        return action, reasons
    zone = (advice or {}).get("buy_zone") or {}
    try:
        close = float(q.get("close")) if q.get("close") is not None else None
        anchor = zone.get("high")
        if anchor is None:
            anchor = zone.get("price")
        if close is not None and anchor is not None:
            a = float(anchor)
            if a > 0 and (close - a) / a >= float(ANTI_CHASE_ABOVE_ZONE_PCT):
                reasons.append("far_above_buy_zone")
                return "watch", reasons
    except (TypeError, ValueError):
        pass
    return action, reasons


def action_to_stance(action: str) -> str:
    return {"buy": "买入", "watch": "观察", "avoid": "回避"}.get(action or "", action or "观察")


def apply_diversification(
    items: List[Dict[str, Any]],
    *,
    max_per_board: int = MAX_PER_BOARD_EXECUTABLE,
    max_theme_boards: int = MAX_THEME_BOARDS_EXECUTABLE,
) -> List[Dict[str, Any]]:
    """items 需已按分数降序。优先按 board_code；无代码时按 industry 名称分桶。"""
    board_counts: Dict[str, int] = {}
    theme_boards: set = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        row = dict(it)
        reasons = list(row.get("constraint_reasons") or [])
        if row.get("action") == "buy":
            board = (row.get("board_code") or "").strip()
            if not board:
                board = (row.get("industry") or row.get("board_name") or "").strip() or "_none_"
            cnt = board_counts.get(board, 0)
            if board != "_none_" and cnt >= int(max_per_board):
                row["action"] = "watch"
                row["stance"] = action_to_stance("watch")
                reasons.append("per_board_cap")
            elif board != "_none_" and board not in theme_boards and len(theme_boards) >= int(
                max_theme_boards
            ):
                row["action"] = "watch"
                row["stance"] = action_to_stance("watch")
                reasons.append("theme_board_cap")
            else:
                if board != "_none_":
                    board_counts[board] = cnt + 1
                    theme_boards.add(board)
        row["constraint_reasons"] = reasons
        out.append(row)
    return out
