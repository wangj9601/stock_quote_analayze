# -*- coding: utf-8 -*-
"""日线波段与趋势结构（Market Structure）：ZigZag → HH/HL → 趋势标签。

复用 swing_zigzag 参数口径（与 Fib / KDE 结构锚一致）。
一期不做完整 SMC（CHOCH/OB/FVG）；仅提供可解释的波段叙事层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.swing_zigzag import (
    DEFAULT_FRACTAL,
    DEFAULT_MAX_BARS,
    DEFAULT_MIN_SWING_BARS,
    PRICE_DECIMALS,
    _augment_with_window_extremes,
    _depth_threshold,
    _parse_bars,
    find_fractal_pivots,
    wilder_atr,
    zigzag_from_fractals,
)

# 收盘越过摆动高/低的缓冲（与形态突破量级接近）
BOS_BREAK_MULT_UP = 1.005
BOS_BREAK_MULT_DOWN = 0.995

TREND_LABELS_ZH = {
    "uptrend": "上升趋势",
    "downtrend": "下降趋势",
    "transition": "趋势转换",
    "range": "震荡整理",
    "insufficient": "信息不足",
}

STRUCTURE_LABELS = ("HH", "HL", "LH", "LL")


def _round_price(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return round(float(v), PRICE_DECIMALS)
    except (TypeError, ValueError):
        return None


def _label_hhhl(zigzag: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """相对前一同向极值标注 HH/HL/LH/LL；首个高/低为 —。"""
    out: List[Dict[str, Any]] = []
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    for z in zigzag:
        kind = str(z.get("kind") or "")
        price = _round_price(z.get("price"))
        label = "—"
        if price is None:
            item = dict(z)
            item["structure"] = label
            out.append(item)
            continue
        if kind == "high":
            if last_high is None:
                label = "—"
            elif price > last_high:
                label = "HH"
            elif price < last_high:
                label = "LH"
            else:
                label = "—"
            last_high = price
        elif kind == "low":
            if last_low is None:
                label = "—"
            elif price > last_low:
                label = "HL"
            elif price < last_low:
                label = "LL"
            else:
                label = "—"
            last_low = price
        item = {
            "index": z.get("index"),
            "kind": kind,
            "price": price,
            "date": z.get("date"),
            "structure": label,
            "confirmed": bool(z.get("confirmed", True)),
        }
        out.append(item)
    return out


def _trend_from_labels(points: Sequence[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    趋势判定（轻量，近端优先）：
    - 近端刚形成 HH+HL 且此前有空头标注 → transition（避免仍报下降）
    - 连续抬高高低点 → uptrend；连续降低 → downtrend
    """
    if len(points) < 4:
        return "insufficient", {"reason": "pivots_lt_4", "hh": 0, "hl": 0, "lh": 0, "ll": 0}

    recent = list(points[-8:])
    counts = {"HH": 0, "HL": 0, "LH": 0, "LL": 0}
    for p in recent:
        s = str(p.get("structure") or "")
        if s in counts:
            counts[s] += 1

    highs = [p for p in recent if p.get("kind") == "high" and p.get("structure") in ("HH", "LH")]
    lows = [p for p in recent if p.get("kind") == "low" and p.get("structure") in ("HL", "LL")]
    last_high_st = highs[-1].get("structure") if highs else None
    last_low_st = lows[-1].get("structure") if lows else None
    prev_high_st = highs[-2].get("structure") if len(highs) >= 2 else None
    prev_low_st = lows[-2].get("structure") if len(lows) >= 2 else None

    rising_highs = last_high_st == "HH" and prev_high_st == "HH"
    rising_lows = last_low_st == "HL" and prev_low_st == "HL"
    falling_highs = last_high_st == "LH" and prev_high_st == "LH"
    falling_lows = last_low_st == "LL" and prev_low_st == "LL"
    recent_bull_pair = last_high_st == "HH" and last_low_st == "HL"
    recent_bear_pair = last_high_st == "LH" and last_low_st == "LL"
    last4 = [str(p.get("structure") or "") for p in recent if p.get("structure") in STRUCTURE_LABELS][-4:]
    last4_bull = last4.count("HH") + last4.count("HL")
    last4_bear = last4.count("LH") + last4.count("LL")

    meta = {
        "reason": "ok",
        "hh": counts["HH"],
        "hl": counts["HL"],
        "lh": counts["LH"],
        "ll": counts["LL"],
        "rising_highs": rising_highs,
        "rising_lows": rising_lows,
        "falling_highs": falling_highs,
        "falling_lows": falling_lows,
        "recent_bull_pair": recent_bull_pair,
        "recent_bear_pair": recent_bear_pair,
        "last4": last4,
    }

    if recent_bull_pair and (counts["LH"] + counts["LL"]) >= 2 and not (rising_highs and rising_lows):
        return "transition", {**meta, "reason": "bull_pair_after_bear"}
    if recent_bear_pair and (counts["HH"] + counts["HL"]) >= 2 and not (falling_highs and falling_lows):
        return "transition", {**meta, "reason": "bear_pair_after_bull"}

    if (rising_highs and rising_lows) or (last4_bull >= 3 and last4_bear <= 1 and recent_bull_pair):
        return "uptrend", {**meta, "reason": "hh_hl"}
    if (falling_highs and falling_lows) or (last4_bear >= 3 and last4_bull <= 1 and recent_bear_pair):
        return "downtrend", {**meta, "reason": "lh_ll"}
    if counts["HH"] >= 2 and counts["HL"] >= 2 and counts["HH"] + counts["HL"] > counts["LH"] + counts["LL"]:
        return "uptrend", {**meta, "reason": "hh_hl_count"}
    if counts["LH"] >= 2 and counts["LL"] >= 2 and counts["LH"] + counts["LL"] > counts["HH"] + counts["HL"]:
        return "downtrend", {**meta, "reason": "lh_ll_count"}

    if (rising_highs and falling_lows) or (falling_highs and rising_lows) or recent_bull_pair or recent_bear_pair:
        return "transition", {**meta, "reason": "mixed_legs"}
    if counts["HH"] or counts["HL"] or counts["LH"] or counts["LL"]:
        return "range", {**meta, "reason": "no_clear_series"}
    return "insufficient", {**meta, "reason": "no_labels"}


