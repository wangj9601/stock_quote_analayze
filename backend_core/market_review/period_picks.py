# -*- coding: utf-8 -*-
"""周报 / 月报个股：按下周、下月重新筛选，不拼接每日 T+1 名单。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.board_roles.classify import is_limit_up, limit_up_threshold_for_code
from backend_core.market_review.picks import _norm_code, limit_band_for_code
from backend_core.recommend.scoring import role_bonus

DISCLAIMER_WEEK = "规则合成参考，非投资建议。这是下周计划，不是按周五收盘价买入。"
DISCLAIMER_MONTH = "规则合成参考，非投资建议。这是下月计划，不是按月末收盘价买入。"
TRIGGER_WEEK = "下周高开越过本周高点不追，回踩本周低点看是否守住。"
TRIGGER_MONTH = "下月高开越过本月高点不追，回踩本月平台看是否守住。"

NO_CHASE_CAP = {"week": 6, "month": 8}
INDUSTRY_CAP = {"week": 4, "month": 6}
AVOID_CAP = {"week": 12, "month": 16}
SIDELINE_CAP = 2


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def disclaimer_for(kind: str) -> str:
    return DISCLAIMER_MONTH if kind == "month" else DISCLAIMER_WEEK


def trigger_for(kind: str) -> str:
    return TRIGGER_MONTH if kind == "month" else TRIGGER_WEEK


def chase_threshold(kind: str, code: Any) -> float:
    wide = limit_up_threshold_for_code(code) >= 15
    if kind == "month":
        return 45.0 if wide else 30.0
    return 25.0 if wide else 15.0


def period_track_cap(
    kind: str,
    season: Any,
    passed: int,
    total: int,
    volume: Any,
    label: Any,
    has_main: bool,
) -> int:
    """缩量或没有主线时为 0。春/夏且末日门槛过半用较高上限。"""
    if not has_main:
        return 0
    if str(volume or "") == "shrink" or str(label or "") == "缩量调整":
        return 0
    warm = str(season or "") in ("春", "夏") and total > 0 and int(passed) * 2 >= int(total)
    if kind == "month":
        return 10 if warm else 6
    return 8 if warm else 5


def assemble_period_picks(
    *,
    kind: str,
    constituents: Dict[str, Dict[str, Any]],
    stats: Dict[str, Dict[str, Any]],
    zt_rows: Sequence[Dict[str, Any]],
    roles: Dict[str, str],
    daily_track_counts: Dict[str, int],
    season: Any,
    gates_passed: int,
    gates_total: int,
    tape_label: Any,
    tape_volume: Any,
    has_main: bool,
    sideline_rows: Sequence[Dict[str, Any]],
    faded: Sequence[Dict[str, Any]],
    last_avoid: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """纯组栏。成分空则写明主线成分不足，不扫全市场。"""
    horizon = "month" if kind == "month" else "week"
    empty = {
        "disclaimer": disclaimer_for(horizon),
        "note": "主线成分不足",
        "mode": "empty",
        "track_cap": 0,
        "no_chase": [],
        "track": [],
        "sideline": [],
        "avoid": [],
    }
    universe = {_norm_code(c): dict(meta or {}) for c, meta in (constituents or {}).items() if _norm_code(c)}
    if not universe or not has_main:
        return empty

    zt_by: Dict[str, Dict[str, Any]] = {}
    for row in zt_rows or []:
        code = _norm_code(row.get("code"))
        if code:
            zt_by[code] = row

    no_chase_src: List[Dict[str, Any]] = []
    for code, meta in universe.items():
        st = stats.get(code) or {}
        zt = zt_by.get(code)
        last_chg = st.get("last_change")
        if last_chg is None and zt:
            last_chg = zt.get("change_percent")
        period_pct = _f(st.get("period_pct"))
        limit_up = zt is not None or is_limit_up(code, last_chg)
        extended = period_pct is not None and period_pct >= chase_threshold(horizon, code)
        if not limit_up and not extended:
            continue
        brk = int((zt or {}).get("break_count") or 0)
        no_chase_src.append(
            {
                "code": code,
                "name": (zt or {}).get("name") or st.get("name") or meta.get("name") or code,
                "industry": meta.get("industry") or "",
                "stance": "炸板不追" if brk > 0 else "不追",
                "board_count": (zt or {}).get("board_count"),
                "seal_yi": (zt or {}).get("seal_yi"),
                "break_count": brk,
                "limit_band": limit_band_for_code(code),
                "period_pct": None if period_pct is None else round(period_pct, 2),
                "change_percent": _f(last_chg),
                "trigger": trigger_for(horizon),
                "period_high": st.get("period_high"),
                "period_low": st.get("period_low"),
            }
        )
    no_chase_src.sort(
        key=lambda r: (
            -int(r.get("board_count") or 0),
            -float(r.get("seal_yi") or 0),
            -float(r.get("period_pct") or 0),
        )
    )
    cap_chase = NO_CHASE_CAP[horizon]
    no_chase = no_chase_src[:cap_chase]
    blocked = {r["code"] for r in no_chase_src}

    cap = period_track_cap(
        horizon, season, gates_passed, gates_total, tape_volume, tape_label, True
    )
    if cap == 0:
        avoid = _avoid_rows(horizon, universe, stats, faded, last_avoid)
        return {
            "disclaimer": disclaimer_for(horizon),
            "note": "" if avoid else "无新增跟踪",
            "mode": "retreat",
            "track_cap": 0,
            "no_chase": [],
            "track": [],
            "sideline": [],
            "avoid": avoid,
        }

    ranked: List[Dict[str, Any]] = []
    for code, meta in universe.items():
        if code in blocked:
            continue
        st = stats.get(code) or {}
        period_pct = _f(st.get("period_pct"))
        last_close = _f(st.get("last_close"))
        mid = _f(st.get("mid"))
        if period_pct is None or last_close is None or mid is None:
            continue
        if period_pct >= chase_threshold(horizon, code):
            continue
        if last_close < mid:
            continue
        if is_limit_up(code, st.get("last_change")) or code in zt_by:
            continue
        overlap = int(meta.get("overlap_days") or 0)
        daily_n = int((daily_track_counts or {}).get(code) or 0)
        role = (roles or {}).get(code) or ""
        score = overlap * 10.0 + role_bonus(role) + min(daily_n, 5) * 2.0
        ranked.append(
            {
                "code": code,
                "name": st.get("name") or meta.get("name") or code,
                "industry": meta.get("industry") or "",
                "stance": "可跟踪",
                "role": role,
                "score": round(score, 2),
                "overlap_days": overlap,
                "daily_track_days": daily_n,
                "period_pct": round(period_pct, 2),
                "change_percent": _f(st.get("last_change")),
                "trigger": trigger_for(horizon),
                "period_high": st.get("period_high"),
                "period_low": st.get("period_low"),
                "pattern": "无明确形态",
                "macd": "--",
                "rsi": None,
                "kdj": "--",
                "trend": "--",
            }
        )
    ranked.sort(key=lambda r: (-float(r.get("score") or 0), -float(r.get("period_pct") or 0)))
    ind_cap = INDUSTRY_CAP[horizon]
    per_ind: Dict[str, int] = {}
    track: List[Dict[str, Any]] = []
    for row in ranked:
        ind = str(row.get("industry") or "")
        if per_ind.get(ind, 0) >= ind_cap:
            continue
        if len(track) >= cap:
            break
        per_ind[ind] = per_ind.get(ind, 0) + 1
        track.append(row)

    sideline: List[Dict[str, Any]] = []
    seen_side = set()
    for rep in sideline_rows or []:
        if len(sideline) >= SIDELINE_CAP:
            break
        code = _norm_code(rep.get("code"))
        if not code or code in seen_side or code in blocked:
            continue
        pct = _f(rep.get("period_pct"))
        if pct is None or pct <= 0:
            continue
        if is_limit_up(code, rep.get("change_percent")):
            continue
        seen_side.add(code)
        sideline.append(
            {
                "code": code,
                "name": rep.get("name") or code,
                "industry": rep.get("industry") or "",
                "stance": "只观察",
                "period_pct": round(pct, 2),
                "change_percent": _f(rep.get("change_percent")),
            }
        )

    return {
        "disclaimer": disclaimer_for(horizon),
        "note": "",
        "mode": "plan",
        "track_cap": cap,
        "no_chase": no_chase,
        "track": track,
        "sideline": sideline,
        "avoid": [],
    }


def _avoid_rows(
    kind: str,
    universe: Dict[str, Dict[str, Any]],
    stats: Dict[str, Dict[str, Any]],
    faded: Sequence[Dict[str, Any]],
    last_avoid: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []

    def _push(code: str, name: str, reason: str, industry: str = "") -> None:
        code = _norm_code(code)
        if not code or code in seen or not reason:
            return
        seen.add(code)
        st = stats.get(code) or {}
        out.append(
            {
                "code": code,
                "name": name or st.get("name") or universe.get(code, {}).get("name") or code,
                "industry": industry or universe.get(code, {}).get("industry") or "",
                "stance": "回避",
                "reason": reason,
                "period_pct": st.get("period_pct"),
            }
        )

    for row in last_avoid or []:
        _push(row.get("code"), row.get("name") or "", row.get("reason") or "回避", row.get("industry") or "")
    for row in faded or []:
        _push(row.get("code"), row.get("name") or "", row.get("reason") or "由强转弱", row.get("industry") or "")
    out.sort(key=lambda r: (0 if "炸板" in str(r.get("reason")) else 1, str(r.get("code"))))
    return out[: AVOID_CAP["month" if kind == "month" else "week"]]


def apply_period_triggers(picks: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """指标补全后仍用周期触发文案，不留「次日」。"""
    text = trigger_for("month" if kind == "month" else "week")
    for row in picks.get("no_chase") or []:
        if row.get("stance") == "炸板不追":
            row["trigger"] = text
        else:
            row["trigger"] = text
    for row in picks.get("track") or []:
        extra = ""
        if row.get("stance") == "观察" and row.get("downgrade"):
            extra = str(row.get("downgrade") or "")
        row["trigger"] = text if not extra else f"{text}{extra}。"
    return picks
