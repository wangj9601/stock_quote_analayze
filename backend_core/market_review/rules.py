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


# 较昨日增加达到该金额（亿元）才记为放量；介于其间视为平量。
VOLUME_EXPAND_YI = 1500.0
VOLUME_EXPAND_TRILLION = VOLUME_EXPAND_YI / 10000.0
BREADTH_RATIO = 1.5
PERCENTILE_MIN_SAMPLE = 20


def _fmt2(v: Any, digits: int = 2) -> str:
    f = _f(v)
    if f is None:
        return "--"
    return f"{f:.{digits}f}"


def yuan_to_yi(v: Any) -> Optional[float]:
    f = _f(v)
    if f is None:
        return None
    return f / 1e8


def classify_tape_regime(
    today: Dict[str, Any],
    yesterday: Optional[Dict[str, Any]] = None,
    breadth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """盘面状态：放量/缩量/平量 × 普涨/普跌/分歧。"""
    y = yesterday or {}
    vol = _f(today.get("vol_trillion"))
    y_vol = _f(y.get("vol_trillion"))
    delta_tri = None
    delta_yi = None
    volume = "unknown"
    if vol is not None and y_vol is not None:
        delta_tri = vol - y_vol
        delta_yi = delta_tri * 10000.0
        if delta_tri >= VOLUME_EXPAND_TRILLION:
            volume = "expand"
        elif vol < y_vol:
            volume = "shrink"
        else:
            volume = "flat"

    up = down = None
    if breadth:
        try:
            up = int(breadth["up_count"]) if breadth.get("up_count") is not None else None
        except (TypeError, ValueError):
            up = None
        try:
            down = int(breadth["down_count"]) if breadth.get("down_count") is not None else None
        except (TypeError, ValueError):
            down = None
    breadth_tag = "unknown"
    if up is not None and down is not None:
        if up > down and up >= down * BREADTH_RATIO:
            breadth_tag = "broad_up"
        elif down > up and down >= up * BREADTH_RATIO:
            breadth_tag = "broad_down"
        else:
            breadth_tag = "mixed"

    if volume == "expand" and breadth_tag == "broad_up":
        label = "放量普涨"
    elif volume == "expand" and breadth_tag == "broad_down":
        label = "放量普跌"
    elif volume == "expand":
        label = "放量震荡"
    elif volume == "shrink":
        label = "缩量调整"
    else:
        label = "平量观察"

    return {
        "label": label,
        "volume": volume,
        "breadth": breadth_tag,
        "vol_trillion": vol,
        "y_vol_trillion": y_vol,
        "vol_delta_yi": None if delta_yi is None else round(delta_yi, 1),
        "up_count": up,
        "down_count": down,
    }


def _pct_zone(pct: Optional[float]) -> str:
    if pct is None:
        return "--"
    if pct >= 80:
        return "高位"
    if pct <= 20:
        return "低位"
    return "中位"


def curve_position_note(
    sample_n: int,
    lo_pct: Optional[float],
    hi_pct: Optional[float],
    sp_pct: Optional[float],
) -> Dict[str, str]:
    """样本不足或 Lo 绝对阈值未校准时，不用冰点四象限。"""
    if sample_n < PERCENTILE_MIN_SAMPLE:
        return {
            "lo": "阈值未校准",
            "hi": "阈值未校准",
            "sp": "阈值未校准",
            "summary": "阈值未校准",
            "percentile_note": "样本不足",
        }
    lo_z, hi_z, sp_z = _pct_zone(lo_pct), _pct_zone(hi_pct), _pct_zone(sp_pct)
    return {
        "lo": lo_z,
        "hi": hi_z,
        "sp": sp_z,
        "summary": f"Lo{lo_z} / Hi{hi_z} / Sp{sp_z}",
        "percentile_note": "",
    }


def build_sentiment(
    today: Dict[str, Any],
    yesterday: Optional[Dict[str, Any]],
    tape: Dict[str, Any],
    market_env: Optional[Dict[str, Any]],
    sector: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """三条可核对事实 + 三条次日观察，不写参与建议。"""
    env = market_env or {}
    sec = sector or {}
    y = yesterday or {}
    facts: List[str] = []
    delta = tape.get("vol_delta_yi")
    if delta is None:
        delta = env.get("vol_delta_yi")
    volume = tape.get("volume")
    if volume == "expand" and delta is not None:
        facts.append(f"量能较昨日放大 {float(delta):.0f} 亿")
    elif volume == "shrink" and delta is not None:
        facts.append(f"量能较昨日萎缩 {abs(float(delta)):.0f} 亿")
    elif delta is not None:
        facts.append(f"量能较昨日变化 {float(delta):+.0f} 亿")
    else:
        facts.append("量能缺少昨日对比")

    zt = today.get("limit_up_count")
    yzt = y.get("limit_up_count")
    ld = (env.get("breadth") or {}).get("limit_down_count")
    if zt is not None:
        bit = f"涨停 {zt} 家"
        if yzt is not None:
            bit += f"（昨日 {yzt}）"
        if ld is not None:
            bit += f"，跌停 {ld} 家"
        facts.append(bit)
    else:
        facts.append("涨停家数缺失")

    main = sec.get("main") or {}
    mname = main.get("board_name")
    yi = main.get("net_inflow_yi")
    if mname:
        flow = f"，净流入 {_fmt2(yi, 1)} 亿" if yi is not None else ""
        facts.append(f"当日主线 {mname}{flow}")
    else:
        facts.append("当日主线不明确")

    watch: List[str] = []
    if mname:
        watch.append(f"观察主线「{mname}」次日涨跌幅与净流入是否仍为正")
    else:
        watch.append("观察是否出现净流入为正的行业主线")
    ret = today.get("prev_cb_return")
    if ret is not None:
        watch.append(f"观察昨日高标溢价（今日昨连板收益 {_fmt2(ret)}%）")
    else:
        watch.append("观察昨日高标溢价")
    gap = env.get("sh_gap_to_high20")
    if gap is not None:
        watch.append(f"上证距近20日高点还差约 {float(gap):.0f} 点")
    else:
        watch.append("上证距近20日高点：指数数据不足")
    return {"facts": facts[:3], "watch": watch[:3]}


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

    neg_signals: List[str] = []
    if y_cb is not None and cb is not None and cb < 10 <= y_cb:
        neg_signals.append("连板重回冬线")
    volume_tag = "unknown"
    if vol is not None and y_vol is not None:
        if (vol - y_vol) >= VOLUME_EXPAND_TRILLION:
            volume_tag = "expand"
            signals.append("量能放大")
        elif vol < y_vol:
            volume_tag = "shrink"
            neg_signals.append("量能继续萎缩或持平")
        else:
            volume_tag = "flat"
    if hi is not None and y_hi is not None and (hi - y_hi) <= -20:
        neg_signals.append("Hi暴跌")
    if lo is not None and y_lo is not None and lo < y_lo:
        neg_signals.append("Lo续跌")

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
        neg_signals.append("假高度（高度升+连板降+量能缩）")

    signals.extend(neg_signals)

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

    vol_change_small = volume_tag == "flat"
    if len(neg_signals) >= 3:
        summary = "缩量回暖夭折或退潮二次探底：多项情绪指标同步恶化。"
    elif isolated_height:
        summary = "出现孤高隐患，广度与量能未跟上高度。"
    elif volume_tag == "expand":
        delta_yi = (vol - y_vol) * 10000.0
        summary = (
            f"成交额较昨日增加约 {delta_yi:.0f} 亿。"
            "放量是否有效，看上涨家数是否明显多于下跌家数。"
        )
    elif vol_change_small and not neg_signals:
        summary = "核心指标相对平稳，等待量能与连板确认。"
    elif not neg_signals:
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


def draft_viewpoint(
    today: Dict[str, Any],
    rules: Dict[str, Any],
    season: Dict[str, Any],
    tape: Optional[Dict[str, Any]] = None,
    market_env: Optional[Dict[str, Any]] = None,
    sector: Optional[Dict[str, Any]] = None,
) -> str:
    env = market_env or {}
    if tape is None:
        tape = classify_tape_regime(today, None, env.get("breadth"))
    label = tape.get("label") or "平量观察"
    season_name = season.get("season") or "--"
    vol = _fmt2(today.get("vol_trillion"))
    delta = tape.get("vol_delta_yi")
    if delta is None:
        delta = env.get("vol_delta_yi")
    vol_bit = f"今日量能 {vol} 万亿"
    if delta is not None and tape.get("volume") == "expand":
        vol_bit += f"，较昨日放量 {float(delta):.0f} 亿"
    elif delta is not None and tape.get("volume") == "shrink":
        vol_bit += f"，较昨日缩量 {abs(float(delta)):.0f} 亿"
    elif delta is not None:
        vol_bit += f"，较昨日变化 {float(delta):+.0f} 亿"
    if env.get("above_2t"):
        vol_bit += "，站上 2 万亿"

    br = env.get("breadth") or {}
    parts = [vol_bit]
    if br.get("up_count") is not None and br.get("down_count") is not None:
        parts.append(f"上涨 {br['up_count']} 家、下跌 {br['down_count']} 家")
    zt = today.get("limit_up_count")
    ld = br.get("limit_down_count")
    if zt is not None:
        zt_bit = f"涨停 {zt}"
        if ld is not None:
            zt_bit += f"、跌停 {ld}"
        parts.append(zt_bit)

    main = (sector or {}).get("main") or {}
    mname = main.get("board_name")
    if mname:
        yi = main.get("net_inflow_yi")
        main_bit = f"当日主线：{mname}"
        if yi is not None:
            main_bit += f"（净流入 {_fmt2(yi, 1)} 亿）"
        parts.append(main_bit)
    else:
        parts.append("当日主线不明确")

    tails = {
        "放量普涨": "次日观察主线能否延续、高标溢价，以及上证距近20日高点的距离。",
        "放量普跌": "量能放大但下跌家数占优，先看广度能否修复，不预判反转。",
        "放量震荡": "量能放大但涨跌分歧，先观察、不预判方向。",
        "缩量调整": "若继续缩量阴跌则保持观望。",
        "平量观察": "量能与涨跌接近，先观察、不预判方向。",
    }
    eco = ""
    if label == "放量普涨" and season_name in ("秋", "冬"):
        eco = "连板生态仍偏冷，但指数与广度已改善。"
    cb = today.get("cb_count")
    h = today.get("height")
    body = "。".join(parts)
    return (
        f"{body}。连板 {cb} 家，高度 {h} 板，情绪周期「{season_name}」，"
        f"盘面状态「{label}」。{eco}{tails.get(label, tails['平量观察'])}"
    )


def draft_advice(
    gates: Dict[str, Any],
    season: Dict[str, Any],
    rules: Dict[str, Any],
    tape: Optional[Dict[str, Any]] = None,
    sentiment: Optional[Dict[str, Any]] = None,
) -> str:
    passed = gates.get("passed") or 0
    total = gates.get("total") or 5
    season_name = season.get("season") or "--"
    label = (tape or {}).get("label") or ""
    if not label:
        sigs = rules.get("signals") or []
        if any("量能放大" in str(s) for s in sigs):
            label = "放量震荡"
        elif any("萎缩" in str(s) for s in sigs):
            label = "缩量调整"
        else:
            label = "平量观察"
    lines = [
        f"根据今日盘面，硬门槛达标 {passed}/{total}，情绪周期为「{season_name}」，盘面状态为「{label}」。",
    ]
    if label == "放量普涨":
        if passed < total or season_name in ("冬", "秋"):
            lines.append("连板生态仍偏冷，但指数与广度已改善。")
        watch = (sentiment or {}).get("watch") or []
        if watch:
            for i, w in enumerate(watch, 1):
                lines.append(f"{i}. {w}")
        else:
            lines.append("1. 次日看主线涨跌幅与净流入是否仍为正。")
            lines.append("2. 观察昨日高标溢价。")
            lines.append("3. 看上证距近20日高点的距离。")
        lines.append("方向仍以同花顺概念为准，行业只作赛道确认。")
    elif label == "缩量调整":
        lines.append("1. 缩量环境下不接跌，等待放量确认。")
        lines.append("2. 方向仍以同花顺概念为准，行业只作赛道确认。")
        lines.append("3. 风险控制：若继续缩量阴跌则保持观望，优先空仓或极轻仓。")
    elif label == "放量普跌":
        lines.append("1. 放量但广度偏弱，先看下跌家数是否收敛。")
        lines.append("2. 不预判反转，主线未明确前不扩散方向。")
    else:
        lines.append("1. 先观察量能与涨跌家数，不预判方向。")
        lines.append("2. 方向仍以同花顺概念为准，行业只作赛道确认。")
    if rules.get("sp_eve"):
        lines.append("附：Spread 跌破 50，处于变盘前夜区，注意弹性与假突破风险。")
    return "\n".join(lines)
