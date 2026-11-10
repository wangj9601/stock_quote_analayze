# -*- coding: utf-8 -*-
"""日线 SMC 子集：CHOCH/BOS、订单块（OB）、公允价值缺口（FVG）。

复用 ZigZag 标注点与收盘破位缓冲；不替代形态 tactical，不入策略硬筛。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.analysis.swing_zigzag import PRICE_DECIMALS, wilder_atr

# 与 market_structure 破位缓冲对齐（避免循环导入，常量本地维护）
# 未给 ATR 时仍用 0.5% 下限；给出 ATR 后取 max(0.5%, 0.3×ATR/价位)。
BOS_BREAK_FLOOR_PCT = 0.005
BOS_BREAK_ATR_FRAC = 0.3
BOS_BREAK_MULT_UP = 1.0 + BOS_BREAK_FLOOR_PCT
BOS_BREAK_MULT_DOWN = 1.0 - BOS_BREAK_FLOOR_PCT

_EVENT_KEY_ZH = {
    "structure_shift_unconfirmed": "结构位移未确认",
    "choch_bullish": "看涨性质转换",
    "choch_bearish": "看跌性质转换",
    "bos_bullish": "看涨结构延续",
    "bos_bearish": "看跌结构延续",
}
_ZONE_STATUS_ZH = {
    "active": "活跃",
    "open": "未回补",
    "partial": "部分回补",
    "filled": "已回补",
    "mitigated": "已缓解",
}
FVG_ATR_MULT = 0.15
FVG_MIN_PCT = 0.003
MAX_ORDER_BLOCKS = 6
MAX_FVGS = 8
DEFAULT_CONFIRM_RIGHT = 2
# 同向区间重叠比例（重叠长度 / 较窄区高度）≥ 该阈值即合并；包含关系记 1.0。
# 设为 > 1.0 可关闭合并（如 1.01）。
ZONE_MERGE_OVERLAP_RATIO = 0.5
# 区间 mid 距现价超过该百分比 → relevance=remote（历史残余，默认折叠）
REMOTE_DISTANCE_PCT = 20.0

STRUCTURE_BIAS_LABELS = {
    "bullish": "看涨",
    "bearish": "看跌",
    "neutral": "中性",
}
STRUCTURE_BIAS_NOTE = (
    "结构偏向由 HH/HL 趋势映射，单次 CHOCH/BOS 不会立刻改写；"
    "出现 choch 与偏向相反时表示「已有性质转换迹象，大结构尚未确认翻转」。"
)


def _trend_from_labels(points: Sequence[Dict[str, Any]]):
    from backend_core.analysis.market_structure import _trend_from_labels as _fn

    return _fn(points)


def structure_bias_meta(bias: str) -> Dict[str, str]:
    """结构偏向展示元数据：与 last_event/CHOCH 解耦，避免 UI 误读为同步翻转。"""
    b = str(bias or "").strip().lower()
    if b not in STRUCTURE_BIAS_LABELS:
        b = "neutral"
    return {
        "structure_bias": b,
        "structure_bias_label": STRUCTURE_BIAS_LABELS[b],
        "structure_bias_basis": "hh_hl_trend",
        "structure_bias_note": STRUCTURE_BIAS_NOTE,
    }


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


def _apply_zone_relevance(
    zones: Sequence[Dict[str, Any]],
    *,
    last_close: float,
    remote_pct: float = REMOTE_DISTANCE_PCT,
) -> None:
    """就地标注 relevance=near|remote；remote 表示远离现价的历史残余。"""
    thr = max(0.0, float(remote_pct))
    for z in zones:
        mid = _f(z.get("mid"))
        if mid is None:
            lo, hi = _f(z.get("low")), _f(z.get("high"))
            if lo is not None and hi is not None:
                mid = (lo + hi) / 2.0
                z["mid"] = _round_px(mid)
        dist = _f(z.get("distance_pct"))
        if dist is None and mid is not None and last_close:
            dist = abs(float(mid) - float(last_close)) / float(last_close) * 100.0
            z["distance_pct"] = round(dist, 3)
        if dist is not None and float(dist) >= thr:
            z["relevance"] = "remote"
        else:
            z["relevance"] = "near"


def _sort_zones_near_first(
    zones: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """near 优先，同组内按 _recency_key 新→旧。"""
    near = [z for z in zones if z.get("relevance") != "remote"]
    remote = [z for z in zones if z.get("relevance") == "remote"]
    near.sort(key=_recency_key, reverse=True)
    remote.sort(key=_recency_key, reverse=True)
    return near + remote


def _last_swing(
    points: Sequence[Dict[str, Any]], kind: str
) -> Optional[Dict[str, Any]]:
    for p in reversed(points):
        if p.get("kind") == kind and p.get("price") is not None:
            return p
    return None


def event_key_zh(key: Optional[str]) -> str:
    k = str(key or "").strip()
    return _EVENT_KEY_ZH.get(k, k)


def zone_status_zh(status: Optional[str], relevance: Optional[str] = None) -> str:
    raw = str(status or "").strip()
    label = _ZONE_STATUS_ZH.get(raw, raw)
    if str(relevance or "") == "remote":
        label = f"{label}·远离现价" if label else "远离现价"
    return label or "--"


def break_buffer_pct(level: float, atr: Optional[float]) -> float:
    """破位缓冲比例：max(0.5%, 0.3×ATR/价位)。ATR 为价格单位。"""
    pct = BOS_BREAK_FLOOR_PCT
    try:
        lvl = abs(float(level))
        a = float(atr) if atr is not None else 0.0
    except (TypeError, ValueError):
        return pct
    if lvl > 0 and a > 0:
        pct = max(BOS_BREAK_FLOOR_PCT, BOS_BREAK_ATR_FRAC * a / lvl)
    return pct


def adaptive_break_mults(
    level: float,
    atr: Optional[float],
    *,
    break_mult_up: float = BOS_BREAK_MULT_UP,
    break_mult_down: float = BOS_BREAK_MULT_DOWN,
) -> Tuple[float, float]:
    """显式改写倍数时尊重调用方；否则在有 ATR 时按波动率放大缓冲。"""
    custom = (
        abs(float(break_mult_up) - BOS_BREAK_MULT_UP) > 1e-12
        or abs(float(break_mult_down) - BOS_BREAK_MULT_DOWN) > 1e-12
    )
    if custom or atr is None:
        return float(break_mult_up), float(break_mult_down)
    pct = break_buffer_pct(level, atr)
    return 1.0 + pct, 1.0 - pct


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
    atr: Optional[float] = None,
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
            up_m, _down_m = adaptive_break_mults(
                lvl, atr, break_mult_up=break_mult_up, break_mult_down=break_mult_down
            )
            thr = lvl * up_m
            if key not in broken_high_keys and close >= thr:
                etype, direction, ekey = _classify_break(bias=bias, break_side="high")
                candidates.append(
                    {
                        "type": etype,
                        "direction": direction,
                        "event_key": ekey,
                        "event_key_label": event_key_zh(ekey),
                        "buffer_mult": round(up_m, 6),
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
            _up_m, down_m = adaptive_break_mults(
                lvl, atr, break_mult_up=break_mult_up, break_mult_down=break_mult_down
            )
            thr = lvl * down_m
            if key not in broken_low_keys and close <= thr:
                etype, direction, ekey = _classify_break(bias=bias, break_side="low")
                candidates.append(
                    {
                        "type": etype,
                        "direction": direction,
                        "event_key": ekey,
                        "event_key_label": event_key_zh(ekey),
                        "buffer_mult": round(down_m, 6),
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
    """由结构事件回溯冲动腿内最后反向 K，生成 OB（原始列表；合并/降权在 analyze_smc）。"""
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

    # 近端优先：按事件顺序倒序去重，再按日期新→旧截断
    blocks.reverse()
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for b in blocks:
        key = (b.get("direction"), b.get("low"), b.get("high"), b.get("bar_date"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(b)
    deduped.sort(
        key=lambda x: (
            str(x.get("bar_date") or x.get("event_bar_date") or ""),
            int(x.get("bar_index") or 0),
        ),
        reverse=True,
    )
    return deduped[: max(1, int(max_blocks))]


def detect_fvgs(
    ohlc: Sequence[Dict[str, Any]],
    *,
    atr: Optional[float] = None,
    max_fvgs: int = MAX_FVGS,
    atr_mult: float = FVG_ATR_MULT,
    min_pct: float = FVG_MIN_PCT,
) -> List[Dict[str, Any]]:
    """三连 K 线公允价值缺口（原始列表；合并/降权在 analyze_smc）。"""
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
            mid = (gap_lo + gap_hi) / 2.0
            found.append(
                {
                    "direction": "bullish",
                    "low": _round_px(gap_lo),
                    "high": _round_px(gap_hi),
                    "mid": _round_px(mid),
                    "height": _round_px(height),
                    "status": status,
                    "start_date": a.get("date"),
                    "end_date": c.get("date"),
                    "bar_index": i,
                    "distance_pct": round(abs(last_close - mid) / last_close * 100.0, 3)
                    if last_close
                    else None,
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
            mid = (gap_lo + gap_hi) / 2.0
            found.append(
                {
                    "direction": "bearish",
                    "low": _round_px(gap_lo),
                    "high": _round_px(gap_hi),
                    "mid": _round_px(mid),
                    "height": _round_px(height),
                    "status": status,
                    "start_date": a.get("date"),
                    "end_date": c.get("date"),
                    "bar_index": i,
                    "distance_pct": round(abs(last_close - mid) / last_close * 100.0, 3)
                    if last_close
                    else None,
                }
            )

    # 按形成日新→旧；同日用 bar_index 近端优先
    found.sort(
        key=lambda f: (
            str(f.get("end_date") or f.get("start_date") or ""),
            int(f.get("bar_index") or 0),
        ),
        reverse=True,
    )
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


def _zone_overlap_ratio(
    a_lo: float, a_hi: float, b_lo: float, b_hi: float
) -> float:
    """重叠长度 / 较窄区间高度；包含关系记 1.0，无重叠记 0。"""
    inter = min(a_hi, b_hi) - max(a_lo, b_lo)
    if inter <= 0:
        return 0.0
    base = min(a_hi - a_lo, b_hi - b_lo)
    if base <= 0:
        return 0.0
    return inter / base


def _merge_by_overlap(
    zones: Sequence[Dict[str, Any]],
    *,
    min_overlap_ratio: float,
    group_key,
) -> List[List[Dict[str, Any]]]:
    """并查集：同组（同方向）且重叠达标者归为一簇。区间数 <= 十余条，O(n^2) 足够。"""
    n = len(zones)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if group_key(zones[i]) != group_key(zones[j]):
                continue
            if (
                _zone_overlap_ratio(
                    float(zones[i]["low"]),
                    float(zones[i]["high"]),
                    float(zones[j]["low"]),
                    float(zones[j]["high"]),
                )
                >= min_overlap_ratio
            ):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(zones[i])
    return list(groups.values())


def _recency_key(z: Dict[str, Any]) -> Tuple[str, int]:
    return (
        str(z.get("bar_date") or z.get("event_bar_date") or z.get("end_date") or ""),
        int(z.get("bar_index") or 0),
    )


_SOURCE_PRIORITY = {
    "choch_bullish": 3,
    "choch_bearish": 3,
    "bos_bullish": 2,
    "bos_bearish": 2,
}


def _pick_source_event(members: Sequence[Dict[str, Any]]) -> Optional[str]:
    """合并区来源：结构意义更强的优先（choch > bos > unconfirmed），同级取最近。"""

    def key(m: Dict[str, Any]):
        src = str(m.get("source_event") or m.get("event_type") or "")
        return (_SOURCE_PRIORITY.get(src, 1), _recency_key(m))

    return str(max(members, key=key).get("source_event") or max(members, key=key).get("event_type") or "") or None


def merge_order_blocks(
    blocks: Sequence[Dict[str, Any]],
    *,
    limit: Optional[int] = None,
    last_close: Optional[float] = None,
    min_overlap_ratio: float = ZONE_MERGE_OVERLAP_RATIO,
) -> List[Dict[str, Any]]:
    """同向重叠订单块合并为一条带，消除语义重复的阻力/支撑带。

    - 仅合并同向；重叠比例 >= min_overlap_ratio（> 1.0 视为关闭）
    - 合并后区间取并集；状态 active 优先；来源 choch > bos > unconfirmed
    - 合并簇追加 merged_count / merged_from（原始区间列表），单条区不动原字段
    """
    items: List[Dict[str, Any]] = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        lo = _f(b.get("low"))
        hi = _f(b.get("high"))
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        z = dict(b)
        z["low"], z["high"] = lo, hi
        items.append(z)
    if not items:
        return []
    if float(min_overlap_ratio) > 1.0:
        out = list(items)
    else:
        clusters = _merge_by_overlap(
            items,
            min_overlap_ratio=float(min_overlap_ratio),
            group_key=lambda z: str(z.get("direction") or ""),
        )
        out = [_finalize_merged_ob(c, last_close=last_close) for c in clusters]

    out.sort(key=_recency_key, reverse=True)
    if limit is not None:
        out = out[: max(1, int(limit))]
    return out


def _finalize_merged_ob(
    members: Sequence[Dict[str, Any]], *, last_close: Optional[float]
) -> Dict[str, Any]:
    if len(members) == 1:
        return dict(members[0])
    lo = min(float(m["low"]) for m in members)
    hi = max(float(m["high"]) for m in members)
    newest = max(members, key=_recency_key)
    merged = dict(newest)
    merged["low"] = _round_px(lo)
    merged["high"] = _round_px(hi)
    merged["mid"] = _round_px((lo + hi) / 2.0)
    merged["status"] = "active" if any(m.get("status") == "active" for m in members) else "mitigated"
    src = _pick_source_event(members)
    if src:
        merged["source_event"] = src
    if last_close:
        merged["distance_pct"] = round(
            abs(float(last_close) - (lo + hi) / 2.0) / float(last_close) * 100.0, 3
        )
    merged["merged_count"] = len(members)
    merged["merged_from"] = sorted(
        [[_round_px(m["low"]), _round_px(m["high"])] for m in members],
        key=lambda r: (r[0] if r[0] is not None else 0.0),
    )
    return merged


def merge_fvgs(
    fvgs: Sequence[Dict[str, Any]],
    *,
    limit: Optional[int] = None,
    min_overlap_ratio: float = ZONE_MERGE_OVERLAP_RATIO,
) -> List[Dict[str, Any]]:
    """同向重叠 FVG 合并为一条缺口带；状态 open > partial > filled。"""
    items: List[Dict[str, Any]] = []
    for f in fvgs or []:
        if not isinstance(f, dict):
            continue
        lo = _f(f.get("low"))
        hi = _f(f.get("high"))
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        z = dict(f)
        z["low"], z["high"] = lo, hi
        items.append(z)
    if not items:
        return []
    if float(min_overlap_ratio) > 1.0:
        out = list(items)
    else:
        clusters = _merge_by_overlap(
            items,
            min_overlap_ratio=float(min_overlap_ratio),
            group_key=lambda z: str(z.get("direction") or ""),
        )
        out = [_finalize_merged_fvg(c) for c in clusters]

    out.sort(key=_recency_key, reverse=True)
    if limit is not None:
        out = out[: max(1, int(limit))]
    return out


_FVG_STATUS_PRIORITY = {"open": 3, "partial": 2, "filled": 1}


def _finalize_merged_fvg(members: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if len(members) == 1:
        return dict(members[0])
    lo = min(float(m["low"]) for m in members)
    hi = max(float(m["high"]) for m in members)
    newest = max(members, key=_recency_key)
    merged = dict(newest)
    merged["low"] = _round_px(lo)
    merged["high"] = _round_px(hi)
    merged["mid"] = _round_px((lo + hi) / 2.0)
    merged["height"] = _round_px(hi - lo)
    merged["status"] = max(
        (str(m.get("status") or "filled") for m in members),
        key=lambda s: _FVG_STATUS_PRIORITY.get(s, 0),
    )
    starts = [str(m.get("start_date")) for m in members if m.get("start_date")]
    merged["start_date"] = min(starts) if starts else newest.get("start_date")
    merged["merged_count"] = len(members)
    merged["merged_from"] = sorted(
        [[_round_px(m["low"]), _round_px(m["high"])] for m in members],
        key=lambda r: (r[0] if r[0] is not None else 0.0),
    )
    return merged


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
        "buffer_mult": event.get("buffer_mult")
        if event.get("buffer_mult") is not None
        else (BOS_BREAK_MULT_UP if direction == "bullish" else BOS_BREAK_MULT_DOWN),
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
        ek = event_key_zh(str(last_event.get("event_key") or ""))
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
        st = zone_status_zh(open_fvg.get("status"))
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
    zone_merge_ratio: float = ZONE_MERGE_OVERLAP_RATIO,
    remote_pct: float = REMOTE_DISTANCE_PCT,
) -> Dict[str, Any]:
    """完整 SMC 子集分析。"""
    ohlc = parse_ohlc_bars(bars)
    empty = {
        "ok": False,
        "events": [],
        "last_event": None,
        "order_blocks": [],
        "fvgs": [],
        "summary": "样本不足，暂无 SMC 结构事件。",
    }
    empty.update(structure_bias_meta("neutral"))
    if len(ohlc) < 3 or len(labeled_zigzag) < 2:
        return empty

    if atr is None:
        atr = wilder_atr(_parsed_hlc_for_atr(ohlc))

    trend, _ = _trend_from_labels(labeled_zigzag)
    bias = trend_to_structure_bias(trend)
    bias_meta = structure_bias_meta(bias)
    events = detect_structure_events(
        ohlc, labeled_zigzag, confirm_right=confirm_right, atr=atr
    )
    last_event = events[-1] if events else None
    # 若历史扫描无事件，用最新收盘对全链做一次即时判定（与旧 last_bos_like 对齐）
    if last_event is None and ohlc:
        snap = _snapshot_last_event(ohlc[-1], labeled_zigzag, bias, atr=atr)
        if snap:
            events = [snap]
            last_event = snap

    last_close = float(ohlc[-1]["close"])
    # 先多取再合并/降权，避免截断吃掉可合并成员
    raw_obs = detect_order_blocks(
        ohlc, events, max_blocks=max(3, int(max_order_blocks) * 3)
    )
    order_blocks = merge_order_blocks(
        raw_obs,
        limit=None,
        last_close=last_close,
        min_overlap_ratio=zone_merge_ratio,
    )
    raw_fvgs = detect_fvgs(ohlc, atr=atr, max_fvgs=max(4, int(max_fvgs) * 3))
    fvgs = merge_fvgs(raw_fvgs, limit=None, min_overlap_ratio=zone_merge_ratio)
    _apply_zone_relevance(order_blocks, last_close=last_close, remote_pct=remote_pct)
    _apply_zone_relevance(fvgs, last_close=last_close, remote_pct=remote_pct)
    order_blocks = _sort_zones_near_first(order_blocks)[: max(1, int(max_order_blocks))]
    fvgs = _sort_zones_near_first(fvgs)[: max(1, int(max_fvgs))]
    summary = build_smc_summary(last_event, order_blocks, fvgs)

    return {
        "ok": True,
        **bias_meta,
        "events": events[-12:],
        "last_event": last_event,
        "order_blocks": order_blocks,
        "fvgs": fvgs,
        "summary": summary,
        "params": {
            "confirm_right": int(confirm_right),
            "break_mult_up": BOS_BREAK_MULT_UP,
            "break_mult_down": BOS_BREAK_MULT_DOWN,
            "break_floor_pct": BOS_BREAK_FLOOR_PCT,
            "break_atr_frac": BOS_BREAK_ATR_FRAC,
            "break_buffer_pct": round(break_buffer_pct(last_close, atr), 6),
            "fvg_atr_mult": FVG_ATR_MULT,
            "fvg_min_pct": FVG_MIN_PCT,
            "max_order_blocks": int(max_order_blocks),
            "max_fvgs": int(max_fvgs),
            "zone_merge_ratio": float(zone_merge_ratio),
            "remote_distance_pct": float(remote_pct),
        },
    }


def _snapshot_last_event(
    last_bar: Dict[str, Any],
    labeled: Sequence[Dict[str, Any]],
    bias: str,
    *,
    atr: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    close = float(last_bar["close"])
    last_high = _last_swing(labeled, "high")
    last_low = _last_swing(labeled, "low")
    candidates: List[Dict[str, Any]] = []
    if last_high is not None:
        lvl = float(last_high["price"])
        up_m, _down_m = adaptive_break_mults(lvl, atr)
        if close >= lvl * up_m:
            etype, direction, ekey = _classify_break(bias=bias, break_side="high")
            candidates.append(
                {
                    "type": etype,
                    "direction": direction,
                    "event_key": ekey,
                    "event_key_label": event_key_zh(ekey),
                    "buffer_mult": round(up_m, 6),
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
        _up_m, down_m = adaptive_break_mults(lvl, atr)
        if close <= lvl * down_m:
            etype, direction, ekey = _classify_break(bias=bias, break_side="low")
            candidates.append(
                {
                    "type": etype,
                    "direction": direction,
                    "event_key": ekey,
                    "event_key_label": event_key_zh(ekey),
                    "buffer_mult": round(down_m, 6),
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
