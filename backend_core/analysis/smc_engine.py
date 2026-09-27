# -*- coding: utf-8 -*-
"""日线 SMC 子集：CHOCH/BOS、订单块（OB）、公允价值缺口（FVG）。

复用 ZigZag 标注点与收盘破位缓冲；不替代形态 tactical，不入策略硬筛。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.swing_zigzag import PRICE_DECIMALS, wilder_atr

# 与 market_structure 破位缓冲对齐（避免循环导入，常量本地维护）
BOS_BREAK_MULT_UP = 1.005
BOS_BREAK_MULT_DOWN = 0.995
FVG_ATR_MULT = 0.15
FVG_MIN_PCT = 0.003
MAX_ORDER_BLOCKS = 6
MAX_FVGS = 8
DEFAULT_CONFIRM_RIGHT = 2


def _trend_from_labels(points: Sequence[Dict[str, Any]]):
    from backend_core.analysis.market_structure import _trend_from_labels as _fn

    return _fn(points)


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _as_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _round_px(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return round(float(v), PRICE_DECIMALS)
    except (TypeError, ValueError):
        return None


def parse_ohlc_bars(bars: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """解析为带 index 的 OHLC 列表；无 open 时用前收近似。"""
    raw: List[Tuple[date, Optional[float], float, float, float]] = []
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        d = _as_date(b.get("date") or b.get("trade_date"))
        h = _f(b.get("high"))
        lo = _f(b.get("low"))
        c = _f(b.get("close"))
        o = _f(b.get("open"))
        if d is None or h is None or lo is None or c is None:
            continue
        if h < lo:
            h, lo = lo, h
        raw.append((d, o, h, lo, c))
    raw.sort(key=lambda x: x[0])
    out: List[Dict[str, Any]] = []
    prev_c: Optional[float] = None
    for i, (d, o, h, lo, c) in enumerate(raw):
        open_px = o if o is not None else (prev_c if prev_c is not None else c)
        out.append(
            {
                "index": i,
                "date": d.isoformat(),
                "open": float(open_px),
                "high": float(h),
                "low": float(lo),
                "close": float(c),
            }
        )
        prev_c = float(c)
    return out


def _parsed_hlc_for_atr(
    ohlc: Sequence[Dict[str, Any]],
) -> List[Tuple[date, float, float, float]]:
    rows: List[Tuple[date, float, float, float]] = []
    for b in ohlc:
        d = _as_date(b.get("date"))
        if d is None:
            continue
        rows.append((d, float(b["high"]), float(b["low"]), float(b["close"])))
    return rows


def trend_to_structure_bias(trend: str) -> str:
    t = str(trend or "").strip().lower()
    if t == "uptrend":
        return "bullish"
    if t == "downtrend":
        return "bearish"
    return "neutral"


def _last_swing(
    points: Sequence[Dict[str, Any]], kind: str
) -> Optional[Dict[str, Any]]:
    for p in reversed(points):
        if p.get("kind") == kind and p.get("price") is not None:
            return p
    return None


def _classify_break(
    *,
    bias: str,
    break_side: str,
) -> Tuple[str, str, Optional[str]]:
    """返回 (type, direction, event_key)。neutral 破位 → bos + structure_shift_unconfirmed 标记由调用方加。"""
    if break_side == "high":
        direction = "bullish"
        if bias == "bearish":
            return "choch", direction, "choch_bullish"
        if bias == "bullish":
            return "bos", direction, "bos_bullish"
        return "bos", direction, "structure_shift_unconfirmed"
    # break_side == "low"
    direction = "bearish"
    if bias == "bullish":
        return "choch", direction, "choch_bearish"
    if bias == "bearish":
        return "bos", direction, "bos_bearish"
    return "bos", direction, "structure_shift_unconfirmed"


def detect_structure_events(
    ohlc: Sequence[Dict[str, Any]],
    labeled: Sequence[Dict[str, Any]],
    *,
    confirm_right: int = DEFAULT_CONFIRM_RIGHT,
    break_mult_up: float = BOS_BREAK_MULT_UP,
    break_mult_down: float = BOS_BREAK_MULT_DOWN,
) -> List[Dict[str, Any]]:
    """沿 K 线扫描：用已确认摆动点判定 BOS/CHOCH。"""
    if len(ohlc) < 3 or len(labeled) < 2:
        return []

    events: List[Dict[str, Any]] = []
    broken_high_keys: set = set()
    broken_low_keys: set = set()
    cr = max(0, int(confirm_right))

    for bar in ohlc:
        i = int(bar["index"])
        close = float(bar["close"])
        active = [
            p
            for p in labeled
            if p.get("index") is not None and int(p["index"]) + cr < i
        ]
        if len(active) < 2:
            continue
        trend, _ = _trend_from_labels(active)
        bias = trend_to_structure_bias(trend)
        last_high = _last_swing(active, "high")
        last_low = _last_swing(active, "low")

        candidates: List[Dict[str, Any]] = []
        if last_high is not None:
            lvl = float(last_high["price"])
            key = (last_high.get("date"), round(lvl, PRICE_DECIMALS), "high")
            thr = lvl * break_mult_up
            if key not in broken_high_keys and close >= thr:
                etype, direction, ekey = _classify_break(bias=bias, break_side="high")
                candidates.append(
                    {
                        "type": etype,
                        "direction": direction,
                        "event_key": ekey,
                        "level": _round_px(lvl),
                        "level_date": last_high.get("date"),
                        "level_index": last_high.get("index"),
                        "bar_date": bar.get("date"),
                        "bar_index": i,
                        "close": _round_px(close),
                        "excess_pct": round((close / lvl - 1.0) * 100.0, 3) if lvl else None,
                        "structure_bias": bias,
                        "leg_start_index": _leg_start_index(active, "bullish"),
                    }
                )
                broken_high_keys.add(key)
        if last_low is not None:
            lvl = float(last_low["price"])
            key = (last_low.get("date"), round(lvl, PRICE_DECIMALS), "low")
            thr = lvl * break_mult_down
            if key not in broken_low_keys and close <= thr:
                etype, direction, ekey = _classify_break(bias=bias, break_side="low")
                candidates.append(
                    {
                        "type": etype,
                        "direction": direction,
                        "event_key": ekey,
                        "level": _round_px(lvl),
                        "level_date": last_low.get("date"),
                        "level_index": last_low.get("index"),
                        "bar_date": bar.get("date"),
                        "bar_index": i,
                        "close": _round_px(close),
                        "excess_pct": round((close / lvl - 1.0) * 100.0, 3) if lvl else None,
                        "structure_bias": bias,
                        "leg_start_index": _leg_start_index(active, "bearish"),
                    }
                )
                broken_low_keys.add(key)

        if not candidates:
            continue
        if len(candidates) == 1:
            events.append(candidates[0])
        else:
            events.append(
                max(candidates, key=lambda c: abs(float(c.get("excess_pct") or 0)))
            )

    return events


def _leg_start_index(active: Sequence[Dict[str, Any]], direction: str) -> Optional[int]:
    """冲动腿起点：看涨破位取最近摆动低；看跌破位取最近摆动高。"""
    if direction == "bullish":
        p = _last_swing(active, "low")
    else:
        p = _last_swing(active, "high")
    if p is None or p.get("index") is None:
        return None
    return int(p["index"])


def _is_bearish_candle(bar: Dict[str, Any], prev_close: Optional[float]) -> bool:
    o = _f(bar.get("open"))
    c = _f(bar.get("close"))
    if o is not None and c is not None:
        return c < o
    if c is not None and prev_close is not None:
        return c < prev_close
    return False


def _is_bullish_candle(bar: Dict[str, Any], prev_close: Optional[float]) -> bool:
    o = _f(bar.get("open"))
    c = _f(bar.get("close"))
    if o is not None and c is not None:
        return c > o
    if c is not None and prev_close is not None:
        return c > prev_close
    return False


def detect_order_blocks(
    ohlc: Sequence[Dict[str, Any]],
    events: Sequence[Dict[str, Any]],
    *,
    max_blocks: int = MAX_ORDER_BLOCKS,
) -> List[Dict[str, Any]]:
    """由结构事件回溯冲动腿内最后反向 K，生成 OB。"""
    if not ohlc or not events:
        return []
    by_idx = {int(b["index"]): b for b in ohlc}
    last_close = float(ohlc[-1]["close"])
    blocks: List[Dict[str, Any]] = []

    for ev in events:
        direction = str(ev.get("direction") or "")
        bar_index = ev.get("bar_index")
        leg_start = ev.get("leg_start_index")
        if bar_index is None:
            continue
        end_i = int(bar_index)
        start_i = int(leg_start) if leg_start is not None else max(0, end_i - 20)
        if start_i > end_i:
            start_i, end_i = end_i, start_i

        chosen: Optional[Dict[str, Any]] = None
        for i in range(end_i - 1, start_i - 1, -1):
            bar = by_idx.get(i)
            if bar is None:
                continue
            prev = by_idx.get(i - 1)
            prev_c = float(prev["close"]) if prev else None
            if direction == "bullish" and _is_bearish_candle(bar, prev_c):
                chosen = bar
                break
            if direction == "bearish" and _is_bullish_candle(bar, prev_c):
                chosen = bar
                break
        if chosen is None:
            # 回退：腿起点蜡烛
            chosen = by_idx.get(start_i) or by_idx.get(end_i)

        if chosen is None:
            continue

        lo = float(chosen["low"])
        hi = float(chosen["high"])
        if direction == "bullish":
            # 收盘跌破区块下沿 → mitigated
            if last_close < lo:
                status = "mitigated"
            else:
                status = "active"
        else:
            if last_close > hi:
                status = "mitigated"
            else:
                status = "active"

        mid = (lo + hi) / 2.0
        blocks.append(
            {
                "direction": direction,
                "low": _round_px(lo),
                "high": _round_px(hi),
                "mid": _round_px(mid),
                "status": status,
                "source_event": ev.get("event_key") or ev.get("type"),
                "event_type": ev.get("type"),
                "bar_date": chosen.get("date"),
                "bar_index": chosen.get("index"),
                "event_bar_date": ev.get("bar_date"),
                "distance_pct": round(abs(last_close - mid) / last_close * 100.0, 3)
                if last_close
                else None,
            }
        )

    # 近端优先：按事件顺序倒序去重（同区间合并），再按距现价排序截断
    blocks.reverse()
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for b in blocks:
        key = (b.get("direction"), b.get("low"), b.get("high"), b.get("bar_date"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(b)
    deduped.sort(key=lambda x: float(x.get("distance_pct") or 1e9))
    return deduped[: max(1, int(max_blocks))]


def detect_fvgs(
    ohlc: Sequence[Dict[str, Any]],
    *,
    atr: Optional[float] = None,
    max_fvgs: int = MAX_FVGS,
    atr_mult: float = FVG_ATR_MULT,
    min_pct: float = FVG_MIN_PCT,
) -> List[Dict[str, Any]]:
    """三连 K 线公允价值缺口。"""
    n = len(ohlc)
    if n < 3:
        return []
    last_close = float(ohlc[-1]["close"])
    min_gap = max(
        (float(atr) * atr_mult) if atr and atr > 0 else 0.0,
        last_close * float(min_pct),
    )
    found: List[Dict[str, Any]] = []

    for i in range(2, n):
        a = ohlc[i - 2]
        c = ohlc[i]
        # 看涨：i-2 高 < i 低
        if float(a["high"]) < float(c["low"]):
            gap_lo = float(a["high"])
            gap_hi = float(c["low"])
            height = gap_hi - gap_lo
            if height < min_gap:
                continue
            status = _fvg_fill_status(ohlc, i + 1, gap_lo, gap_hi, "bullish")
            found.append(
                {
                    "direction": "bullish",
                    "low": _round_px(gap_lo),
                    "high": _round_px(gap_hi),
                    "height": _round_px(height),
                    "status": status,
                    "start_date": a.get("date"),
                    "end_date": c.get("date"),
                    "bar_index": i,
                }
            )
        # 看跌：i-2 低 > i 高
        if float(a["low"]) > float(c["high"]):
            gap_hi = float(a["low"])
            gap_lo = float(c["high"])
            height = gap_hi - gap_lo
            if height < min_gap:
                continue
            status = _fvg_fill_status(ohlc, i + 1, gap_lo, gap_hi, "bearish")
            found.append(
                {
                    "direction": "bearish",
                    "low": _round_px(gap_lo),
                    "high": _round_px(gap_hi),
                    "height": _round_px(height),
                    "status": status,
                    "start_date": a.get("date"),
                    "end_date": c.get("date"),
                    "bar_index": i,
                }
            )

    # 优先 open/partial，再按时间近端
    def _rank(f: Dict[str, Any]) -> Tuple[int, int]:
        st = str(f.get("status") or "")
        pri = 0 if st == "open" else (1 if st == "partial" else 2)
        return (pri, -int(f.get("bar_index") or 0))

    found.sort(key=_rank)
    return found[: max(1, int(max_fvgs))]


def _fvg_fill_status(
    ohlc: Sequence[Dict[str, Any]],
    from_index: int,
    gap_lo: float,
    gap_hi: float,
    direction: str,
) -> str:
    touched = False
    for j in range(from_index, len(ohlc)):
        bar = ohlc[j]
        lo, hi = float(bar["low"]), float(bar["high"])
        if hi < gap_lo or lo > gap_hi:
            continue
        touched = True
        # 完全穿越：看涨 FVG 被向下完全穿过（low < gap_lo 且曾进入）；简化：收盘越过对侧
        close = float(bar["close"])
        if direction == "bullish" and close < gap_lo:
            return "filled"
        if direction == "bearish" and close > gap_hi:
            return "filled"
        # 整根覆盖区间
        if lo <= gap_lo and hi >= gap_hi:
            return "filled"
    return "partial" if touched else "open"


def event_to_bos_like(event: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """兼容旧 last_bos_like 字段。"""
    if not event:
        return None
    direction = str(event.get("direction") or "")
    if direction == "bullish":
        btype = "break_swing_high"
        label = "收盘越过近期摆动高点"
        if event.get("type") == "choch":
            label = "CHOCH：收盘越过摆动高点（空头语境转多）"
    else:
        btype = "break_swing_low"
        label = "收盘跌破近期摆动低点"
        if event.get("type") == "choch":
            label = "CHOCH：收盘跌破摆动低点（多头语境转空）"
    return {
        "type": btype,
        "label": label,
        "level": event.get("level"),
        "level_date": event.get("level_date"),
        "close": event.get("close"),
        "buffer_mult": BOS_BREAK_MULT_UP if direction == "bullish" else BOS_BREAK_MULT_DOWN,
        "excess_pct": event.get("excess_pct"),
        "smc_type": event.get("type"),
        "smc_event_key": event.get("event_key"),
        "direction": direction,
    }


def build_smc_summary(
    last_event: Optional[Dict[str, Any]],
    order_blocks: Sequence[Dict[str, Any]],
    fvgs: Sequence[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if last_event:
        et = str(last_event.get("type") or "").upper()
        ek = str(last_event.get("event_key") or "")
        direction = "多" if last_event.get("direction") == "bullish" else "空"
        lvl = last_event.get("level")
        parts.append(
            f"最近结构事件 {et}（{ek or direction}）"
            f"{f' @ {lvl}' if lvl is not None else ''}（{last_event.get('bar_date') or '--'}）"
        )
    active_ob = next((b for b in order_blocks if b.get("status") == "active"), None)
    if active_ob:
        d = "看涨" if active_ob.get("direction") == "bullish" else "看跌"
        parts.append(
            f"活跃{d}OB [{active_ob.get('low')}–{active_ob.get('high')}]"
        )
    open_fvg = next((f for f in fvgs if f.get("status") in ("open", "partial")), None)
    if open_fvg:
        d = "看涨" if open_fvg.get("direction") == "bullish" else "看跌"
        st = open_fvg.get("status")
        parts.append(
            f"{d}FVG({st}) [{open_fvg.get('low')}–{open_fvg.get('high')}]"
        )
    if not parts:
        return "暂无显著 CHOCH/BOS、活跃订单块或未填 FVG。"
    return "；".join(parts) + "。"


def analyze_smc(
    bars: Sequence[Dict[str, Any]],
    labeled_zigzag: Sequence[Dict[str, Any]],
    *,
    confirm_right: int = DEFAULT_CONFIRM_RIGHT,
    atr: Optional[float] = None,
    max_order_blocks: int = MAX_ORDER_BLOCKS,
    max_fvgs: int = MAX_FVGS,
) -> Dict[str, Any]:
    """完整 SMC 子集分析。"""
    ohlc = parse_ohlc_bars(bars)
    empty = {
        "ok": False,
        "structure_bias": "neutral",
        "events": [],
        "last_event": None,
        "order_blocks": [],
        "fvgs": [],
        "summary": "样本不足，暂无 SMC 结构事件。",
    }
    if len(ohlc) < 3 or len(labeled_zigzag) < 2:
        return empty

    if atr is None:
        atr = wilder_atr(_parsed_hlc_for_atr(ohlc))

    trend, _ = _trend_from_labels(labeled_zigzag)
    bias = trend_to_structure_bias(trend)
    events = detect_structure_events(
        ohlc, labeled_zigzag, confirm_right=confirm_right
    )
    last_event = events[-1] if events else None
    # 若历史扫描无事件，用最新收盘对全链做一次即时判定（与旧 last_bos_like 对齐）
    if last_event is None and ohlc:
        snap = _snapshot_last_event(ohlc[-1], labeled_zigzag, bias)
        if snap:
            events = [snap]
            last_event = snap

    order_blocks = detect_order_blocks(
        ohlc, events, max_blocks=max_order_blocks
    )
    fvgs = detect_fvgs(ohlc, atr=atr, max_fvgs=max_fvgs)
    summary = build_smc_summary(last_event, order_blocks, fvgs)

    return {
        "ok": True,
        "structure_bias": bias,
        "events": events[-12:],
        "last_event": last_event,
        "order_blocks": order_blocks,
        "fvgs": fvgs,
        "summary": summary,
        "params": {
            "confirm_right": int(confirm_right),
            "break_mult_up": BOS_BREAK_MULT_UP,
            "break_mult_down": BOS_BREAK_MULT_DOWN,
            "fvg_atr_mult": FVG_ATR_MULT,
            "fvg_min_pct": FVG_MIN_PCT,
            "max_order_blocks": int(max_order_blocks),
            "max_fvgs": int(max_fvgs),
        },
    }


def _snapshot_last_event(
    last_bar: Dict[str, Any],
    labeled: Sequence[Dict[str, Any]],
    bias: str,
) -> Optional[Dict[str, Any]]:
    close = float(last_bar["close"])
    last_high = _last_swing(labeled, "high")
    last_low = _last_swing(labeled, "low")
    candidates: List[Dict[str, Any]] = []
    if last_high is not None:
        lvl = float(last_high["price"])
        if close >= lvl * BOS_BREAK_MULT_UP:
            etype, direction, ekey = _classify_break(bias=bias, break_side="high")
            candidates.append(
                {
                    "type": etype,
                    "direction": direction,
                    "event_key": ekey,
                    "level": _round_px(lvl),
                    "level_date": last_high.get("date"),
                    "level_index": last_high.get("index"),
                    "bar_date": last_bar.get("date"),
                    "bar_index": last_bar.get("index"),
                    "close": _round_px(close),
                    "excess_pct": round((close / lvl - 1.0) * 100.0, 3),
                    "structure_bias": bias,
                    "leg_start_index": _leg_start_index(labeled, "bullish"),
                }
            )
    if last_low is not None:
        lvl = float(last_low["price"])
        if close <= lvl * BOS_BREAK_MULT_DOWN:
            etype, direction, ekey = _classify_break(bias=bias, break_side="low")
            candidates.append(
                {
                    "type": etype,
                    "direction": direction,
                    "event_key": ekey,
                    "level": _round_px(lvl),
                    "level_date": last_low.get("date"),
                    "level_index": last_low.get("index"),
                    "bar_date": last_bar.get("date"),
                    "bar_index": last_bar.get("index"),
                    "close": _round_px(close),
                    "excess_pct": round((close / lvl - 1.0) * 100.0, 3),
                    "structure_bias": bias,
                    "leg_start_index": _leg_start_index(labeled, "bearish"),
                }
            )
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda c: abs(float(c.get("excess_pct") or 0)))