def _last_bos_like(
    points: Sequence[Dict[str, Any]],
    *,
    last_close: Optional[float],
) -> Optional[Dict[str, Any]]:
    """轻量破摆动高/低：收盘有效越过最近确认的 swing high / swing low。"""
    if last_close is None or last_close <= 0 or len(points) < 2:
        return None
    last_high = None
    last_low = None
    for p in reversed(points):
        if last_high is None and p.get("kind") == "high" and p.get("price") is not None:
            last_high = p
        if last_low is None and p.get("kind") == "low" and p.get("price") is not None:
            last_low = p
        if last_high is not None and last_low is not None:
            break
    if last_high is None and last_low is None:
        return None

    close = float(last_close)
    # 优先判定与最近极值时间更近者；若双侧都破则取幅度更大者
    candidates: List[Dict[str, Any]] = []
    if last_high is not None:
        lvl = float(last_high["price"])
        thr = lvl * BOS_BREAK_MULT_UP
        if close >= thr:
            candidates.append(
                {
                    "type": "break_swing_high",
                    "label": "收盘越过近期摆动高点",
                    "level": round(lvl, PRICE_DECIMALS),
                    "level_date": last_high.get("date"),
                    "close": round(close, PRICE_DECIMALS),
                    "buffer_mult": BOS_BREAK_MULT_UP,
                    "excess_pct": round((close / lvl - 1.0) * 100.0, 3) if lvl else None,
                }
            )
    if last_low is not None:
        lvl = float(last_low["price"])
        thr = lvl * BOS_BREAK_MULT_DOWN
        if close <= thr:
            candidates.append(
                {
                    "type": "break_swing_low",
                    "label": "收盘跌破近期摆动低点",
                    "level": round(lvl, PRICE_DECIMALS),
                    "level_date": last_low.get("date"),
                    "close": round(close, PRICE_DECIMALS),
                    "buffer_mult": BOS_BREAK_MULT_DOWN,
                    "excess_pct": round((close / lvl - 1.0) * 100.0, 3) if lvl else None,
                }
            )
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # 双侧都触发时取 |excess| 更大者
    return max(candidates, key=lambda c: abs(float(c.get("excess_pct") or 0)))


def _fmt_px(v: Any) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "--"


