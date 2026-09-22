# -*- coding: utf-8 -*-
"""袋鼠尾（Kangaroo Tail）日线识别：看涨 / 看跌。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _bar_date(bar: Dict[str, Any]) -> str:
    raw = bar.get("date") if bar.get("date") is not None else bar.get("trade_date")
    return str(raw or "")[:10]


def _ma(closes: Sequence[float], n: int) -> Optional[float]:
    if n <= 0 or len(closes) < n:
        return None
    window = list(closes[-n:])
    if any(c is None or c <= 0 for c in window):
        return None
    return sum(window) / float(n)


def _score_hit(
    *,
    direction: str,
    shadow_ratio: float,
    range_pct: float,
    close_pos: float,
    body_ratio: float,
) -> float:
    """0–100 得分：影线主导度 + 振幅 + 收盘位置 + 实体瘦小。"""
    # 影线相对实体：2x→40，4x→60
    s1 = min(60.0, max(0.0, (shadow_ratio - 1.0) * 20.0))
    # 振幅：2%→10，6%→30
    s2 = min(30.0, max(0.0, (range_pct - 0.02) / 0.04 * 30.0))
    # 收盘位置：看涨越靠上越好，看跌越靠下越好
    if direction == "bullish":
        s3 = min(20.0, max(0.0, (close_pos - 0.5) * 40.0))
    else:
        s3 = min(20.0, max(0.0, (0.5 - close_pos) * 40.0))
    # 实体瘦：body/range 越小越好
    s4 = min(20.0, max(0.0, (1.0 / 3.0 - body_ratio) / (1.0 / 3.0) * 20.0))
    return round(min(100.0, s1 + s2 + s3 + s4), 2)


def detect_kangaroo_tail_bar(
    bar: Dict[str, Any],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    ma20: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """检测单根日线是否为袋鼠尾。返回命中 dict 或 None。"""
    cfg = dict(pattern_cfg or {})
    min_range_pct = float(cfg.get("min_range_pct") if cfg.get("min_range_pct") is not None else 0.02)
    max_body_ratio = float(cfg.get("max_body_ratio") if cfg.get("max_body_ratio") is not None else (1.0 / 3.0))
    shadow_body_mult = float(cfg.get("shadow_body_mult") if cfg.get("shadow_body_mult") is not None else 2.0)
    shadow_range_mult = float(
        cfg.get("shadow_range_mult") if cfg.get("shadow_range_mult") is not None else 0.5
    )
    opposite_shadow_body_mult = float(
        cfg.get("opposite_shadow_body_mult")
        if cfg.get("opposite_shadow_body_mult") is not None
        else 0.3
    )
    close_half = float(cfg.get("close_half_ratio") if cfg.get("close_half_ratio") is not None else 0.5)
    require_trend = bool(cfg.get("require_trend_filter", True))
    exclude_limit_board = bool(cfg.get("exclude_limit_board", True))
    directions = str(cfg.get("directions") or "both").strip().lower()
    if directions not in ("bullish", "bearish", "both"):
        directions = "both"

    o = _f(bar.get("open"))
    h = _f(bar.get("high"))
    lo = _f(bar.get("low"))
    c = _f(bar.get("close"))
    if o is None or h is None or lo is None or c is None:
        return None
    if min(o, h, lo, c) <= 0:
        return None
    if h < lo:
        h, lo = lo, h

    rng = h - lo
    if rng <= 0:
        return None
    if exclude_limit_board and abs(h - lo) / c < 1e-6:
        return None

    range_pct = rng / c
    if range_pct < min_range_pct:
        return None

    body = abs(c - o)
    body_ratio = body / rng
    if body_ratio > max_body_ratio:
        return None

    # 十字星兜底：实体极小用 range 比例判断
    body_for_ratio = body if body > 1e-8 else rng * 0.01
    lower_shadow = min(o, c) - lo
    upper_shadow = h - max(o, c)
    if lower_shadow < 0:
        lower_shadow = 0.0
    if upper_shadow < 0:
        upper_shadow = 0.0

    close_pos = (c - lo) / rng
    date_s = _bar_date(bar)

    candidates: List[Dict[str, Any]] = []

    # ---- 看涨：长下影 ----
    if directions in ("bullish", "both"):
        need_lower = max(body_for_ratio * shadow_body_mult, rng * shadow_range_mult)
        opp_ok = upper_shadow <= body_for_ratio * opposite_shadow_body_mult
        close_ok = close_pos >= close_half
        trend_ok = True
        if require_trend and ma20 is not None and ma20 > 0:
            trend_ok = lo < ma20
        if lower_shadow >= need_lower and opp_ok and close_ok and trend_ok:
            shadow_ratio = lower_shadow / body_for_ratio
            score = _score_hit(
                direction="bullish",
                shadow_ratio=shadow_ratio,
                range_pct=range_pct,
                close_pos=close_pos,
                body_ratio=body_ratio,
            )
            candidates.append(
                {
                    "pattern_type": "kangaroo_tail_bullish",
                    "direction": "bullish",
                    "status": "hit",
                    "signal_date": date_s,
                    "score": score,
                    "open": o,
                    "high": h,
                    "low": lo,
                    "close": c,
                    "body": round(body, 6),
                    "lower_shadow": round(lower_shadow, 6),
                    "upper_shadow": round(upper_shadow, 6),
                    "range_pct": round(range_pct * 100.0, 4),
                    "body_ratio": round(body_ratio, 4),
                    "close_pos": round(close_pos, 4),
                    "shadow_ratio": round(shadow_ratio, 4),
                    "ma20": ma20,
                    "last_close": c,
                }
            )

    # ---- 看跌：长上影 ----
    if directions in ("bearish", "both"):
        need_upper = max(body_for_ratio * shadow_body_mult, rng * shadow_range_mult)
        opp_ok = lower_shadow <= body_for_ratio * opposite_shadow_body_mult
        close_ok = close_pos <= (1.0 - close_half)
        trend_ok = True
        if require_trend and ma20 is not None and ma20 > 0:
            trend_ok = h > ma20
        if upper_shadow >= need_upper and opp_ok and close_ok and trend_ok:
            shadow_ratio = upper_shadow / body_for_ratio
            score = _score_hit(
                direction="bearish",
                shadow_ratio=shadow_ratio,
                range_pct=range_pct,
                close_pos=close_pos,
                body_ratio=body_ratio,
            )
            candidates.append(
                {
                    "pattern_type": "kangaroo_tail_bearish",
                    "direction": "bearish",
                    "status": "hit",
                    "signal_date": date_s,
                    "score": score,
                    "open": o,
                    "high": h,
                    "low": lo,
                    "close": c,
                    "body": round(body, 6),
                    "lower_shadow": round(lower_shadow, 6),
                    "upper_shadow": round(upper_shadow, 6),
                    "range_pct": round(range_pct * 100.0, 4),
                    "body_ratio": round(body_ratio, 4),
                    "close_pos": round(close_pos, 4),
                    "shadow_ratio": round(shadow_ratio, 4),
                    "ma20": ma20,
                    "last_close": c,
                }
            )

    if not candidates:
        return None
    # 理论上不会同时满足双向；若同时取得分更高者
    candidates.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return candidates[0]


def detect_kangaroo_tail(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """从升序日线 bars 检测最近一根（末根）袋鼠尾。"""
    cfg = dict(pattern_cfg or {})
    ma_period = max(5, int(cfg.get("ma_period") or 20))
    lookback_signal = max(1, int(cfg.get("lookback_signal_bars") or 1))

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) < ma_period:
        return None

    # 在最近 lookback_signal_bars 根内找最新命中（默认只看末日）
    start = max(ma_period - 1, len(seq) - lookback_signal)
    best: Optional[Dict[str, Any]] = None
    for i in range(start, len(seq)):
        closes = [_f(b.get("close")) or 0.0 for b in seq[: i + 1]]
        ma20 = _ma(closes, ma_period)
        hit = detect_kangaroo_tail_bar(seq[i], pattern_cfg=cfg, ma20=ma20)
        if hit:
            best = hit  # 保留时间上更靠后的
    return best


def detect_kangaroo_tails_in_bars(
    bars: Sequence[Dict[str, Any]],
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    max_hits: int = 5,
) -> List[Dict[str, Any]]:
    """扫描窗口内多根袋鼠尾（供形态工具），按日期倒序。"""
    cfg = dict(pattern_cfg or {})
    ma_period = max(5, int(cfg.get("ma_period") or 20))
    seq = [b for b in (bars or []) if isinstance(b, dict)]
    if len(seq) < ma_period:
        return []
    hits: List[Dict[str, Any]] = []
    for i in range(ma_period - 1, len(seq)):
        closes = [_f(b.get("close")) or 0.0 for b in seq[: i + 1]]
        ma20 = _ma(closes, ma_period)
        hit = detect_kangaroo_tail_bar(seq[i], pattern_cfg=cfg, ma20=ma20)
        if not hit:
            continue
        # 形态工具标准字段
        hit = dict(hit)
        hit["formed_at"] = hit.get("signal_date")
        hit["confidence"] = min(0.99, float(hit.get("score") or 0) / 100.0)
        hit["key_levels"] = {
            "high": hit.get("high"),
            "low": hit.get("low"),
            "close": hit.get("close"),
        }
        hit["pivots"] = [
            {
                "date": hit.get("signal_date"),
                "price": hit.get("low") if hit.get("direction") == "bullish" else hit.get("high"),
                "role": "tail",
            }
        ]
        hits.append(hit)
    hits.sort(key=lambda h: str(h.get("signal_date") or ""), reverse=True)
    if max_hits > 0:
        hits = hits[:max_hits]
    return hits
