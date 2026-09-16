# -*- coding: utf-8 -*-
"""每日复盘：规则引擎（硬门槛、情绪周期、叙述槽位）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


HARD_GATES = [
    {
        "id": 1,
        "name": "市场总成交量",
        "standard": "≥ 2万亿",
        "key": "vol_trillion",
        "min": 2.0,
    },
    {
        "id": 2,
        "name": "连板家数",
        "standard": "≥ 13家",
        "key": "cb_count",
        "min": 13,
    },
    {
        "id": 3,
        "name": "市场高度",
        "standard": "≥ 6板",
        "key": "height",
        "min": 6,
    },
    {
        "id": 4,
        "name": "十日最低涨幅连续上升",
        "standard": "近3日连续上升",
        "key": "lo_rising_3d",
        "min": True,
    },
    {
        "id": 5,
        "name": "十日最高涨幅稳定",
        "standard": "近3日稳定 ≥ 95",
        "key": "hi_stable_95",
        "min": True,
    },
]


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def evaluate_hard_gates(
    today: Dict[str, Any],
    hist: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """hist 为含今日在内、按日期升序的近若干日指标行。"""
    lo_rising = False
    hi_stable = False
    if len(hist) >= 3:
        last3 = hist[-3:]
        los = [_f(r.get("lo_value")) for r in last3]
        his = [_f(r.get("hi_value")) for r in last3]
        if all(x is not None for x in los):
            lo_rising = los[0] < los[1] < los[2]
        if all(x is not None for x in his):
            hi_stable = all(x >= 95 for x in his)

    values = {
        "vol_trillion": _f(today.get("vol_trillion")),
        "cb_count": today.get("cb_count"),
        "height": today.get("height"),
        "lo_rising_3d": lo_rising,
        "hi_stable_95": hi_stable,
    }
    items = []
    passed = 0
    for g in HARD_GATES:
        key = g["key"]
        val = values.get(key)
        ok = False
        note = ""
        if key in ("lo_rising_3d", "hi_stable_95"):
            ok = bool(val)
            note = "达标" if ok else "不达标"
        else:
            try:
                ok = val is not None and float(val) >= float(g["min"])
            except (TypeError, ValueError):
                ok = False
            note = "达标" if ok else "不达标"
        if ok:
            passed += 1
        items.append(
            {
                "id": g["id"],
                "name": g["name"],
                "standard": g["standard"],
                "value": val,
                "passed": ok,
                "note": note,
            }
        )
    return {
        "items": items,
        "passed": passed,
        "total": len(items),
        "rate": f"{passed}/{len(items)}",
    }


def classify_season(
    cb: Optional[int],
    height: Optional[int],
    prev_cb_return: Optional[float],
) -> Dict[str, Any]:
    """优先匹配最冷季节。"""
    cb_i = int(cb) if cb is not None else None
    h_i = int(height) if height is not None else None
    ret = _f(prev_cb_return)

    checks = {
        "冬": {
            "cb": cb_i is not None and cb_i < 10,
            "height": h_i is not None and h_i < 4,
            "prev_cb_return": ret is not None and ret < 0,
        },
        "秋": {
            "cb": cb_i is not None and cb_i < 13,
            "height": h_i is not None and h_i < 6,
            "prev_cb_return": ret is not None and ret < 1,
        },
        "春": {
            "cb": cb_i is not None and cb_i < 18,
            "height": h_i is not None and h_i < 7,
            "prev_cb_return": ret is not None and ret > 3,
        },
    }

    season = "夏"
    for name in ("冬", "秋", "春"):
        flags = checks[name]
        if all(flags.values()):
            season = name
            break
        if name == "秋" and flags["cb"] and flags["height"]:
            # 参考文：连板+高度满足秋区即可判秋（溢价可分歧）
            season = "秋"
            break
        if name == "冬" and flags["cb"]:
            # 部分满足冬线，仍可能最终判秋；先记录
            pass

    # 若未全满足冬但秋匹配，保持秋；全满足冬则冬
    if all(checks["冬"].values()):
        season = "冬"
    elif checks["秋"]["cb"] and checks["秋"]["height"]:
        season = "秋"
    elif all(checks["春"].values()):
        season = "春"
    else:
        season = "夏"

    return {
        "season": season,
        "checks": checks,
        "cb": cb_i,
        "height": h_i,
        "prev_cb_return": ret,
    }


def dual_curve_quadrant(lo: Optional[float], hi: Optional[float]) -> str:
    lo_v = _f(lo)
    hi_v = _f(hi)
    if lo_v is None or hi_v is None:
        return "未知"
    low_lo = lo_v < 35
    low_hi = hi_v < 100
    if low_lo and low_hi:
        return "冬/冰点"
    if low_lo and not low_hi:
        return "低位修复"
    if (not low_lo) and low_hi:
        return "高位降温"
    return "夏/活跃"


def build_trend_rules(
    today: Dict[str, Any],
    yesterday: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    y = yesterday or {}
    signals = []
    cb = today.get("cb_count")
    y_cb = y.get("cb_count")
    vol = _f(today.get("vol_trillion"))
    y_vol = _f(y.get("vol_trillion"))
    hi = _f(today.get("hi_value"))
    y_hi = _f(y.get("hi_value"))
    lo = _f(today.get("lo_value"))
    y_lo = _f(y.get("lo_value"))
    h = today.get("height")
    y_h = y.get("height")
    sp = _f(today.get("sp_value"))

    if y_cb is not None and cb is not None and cb < 10 <= y_cb:
        signals.append("连板重回冬线")
    if vol is not None and (y_vol is None or vol <= y_vol):
        signals.append("量能继续萎缩或持平")
    if hi is not None and y_hi is not None and (hi - y_hi) <= -20:
        signals.append("Hi暴跌")
    if lo is not None and y_lo is not None and lo < y_lo:
        signals.append("Lo续跌")

    isolated_height = False
    if (
        h is not None
        and y_h is not None
        and h > y_h
        and cb is not None
        and y_cb is not None
        and cb < y_cb
        and vol is not None
        and y_vol is not None
        and vol < y_vol
    ):
        isolated_height = True
        signals.append("假高度（高度升+连板降+量能缩）")

    delta = {
        "height": {"from": y_h, "to": h},
        "cb_count": {"from": y_cb, "to": cb},
        "lo_value": {"from": y_lo, "to": lo},
        "hi_value": {"from": y_hi, "to": hi},
        "vol_trillion": {"from": y_vol, "to": vol},
        "sp_value": {"from": _f(y.get("sp_value")), "to": sp},
        "prev_cb_return": {
            "from": _f(y.get("prev_cb_return")),
            "to": _f(today.get("prev_cb_return")),
        },
    }

    if len(signals) >= 3:
        summary = "缩量回暖夭折或退潮二次探底：多项情绪指标同步恶化。"
    elif isolated_height:
        summary = "出现孤高隐患，广度与量能未跟上高度。"
    elif not signals:
        summary = "核心指标相对平稳，等待量能与连板确认。"
    else:
        summary = "情绪指标部分走弱，需观察能否止跌。"

    return {
        "signals": signals,
        "isolated_height": isolated_height,
        "delta": delta,
        "summary": summary,
        "sp_eve": sp is not None and sp < 50,
        "quadrant": dual_curve_quadrant(lo, hi),
    }


def draft_viewpoint(today: Dict[str, Any], rules: Dict[str, Any], season: Dict[str, Any]) -> str:
    vol = today.get("vol_trillion")
    cb = today.get("cb_count")
    h = today.get("height")
    season_name = season.get("season") or "--"
    signals = rules.get("signals") or []
    sig_txt = "、".join(signals) if signals else "暂无明确恶化信号"
    return (
        f"今日量能约 {vol if vol is not None else '--'} 万亿，连板 {cb} 家，高度 {h} 板；"
        f"情绪周期判定为「{season_name}」。盘面要点：{sig_txt}。"
        f"明日需确认能否止跌（允许低开高走或急跌后放量回拉）；若继续缩量阴跌则保持观望。"
    )


def draft_advice(gates: Dict[str, Any], season: Dict[str, Any], rules: Dict[str, Any]) -> str:
    passed = gates.get("passed") or 0
    total = gates.get("total") or 5
    season_name = season.get("season") or "--"
    lines = [
        f"根据今日盘面，硬门槛达标 {passed}/{total}，情绪周期为「{season_name}」。",
        "1. 观察早盘强度：重点看是否低开高走或急跌后放量拉升。",
        "2. 量能确认：入场需看到成交额有效放大。",
        "3. 方向选择：以同花顺概念主线为准，行业仅作赛道确认；新面孔需看 1–2 日持续性再跟随。",
    ]
    if passed == 0 or season_name in ("冬", "秋"):
        lines.append("4. 风险控制：门槛偏弱，优先空仓或极轻仓，拒绝盲目低吸。")
    else:
        lines.append("4. 风险控制：若连板与量能再度走弱，及时止损降仓。")
    if rules.get("sp_eve"):
        lines.append("附：Spread 跌破 50，处于变盘前夜区，注意弹性与假突破风险。")
    return "\n".join(lines)