def build_trend_analysis(
    trend: str,
    points: Sequence[Dict[str, Any]],
    bos: Optional[Dict[str, Any]],
    *,
    last_close: Optional[float] = None,
    trend_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成「趋势分析说明」：读图图例 + 结构解读 + 阶段判断 + 观察要点。"""
    legend = (
        "读图：HH=更高高点，HL=更高低点（多头结构）；"
        "LH=更低高点，LL=更低低点（空头结构）。"
        "折线仅连接确认摆动点，非完整 K 线。"
    )
    recent = [p for p in points if str(p.get("structure") or "") in STRUCTURE_LABELS]
    chain = "→".join(str(p.get("structure")) for p in recent[-6:]) if recent else "—"
    last_high = next((p for p in reversed(points) if p.get("kind") == "high"), None)
    last_low = next((p for p in reversed(points) if p.get("kind") == "low"), None)

    structure_bits: List[str] = []
    if chain and chain != "—":
        structure_bits.append(f"近端标注序列为 {chain}")
    if last_high:
        structure_bits.append(
            f"最近摆动高点 {_fmt_px(last_high.get('price'))}"
            f"（{last_high.get('structure') or '—'}，{last_high.get('date') or '--'}）"
        )
    if last_low:
        structure_bits.append(
            f"最近摆动低点 {_fmt_px(last_low.get('price'))}"
            f"（{last_low.get('structure') or '—'}，{last_low.get('date') or '--'}）"
        )
    if last_close is not None:
        structure_bits.append(f"基准日收盘 {_fmt_px(last_close)}")
    structure_read = "；".join(structure_bits) + "。" if structure_bits else "摆动点不足，暂无结构解读。"

    meta = trend_meta or {}
    if trend == "uptrend":
        stage = "阶段判断：日线波段以抬高的高点与低点为主，多头结构仍占优；回撤宜观察是否守住最近 HL。"
    elif trend == "downtrend":
        stage = "阶段判断：日线波段以降低的高点与低点为主，空头结构仍占优；反弹宜观察是否受制于最近 LH。"
    elif trend == "transition":
        reason = str(meta.get("reason") or "")
        if reason == "bull_pair_after_bear" or meta.get("recent_bull_pair"):
            stage = (
                "阶段判断：此前多见 LH/LL 下行结构，近端已出现 HH 与 HL，"
                "波段由空翻多的转换迹象增强；需确认收盘站稳突破位、且后续低点不再下破最近 HL。"
            )
        elif reason == "bear_pair_after_bull" or meta.get("recent_bear_pair"):
            stage = (
                "阶段判断：此前多见 HH/HL 上行结构，近端已出现 LH 与 LL，"
                "波段由多转空的转换迹象增强；反弹宜警惕最近 LH 压制。"
            )
        else:
            stage = "阶段判断：高低点标注交叉，趋势方向未单一确立，按转换/观察处理。"
    elif trend == "range":
        stage = "阶段判断：近端未形成清晰的连续抬高或降低系列，更接近震荡整理。"
    else:
        stage = "阶段判断：样本或摆动点不足，暂不给出方向结论。"

    watch_bits: List[str] = []
    if bos:
        if bos.get("type") == "break_swing_high":
            watch_bits.append(
                f"观察要点：收盘已越过摆动高 {_fmt_px(bos.get('level'))}"
                f"（{bos.get('level_date') or '--'}），属上行破位信号；"
                f"若重新跌回该高点下方，则转换失败风险上升。"
            )
        elif bos.get("type") == "break_swing_low":
            watch_bits.append(
                f"观察要点：收盘已跌破摆动低 {_fmt_px(bos.get('level'))}"
                f"（{bos.get('level_date') or '--'}），属下行破位信号；"
                f"反抽该低点附近宜谨慎。"
            )
        else:
            watch_bits.append(f"观察要点：{bos.get('label') or bos.get('type')}")
    else:
        if last_high and last_low:
            watch_bits.append(
                f"观察要点：上破 {_fmt_px(last_high.get('price'))} 强化多头转换；"
                f"下破 {_fmt_px(last_low.get('price'))} 则空头结构延续。"
            )
        else:
            watch_bits.append("观察要点：等待下一确认摆动点后再评估方向。")
    watch_bits.append("本说明与形态短期三态并列参考，不互相覆盖；规则模板，非投资建议。")
    watch = " ".join(watch_bits)

    paragraphs = [legend, structure_read, stage, watch]
    return {
        "legend": legend,
        "structure_read": structure_read,
        "stage": stage,
        "watch": watch,
        "paragraphs": paragraphs,
        "text": chr(10).join(paragraphs),
    }


def _summary_nlg(
    trend: str,
    points: Sequence[Dict[str, Any]],
    bos: Optional[Dict[str, Any]],
    analysis: Optional[Dict[str, Any]] = None,
    *,
    period_zh: str = "日线",
) -> str:
    zh = TREND_LABELS_ZH.get(trend, trend)
    recent = [str(p.get("structure") or "—") for p in points[-6:] if p.get("structure")]
    chain = "→".join(recent) if recent else "—"
    parts = [f"{period_zh}波段：{zh}"]
    if chain and chain != "—":
        parts.append(f"近端标注 {chain}")
    if bos:
        parts.append(str(bos.get("label") or bos.get("type") or "关键事件"))
    if analysis and analysis.get("stage"):
        stage = str(analysis["stage"])
        if "：" in stage:
            stage = stage.split("：", 1)[-1]
        short = stage[:56].rstrip("。")
        parts.append(short + ("…" if len(stage) > 56 else ""))
    else:
        parts.append("详见趋势分析说明")
    return "；".join(parts) + "。"


def aggregate_daily_to_weekly(
    bars: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """日线升序 OHLC → 自然周（周一为周起点）聚合周线。"""
    from datetime import date, datetime, timedelta

    buckets: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        raw = b.get("date") or b.get("trade_date")
        if raw is None:
            continue
        try:
            if hasattr(raw, "date") and callable(raw.date):
                ds = raw.date()  # datetime
            elif isinstance(raw, date):
                ds = raw
            else:
                ds = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        week_start = ds - timedelta(days=ds.weekday())
        key = week_start.isoformat()
        o = _round_price(b.get("open"))
        h = _round_price(b.get("high"))
        lo = _round_price(b.get("low"))
        c = _round_price(b.get("close"))
        if c is None and h is None and lo is None:
            continue
        if key not in buckets:
            order.append(key)
            buckets[key] = {
                "date": key,
                "open": o if o is not None else c,
                "high": h if h is not None else c,
                "low": lo if lo is not None else c,
                "close": c if c is not None else h or lo or o,
                "volume": 0.0,
            }
        w = buckets[key]
        if o is not None and w.get("open") is None:
            w["open"] = o
        if h is not None:
            prev_h = w.get("high")
            w["high"] = h if prev_h is None else max(float(prev_h), float(h))
        if lo is not None:
            prev_l = w.get("low")
            w["low"] = lo if prev_l is None else min(float(prev_l), float(lo))
        if c is not None:
            w["close"] = c
        vol = b.get("volume")
        try:
            if vol is not None:
                w["volume"] = float(w.get("volume") or 0) + float(vol)
        except (TypeError, ValueError):
            pass
    return [buckets[k] for k in order]


def analyze_market_structure(
    bars: Sequence[Dict[str, Any]],
    *,
    max_bars: int = DEFAULT_MAX_BARS,
    fractal_left: int = DEFAULT_FRACTAL,
    fractal_right: int = DEFAULT_FRACTAL,
    min_swing_bars: int = DEFAULT_MIN_SWING_BARS,
    max_points: int = 12,
    period: str = "daily",
) -> Dict[str, Any]:
    """从 OHLC（升序）计算波段与趋势结构；period=daily|weekly 仅影响文案前缀。"""
    parsed = _parse_bars(bars)
    mb = max(40, int(max_bars or DEFAULT_MAX_BARS))
    if len(parsed) > mb:
        parsed = parsed[-mb:]
    min_n = max(1, int(min_swing_bars or DEFAULT_MIN_SWING_BARS))
    max_pts = max(4, min(24, int(max_points or 12)))
    period_n = str(period or "daily").strip().lower()
    period_zh = "周线" if period_n == "weekly" else "日线"

    empty: Dict[str, Any] = {
        "ok": False,
        "reason": "insufficient_bars",
        "trend": "insufficient",
        "trend_label": TREND_LABELS_ZH["insufficient"],
        "trend_meta": {},
        "points": [],
        "zigzag": [],
        "last_bos_like": None,
        "trend_analysis": None,
        "summary": f"{period_zh}样本不足，暂无法判断波段趋势。",
        "last_close": None,
        "asof": None,
        "period": period_n,
        "params": {
            "max_bars": mb,
            "fractal_left": fractal_left,
            "fractal_right": fractal_right,
            "min_swing_bars": min_n,
            "max_points": max_pts,
            "anchor_method": "zigzag_fractal",
            "period": period_n,
        },
    }
    need = fractal_left + fractal_right + 5
    if len(parsed) < need:
        return empty

    atr = wilder_atr(parsed)
    last_close = float(parsed[-1][3])
    asof = parsed[-1][0].isoformat()
    depth = _depth_threshold(last_close, atr)
    pivots = find_fractal_pivots(parsed, left=fractal_left, right=fractal_right)
    pivots = _augment_with_window_extremes(parsed, pivots)
    zz_raw = zigzag_from_fractals(pivots, depth=depth)

    # 过滤过短相邻腿（对齐 Fib min_swing_bars 精神：展示链保留，但过密点可合并已在 zigzag 完成）
    zz_clean: List[Dict[str, Any]] = []
    for z in zz_raw:
        zz_clean.append(
            {
                "index": int(z["index"]),
                "kind": z["kind"],
                "price": round(float(z["price"]), PRICE_DECIMALS),
                "date": z["date"],
                "confirmed": True,
            }
        )

    if len(zz_clean) < 2:
        return {
            **empty,
            "reason": "no_confirmed_swing",
            "last_close": round(last_close, PRICE_DECIMALS),
            "asof": asof,
            "summary": f"{period_zh}未确认足够摆动点，暂无法判断波段趋势。",
            "period": period_n,
        }

    labeled = _label_hhhl(zz_clean)
    # 对外只返回最近 max_points；标注仍基于全链（相对前一同向极值）
    points = labeled[-max_pts:]
    trend, trend_meta = _trend_from_labels(labeled)
    bos = _last_bos_like(labeled, last_close=last_close)
    analysis = build_trend_analysis(
        trend,
        points,
        bos,
        last_close=last_close,
        trend_meta=trend_meta,
    )
    summary = _summary_nlg(trend, points, bos, analysis, period_zh=period_zh)

    return {
        "ok": True,
        "reason": "ok",
        "trend": trend,
        "trend_label": TREND_LABELS_ZH.get(trend, trend),
        "trend_meta": trend_meta,
        "trend_analysis": analysis,
        "points": points,
        "zigzag": [
            {
                "index": p.get("index"),
                "kind": p.get("kind"),
                "price": p.get("price"),
                "date": p.get("date"),
                "structure": p.get("structure"),
            }
            for p in points
        ],
        "last_bos_like": bos,
        "summary": summary,
        "last_close": round(last_close, PRICE_DECIMALS),
        "asof": asof,
        "atr": round(atr, PRICE_DECIMALS) if atr is not None else None,
        "depth": round(depth, PRICE_DECIMALS),
        "period": period_n,
        "params": {
            "max_bars": mb,
            "fractal_left": fractal_left,
            "fractal_right": fractal_right,
            "min_swing_bars": min_n,
            "max_points": max_pts,
            "anchor_method": "zigzag_fractal",
            "period": period_n,
        },
    }


def contrast_with_pattern_bias(
    trend: str,
    short_bias: Optional[str],
    *,
    period_zh: str = "日线",
) -> Optional[str]:
    """与形态 short_bias 对照一句（并列，不覆盖）。"""
    if not short_bias or short_bias in ("insufficient",):
        return None
    bias = str(short_bias).strip().lower()
    # 形态侧常用中文或英文
    bullish = bias in ("bullish", "看多", "up", "long")
    bearish = bias in ("bearish", "看空", "down", "short")
    sideways = bias in ("neutral", "震荡", "range", "watch")
    if trend == "uptrend" and bearish:
        return f"对照：形态偏空，但{period_zh}波段仍呈抬升（HH/HL），宜区分「形态压力」与「波段趋势」。"
    if trend == "downtrend" and bullish:
        return f"对照：形态偏多，但{period_zh}波段已走弱（LH/LL），宜区分「形态反转」与「波段趋势」。"
    if trend == "uptrend" and bullish:
        return f"对照：形态与{period_zh}波段方向一致偏多。"
    if trend == "downtrend" and bearish:
        return f"对照：形态与{period_zh}波段方向一致偏空。"
    if trend in ("range", "transition") and sideways:
        return "对照：形态与波段均偏震荡/转换，宜等待方向确认。"
    if trend in ("range", "transition") and (bullish or bearish):
        return "对照：波段尚未形成清晰系列，形态方向仅供参考，勿互相覆盖。"
    return None


def weekly_counter_trend_caution(
    weekly_trend: Optional[str],
    short_bias: Optional[str],
) -> Optional[Dict[str, Any]]:
    """周线空头 + 日线/形态看多 → 逆势谨慎（软提示，不否决策略）。"""
    wt = str(weekly_trend or "").strip().lower()
    if wt != "downtrend":
        return None
    if not short_bias or short_bias in ("insufficient",):
        return None
    bias = str(short_bias).strip().lower()
    bullish = bias in ("bullish", "看多", "up", "long")
    if not bullish:
        return None
    return {
        "ok": True,
        "counter_trend_caution": True,
        "text": "逆势谨慎：周线仍处下降趋势（LH/LL），日线/形态偏多仅作反弹观察，不宜当作大级别趋势反转确认。",
        "weekly_trend": "downtrend",
    }
