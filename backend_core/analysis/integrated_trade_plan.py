# -*- coding: utf-8 -*-
"""个股分析 · 综合交易策略合成（短线 + 中长线）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend_core.analysis.trade_advice import build_trade_advice

_STRATEGY_PRIORITY = ("urt", "gms", "sbbr", "rpe")
_ACTION_LABELS = {
    "buy": "买入/承接",
    "watch": "观察",
    "avoid": "回避",
    "sell": "减仓/离场",
}
_STANCE_MEDIUM_MAP = {
    "uptrend": ("bull", "偏多"),
    "downtrend": ("bear", "偏空"),
    "transition": ("neutral", "转换观察"),
    "range": ("neutral", "震荡"),
    "insufficient": ("neutral", "样本不足"),
}
_GANN_BIAS_MAP = {
    "bull": ("bull", "江恩偏多"),
    "bear": ("bear", "江恩偏空"),
    "near": ("neutral", "江恩临界"),
    "neutral": ("neutral", "江恩中性"),
}


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_px(v: Any) -> str:
    x = _f(v)
    return f"{x:.2f}" if x is not None else "--"


def _resolve_close_from_levels(levels: Optional[Dict[str, Any]]) -> Optional[float]:
    """从 levels 快照解析现价（兼容 current_price / realtime_price / last_close）。"""
    if not levels or not isinstance(levels, dict):
        return None
    for key in ("current_price", "realtime_price", "last_close", "close"):
        v = _f(levels.get(key))
        if v is not None and v > 0:
            return v
    classic = levels.get("classic_levels") or levels.get("classic") or {}
    if isinstance(classic, dict):
        for key in ("last_close", "anchor_price"):
            v = _f(classic.get(key))
            if v is not None and v > 0:
                return v
    return None


def _best_support_level(levels: Optional[Dict[str, Any]]) -> Optional[float]:
    if not levels or not isinstance(levels, dict):
        return None
    classic = levels.get("classic_levels") or levels.get("classic") or {}
    conf = classic.get("confluence_zones") if isinstance(classic, dict) else {}
    if not conf:
        conf = levels.get("confluence_zones") or {}
    if isinstance(conf, dict) and conf.get("ok"):
        nz = conf.get("nearest_support_zone") or {}
        if isinstance(nz, dict):
            center = _f(nz.get("center"))
            if center is not None:
                return center
    return _f(levels.get("nearest_support"))


def _best_resistance_level(levels: Optional[Dict[str, Any]]) -> Optional[float]:
    if not levels or not isinstance(levels, dict):
        return None
    classic = levels.get("classic_levels") or levels.get("classic") or {}
    conf = classic.get("confluence_zones") if isinstance(classic, dict) else {}
    if not conf:
        conf = levels.get("confluence_zones") or {}
    if isinstance(conf, dict) and conf.get("ok"):
        nz = conf.get("nearest_resistance_zone") or {}
        if isinstance(nz, dict):
            center = _f(nz.get("center"))
            if center is not None:
                return center
    return _f(levels.get("nearest_resistance"))


def _structure_watch_zones(
    *,
    support: Optional[float],
    resistance: Optional[float],
    close: Optional[float],
) -> Dict[str, Any]:
    """无策略命中时：用结构位生成观察区（非正式买点）。"""
    watch_entry = None
    stop_zone = None
    take_profit = None
    medium_watch = None

    if support is not None:
        buf = 0.015
        lo = round(support * (1 - buf), 2)
        hi = round(support * (1 + buf), 2)
        watch_entry = {
            "low": lo,
            "high": hi,
            "price": round(support, 2),
            "basis": "structure_watch",
            "label": f"结构支撑观察区（非买点）≈{_fmt_px(support)}",
        }
        stop_px = round(support * 0.98, 2)
        stop_zone = {
            "price": stop_px,
            "low": stop_px,
            "basis": "structure_invalidation",
            "label": f"跌破支撑观察区失效参考 ≈{_fmt_px(stop_px)}",
        }
        medium_watch = {
            "low": lo,
            "high": hi,
            "price": round(support, 2),
            "basis": "structure_support",
            "label": f"回踩结构支撑 {_fmt_px(support)} 附近观察企稳",
        }

    if resistance is not None:
        take_profit = {
            "prices": [round(resistance, 2)],
            "price": round(resistance, 2),
            "basis": "structure_resistance",
            "label": f"结构阻力观察目标 ≈{_fmt_px(resistance)}",
        }

    summary = "暂无策略正式买点，关注结构支撑附近是否企稳"
    if support is not None and close is not None:
        if close <= support * 1.02:
            summary = (
                f"现价 {_fmt_px(close)} 临近支撑 {_fmt_px(support)}，"
                "观察是否企稳；未触发策略买点前不宜追涨"
            )
        else:
            summary = (
                f"现价 {_fmt_px(close)}，可关注回踩支撑 {_fmt_px(support)} 附近能否企稳"
            )
    elif support is not None:
        summary = f"暂无策略正式买点，关注结构支撑 {_fmt_px(support)} 附近是否企稳"

    return {
        "watch_entry": watch_entry,
        "stop_zone": stop_zone,
        "take_profit": take_profit,
        "medium_watch": medium_watch,
        "summary": summary,
    }


def _zone_txt(z: Optional[Dict[str, Any]]) -> str:
    if not z or not isinstance(z, dict):
        return "--"
    lo, hi = _f(z.get("low")), _f(z.get("high"))
    px = _f(z.get("price"))
    if lo is not None and hi is not None:
        return f"{_fmt_px(lo)} – {_fmt_px(hi)}"
    if px is not None:
        return _fmt_px(px)
    if lo is not None:
        return _fmt_px(lo)
    return "--"


def _levels_to_reference(levels: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not levels or not isinstance(levels, dict):
        return None
    classic = levels.get("classic_levels") or levels.get("classic") or {}
    vp = levels.get("volume_profile") or {}
    conf = classic.get("confluence_zones") or levels.get("confluence_zones") or {}
    ref: Dict[str, Any] = {
        "ok": True,
        "last_close": _resolve_close_from_levels(levels),
        "nearest_support": levels.get("nearest_support"),
        "nearest_resistance": levels.get("nearest_resistance"),
        "nearest_fib_support": classic.get("nearest_fib_support"),
        "nearest_fib_resistance": classic.get("nearest_fib_resistance"),
        "nearest_cam_support": classic.get("nearest_cam_support"),
        "nearest_cam_resistance": classic.get("nearest_cam_resistance"),
        "nearest_pivot_support": classic.get("nearest_pivot_support"),
        "nearest_pivot_resistance": classic.get("nearest_pivot_resistance"),
        "volume_profile": vp if isinstance(vp, dict) else {},
        "confluence_zones": conf if isinstance(conf, dict) else {},
        "nearest_vp_support": vp.get("nearest_support") if isinstance(vp, dict) else None,
        "nearest_vp_resistance": vp.get("nearest_resistance") if isinstance(vp, dict) else None,
        "support_levels": levels.get("support_levels") if isinstance(levels.get("support_levels"), list) else [],
        "resistance_levels": levels.get("resistance_levels")
        if isinstance(levels.get("resistance_levels"), list)
        else [],
    }
    if conf.get("ok"):
        nz_s = conf.get("nearest_support_zone") or {}
        nz_r = conf.get("nearest_resistance_zone") or {}
        if isinstance(nz_s, dict) and nz_s.get("center") is not None:
            ref["nearest_confluence_support"] = nz_s.get("center")
        if isinstance(nz_r, dict) and nz_r.get("center") is not None:
            ref["nearest_confluence_resistance"] = nz_r.get("center")
    return ref


def _pick_primary_strategy(summaries: Dict[str, Dict[str, Any]]) -> str:
    for key in _STRATEGY_PRIORITY:
        s = summaries.get(key) or {}
        if s.get("hit"):
            return key
    return "none"


def _trend_stance(trend: Optional[str]) -> tuple:
    t = (trend or "insufficient").strip().lower()
    return _STANCE_MEDIUM_MAP.get(t, ("neutral", "趋势不明"))


def _merge_medium_stance(*stances: str) -> str:
    vals = [s for s in stances if s]
    if not vals:
        return "neutral"
    if "bear" in vals and "bull" not in vals:
        return "bear"
    if "bull" in vals and "bear" not in vals:
        return "bull"
    return "neutral"


def _short_bias_label(bias: Optional[str]) -> str:
    b = (bias or "").strip().lower()
    if b in ("看多", "bull", "bullish"):
        return "看多"
    if b in ("看空", "bear", "bearish"):
        return "看空"
    if b in ("震荡", "range", "neutral"):
        return "震荡"
    if b == "insufficient":
        return "样本不足"
    return bias or ""


def _build_row_for_advice(
    raw_row: Optional[Dict[str, Any]],
    *,
    levels: Optional[Dict[str, Any]],
    tactical: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    row = dict(raw_row or {})
    lv = levels or {}
    if lv.get("nearest_support") is not None:
        row["nearest_support"] = lv.get("nearest_support")
    if lv.get("nearest_resistance") is not None:
        row["nearest_resistance"] = lv.get("nearest_resistance")
    if isinstance(lv.get("support_levels"), list):
        row["support_levels"] = lv.get("support_levels")
    if isinstance(lv.get("resistance_levels"), list):
        row["resistance_levels"] = lv.get("resistance_levels")
    lc = _resolve_close_from_levels(lv)
    if lc is not None:
        row["close"] = lc
        row["last_close"] = lc
    st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
    if not st and lv:
        st = {}
        if lv.get("nearest_support") is not None:
            st["nearest_support"] = lv.get("nearest_support")
        if lv.get("nearest_resistance") is not None:
            st["nearest_resistance"] = lv.get("nearest_resistance")
        if st:
            row["structure"] = st
    if tactical and isinstance(tactical, dict):
        row["pattern_tactical"] = tactical
        row["tactical"] = tactical
    return row


def _extract_ms(swing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not swing or not isinstance(swing, dict):
        return {}
    data = swing.get("data") if isinstance(swing.get("data"), dict) else swing
    ms = data.get("market_structure") if isinstance(data.get("market_structure"), dict) else data
    weekly = data.get("weekly") if isinstance(data.get("weekly"), dict) else {}
    return {
        "daily_trend": ms.get("trend"),
        "daily_trend_label": ms.get("trend_label") or ms.get("trend"),
        "weekly_trend": weekly.get("trend"),
        "weekly_trend_label": weekly.get("trend_label") or weekly.get("trend"),
        "counter_trend_note": data.get("counter_trend_note") or ms.get("counter_trend_note"),
        "summary": ms.get("summary"),
        "weekly_summary": weekly.get("summary"),
    }


def _extract_gann(gann: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not gann or not isinstance(gann, dict):
        return {}
    data = gann.get("data") if isinstance(gann.get("data"), dict) else gann
    gt = data.get("gann_trend") if isinstance(data.get("gann_trend"), dict) else {}
    verdict = gt.get("verdict") if isinstance(gt.get("verdict"), dict) else {}
    tw = gt.get("time_windows") if isinstance(gt.get("time_windows"), list) else []
    near_tw = [w for w in tw if isinstance(w, dict) and w.get("status") in ("near", "active", "due")]
    return {
        "ok": bool(gt.get("ok")),
        "bias": verdict.get("bias"),
        "bias_label": verdict.get("bias_label") or verdict.get("bias"),
        "summary": verdict.get("summary"),
        "disclaimer": gt.get("disclaimer"),
        "near_time_windows": near_tw[:3],
    }


def build_integrated_trade_plan(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """合成综合交易策略。ctx 含 strategy_pack / levels / pattern / swing / gann / meta。"""
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    strategy_pack = ctx.get("strategy_pack") if isinstance(ctx.get("strategy_pack"), dict) else {}
    summaries = strategy_pack.get("summaries") if isinstance(strategy_pack.get("summaries"), dict) else {}
    raw_rows = strategy_pack.get("rows") if isinstance(strategy_pack.get("rows"), dict) else {}

    levels_data = None
    lv_snap = ctx.get("levels")
    if isinstance(lv_snap, dict):
        levels_data = lv_snap.get("data") if isinstance(lv_snap.get("data"), dict) else lv_snap
    ref = _levels_to_reference(levels_data)

    pattern_snap = ctx.get("pattern") if isinstance(ctx.get("pattern"), dict) else {}
    tactical = pattern_snap.get("tactical") if isinstance(pattern_snap.get("tactical"), dict) else None
    short_bias = _short_bias_label(
        (tactical or {}).get("short_bias") or (tactical or {}).get("bias")
    )

    ms_info = _extract_ms(ctx.get("swing"))
    gann_info = _extract_gann(ctx.get("gann"))

    primary = _pick_primary_strategy(summaries)
    evidence: List[str] = []
    conflicts: List[str] = []

    primary_summary = summaries.get(primary) or {}
    if primary != "none":
        evidence.append(
            f"主策略 {primary_summary.get('name') or primary.upper()}："
            f"{primary_summary.get('label') or '--'}（{primary_summary.get('reason') or ''}）"
        )
    else:
        evidence.append("四策略均未命中：以结构位与趋势旁证为主")

    if levels_data:
        ns, nr = levels_data.get("nearest_support"), levels_data.get("nearest_resistance")
        if ns is not None or nr is not None:
            evidence.append(
                f"结构位：支撑 {_fmt_px(ns)} / 阻力 {_fmt_px(nr)}"
            )

    if short_bias:
        evidence.append(f"形态短线：{short_bias}")
    if ms_info.get("daily_trend_label"):
        evidence.append(f"日线趋势：{ms_info.get('daily_trend_label')}")
    if ms_info.get("weekly_trend_label"):
        evidence.append(f"周线趋势：{ms_info.get('weekly_trend_label')}")
    if gann_info.get("bias_label"):
        evidence.append(f"江恩：{gann_info.get('bias_label')}")

    # trade advice from primary strategy
    advice: Dict[str, Any] = {}
    if primary != "none":
        raw = raw_rows.get(primary)
        row = _build_row_for_advice(raw, levels=levels_data, tactical=tactical)
        advice = build_trade_advice(primary, row, reference_levels=ref)
    else:
        # 无命中：结构观察区（非正式买点）
        kde_s = _best_support_level(levels_data)
        kde_r = _best_resistance_level(levels_data)
        lc = _resolve_close_from_levels(levels_data)
        struct = _structure_watch_zones(support=kde_s, resistance=kde_r, close=lc)
        advice = {
            "action": "watch",
            "confidence": "low",
            "summary": struct["summary"],
            "buy_zone": struct["watch_entry"],
            "stop_zone": struct["stop_zone"],
            "take_profit": struct["take_profit"],
            "deeper_watch": struct["medium_watch"],
            "kde_support": round(kde_s, 2) if kde_s is not None else None,
            "kde_resistance": round(kde_r, 2) if kde_r is not None else None,
            "key_levels": {
                "support": round(kde_s, 2) if kde_s is not None else None,
                "resistance": round(kde_r, 2) if kde_r is not None else None,
                "close": round(lc, 2) if lc is not None else None,
            },
            "horizon": None,
            "sell_triggers": [],
        }
        if kde_s is not None:
            evidence.append(f"观察回踩支撑 {_fmt_px(kde_s)} 附近（非买点）")
        if lc is not None:
            evidence.append(f"现价 {_fmt_px(lc)}")

    action = str(advice.get("action") or "watch")
    confidence = str(advice.get("confidence") or "medium")

    # 形态与短线 action 冲突
    if short_bias == "看空" and action == "buy":
        conflicts.append("形态短线偏空，与策略买点并存，宜降仓或等待确认")
        confidence = "low"
    elif short_bias == "看多" and action == "watch":
        if confidence == "low":
            confidence = "medium"

    daily_st, daily_lab = _trend_stance(ms_info.get("daily_trend"))
    weekly_st, weekly_lab = _trend_stance(ms_info.get("weekly_trend"))
    if ms_info.get("counter_trend_note"):
        conflicts.append(str(ms_info["counter_trend_note"]))
    elif daily_st == "bull" and weekly_st == "bear":
        conflicts.append("日线偏多但周线偏空，短线与中长线节奏可能不一致")
    elif daily_st == "bear" and weekly_st == "bull":
        conflicts.append("日线偏空但周线偏多，宜等待日线企稳再跟")

    gann_st, gann_lab = _GANN_BIAS_MAP.get(
        str(gann_info.get("bias") or "").lower(), ("neutral", "")
    )
    stance_medium = _merge_medium_stance(weekly_st, gann_st)
    stance_medium_labels = [weekly_lab]
    if gann_lab:
        stance_medium_labels.append(gann_lab)
    bias_label = " / ".join([x for x in stance_medium_labels if x])

    if action == "buy" and stance_medium == "bear":
        conflicts.append("短线有买点但中长线偏空，宜小仓或快进快出")
        if confidence == "high":
            confidence = "medium"

    horizon = advice.get("horizon") if isinstance(advice.get("horizon"), dict) else {}
    medium_watch = None
    if horizon.get("medium_term") and isinstance(horizon["medium_term"], dict):
        medium_watch = horizon["medium_term"].get("watch")
    if not medium_watch:
        medium_watch = advice.get("deeper_watch")

    ma20 = None
    if horizon.get("medium_term") and isinstance(horizon["medium_term"], dict):
        ma20 = horizon["medium_term"].get("ma20")

    exit_triggers: List[str] = []
    if advice.get("sell_triggers"):
        for t in advice["sell_triggers"]:
            if isinstance(t, dict) and t.get("label"):
                exit_triggers.append(str(t["label"]))
    if weekly_st == "bear":
        exit_triggers.append("周线趋势转弱或跌破最近 HL 结构")
    if gann_info.get("near_time_windows"):
        for w in gann_info["near_time_windows"]:
            exit_triggers.append(
                f"江恩时间窗 {w.get('label') or w.get('window')}（{w.get('status')}）"
            )
    stop_z = advice.get("stop_zone")
    if stop_z:
        exit_triggers.append(f"跌破止损参考 {_zone_txt(stop_z)}")

    holding_parts: List[str] = []
    if stance_medium == "bull":
        holding_parts.append("中长线偏多：回踩关键均线或结构支撑不破可持有或分批加仓")
    elif stance_medium == "bear":
        holding_parts.append("中长线偏空：反弹至压力附近宜减仓，不宜重仓抄底")
    else:
        holding_parts.append("中长线震荡：区间操作，突破/跌破结构再顺势")
    if ma20 is not None:
        holding_parts.append(f"MA20≈{_fmt_px(ma20)} 作趋势回撤观察")
    if medium_watch and isinstance(medium_watch, dict) and medium_watch.get("label"):
        holding_parts.append(str(medium_watch["label"]))

    tactical_analysis = (tactical or {}).get("analysis") if isinstance((tactical or {}).get("analysis"), dict) else {}
    mt_nlg = tactical_analysis.get("mediumTerm") or (tactical or {}).get("mediumTerm")
    if mt_nlg:
        holding_parts.append(str(mt_nlg)[:160])

    short_triggers: List[str] = []
    if action == "buy":
        short_triggers.append("买入区企稳后可分批建仓")
    elif action == "watch":
        short_triggers.append("等待策略买点或形态确认后再介入")
        bz_watch = advice.get("buy_zone")
        if (
            bz_watch
            and isinstance(bz_watch, dict)
            and bz_watch.get("basis") == "structure_watch"
        ):
            short_triggers.append("当前仅为结构观察区，非策略正式买点")
    bz = advice.get("buy_zone")
    if bz and bz.get("label"):
        short_triggers.append(str(bz["label"]))
    tp = advice.get("take_profit")
    if tp and isinstance(tp, dict) and tp.get("label"):
        short_triggers.append(f"止盈：{tp['label']}")

    medium_summary = "；".join(holding_parts[:3]) if holding_parts else "暂无明确中长线计划，以周线趋势与结构位为主"

    return {
        "stance_short": action,
        "stance_short_label": _ACTION_LABELS.get(action, action),
        "stance_medium": stance_medium,
        "stance_medium_label": bias_label or "中性观察",
        "confidence": confidence,
        "primary_strategy": primary,
        "primary_strategy_name": primary_summary.get("name") if primary != "none" else "无命中",
        "short_term": {
            "action": action,
            "action_label": _ACTION_LABELS.get(action, action),
            "entry_zone": advice.get("buy_zone"),
            "stop_zone": advice.get("stop_zone"),
            "take_profit": advice.get("take_profit"),
            "triggers": short_triggers,
            "summary": advice.get("summary") or "",
            "evidence": [e for e in evidence if "短线" in e or "策略" in e or "结构" in e][:6],
        },
        "medium_term": {
            "bias": stance_medium,
            "bias_label": bias_label,
            "watch_zone": medium_watch,
            "ma20": ma20,
            "holding_plan": "；".join(holding_parts),
            "exit_triggers": exit_triggers[:6],
            "summary": medium_summary,
            "evidence": [
                e for e in evidence
                if "周线" in e or "江恩" in e or "日线" in e
            ][:6],
        },
        "key_levels": advice.get("key_levels") or {
            "support": advice.get("kde_support"),
            "resistance": advice.get("kde_resistance"),
            "close": _resolve_close_from_levels(levels_data),
        },
        "structure_rr": advice.get("structure_rr"),
        "conflicts": conflicts,
        "evidence": evidence,
        "disclaimer": (
            "以上为规则模板合成的短线/中长线参考，整合策略命中、结构位、形态战术、"
            "波段趋势与江恩几何结论，不构成投资建议。"
        ),
    }
