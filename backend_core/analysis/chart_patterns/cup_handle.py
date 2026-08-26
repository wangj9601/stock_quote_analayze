# -*- coding: utf-8 -*-
"""带柄茶杯形态：与管理端 CUPB 策略共用 detect_cup_bottom 算法。

前复权检测时可用 ref_bars（不复权）按枢轴日回填展示价，与管理端 CUPB 对齐。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend_core.strategies.cup_bottom.config import get_default_cupb_config, merge_pattern_cfg

from .pivots import extract_pivot_sequence
from .schema import fmt_px, make_hit


def _cup_pattern_cfg(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """形态工具默认与管理端 CUPB 默认参数一致；保留 invalidated 供前端统计。"""
    base = merge_pattern_cfg(get_default_cupb_config())
    base["exclude_invalidated"] = False
    if override:
        base.update(override)
    return base


def _bar_date(bar: Dict[str, Any]) -> str:
    raw = bar.get("date") if bar.get("date") is not None else bar.get("trade_date")
    return str(raw or "")[:10]


def _ohlc_by_date(bars: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        d = _bar_date(b)
        if not d:
            continue
        row: Dict[str, float] = {}
        for k in ("high", "low", "close"):
            try:
                fv = float(b.get(k))
                if fv == fv and fv > 0:
                    row[k] = fv
            except (TypeError, ValueError):
                pass
        if row:
            out[d] = row
    return out


def _sync_cup_prices_from_ref_bars(
    hit: Dict[str, Any],
    ref_bars: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """按枢轴日从不复权 ref_bars 取 OHLC，使展示价与管理端 CUPB 一致。"""
    by_date = _ohlc_by_date(ref_bars)
    if not by_date:
        return hit

    out = dict(hit)
    qfq_prices: Dict[str, float] = {}
    field_map = (
        ("left_rim_date", "left_rim_price", "high"),
        ("cup_bottom_date", "cup_bottom_price", "low"),
        ("right_rim_date", "right_rim_price", "high"),
        ("handle_low_date", "handle_low_price", "low"),
    )
    for date_key, price_key, ohlc_key in field_map:
        d = str(out.get(date_key) or "")[:10]
        row = by_date.get(d) or {}
        ref_px = row.get(ohlc_key) or row.get("close")
        if ref_px is None:
            continue
        try:
            qfq_prices[price_key] = float(out.get(price_key))
        except (TypeError, ValueError):
            pass
        out[price_key] = round(float(ref_px), 4)

    left = float(out["left_rim_price"])
    bottom = float(out["cup_bottom_price"])
    right = float(out["right_rim_price"])
    handle_low = float(out["handle_low_price"])
    rim = round(max(left, right), 4)
    out["rim"] = rim

    if ref_bars:
        try:
            last_ref = float((ref_bars[-1] or {}).get("close"))
            if last_ref == last_ref and last_ref > 0:
                out["last_close"] = round(last_ref, 4)
        except (TypeError, ValueError, IndexError):
            pass

    depth = rim - bottom
    handle_retrace = rim - handle_low
    out["cup_depth_pct"] = round(depth / rim * 100, 2) if rim > 0 else None
    out["handle_retrace_pct"] = (
        round(handle_retrace / depth * 100, 2) if depth > 0 else None
    )
    if qfq_prices:
        out["_qfq_prices"] = qfq_prices
    out["_cup_price_basis"] = "unadjusted_ref"
    return out


def detect_cup_with_handle(
    bars: Sequence[Dict[str, Any]],
    pivots: Optional[List[Dict[str, Any]]] = None,
    *,
    pattern_cfg: Optional[Dict[str, Any]] = None,
    ref_bars: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """检测带柄茶杯；无命中返回空列表。"""
    from backend_core.strategies.cup_bottom.detector import detect_cup_bottom

    seq = [b for b in (bars or []) if isinstance(b, dict)]
    _ = pivots if pivots is not None else extract_pivot_sequence(seq)

    hit = detect_cup_bottom(seq, pattern_cfg=_cup_pattern_cfg(pattern_cfg))
    if not hit:
        return []

    if ref_bars:
        hit = _sync_cup_prices_from_ref_bars(hit, ref_bars)

    left = float(hit["left_rim_price"])
    bottom = float(hit["cup_bottom_price"])
    right = float(hit["right_rim_price"])
    handle_low = float(hit["handle_low_price"])
    rim = float(hit["rim"])
    last_c = float(hit["last_close"])
    status = str(hit.get("status") or "forming")
    grade = str(hit.get("grade") or "")

    if status == "confirmed":
        conf = {"A": 0.68, "B": 0.60, "C": 0.52}.get(grade, 0.60)
    elif status == "invalidated":
        conf = 0.22
    else:
        conf = {"A": 0.50, "B": 0.46, "C": 0.40}.get(grade, 0.46)

    reason = (
        f"带柄茶杯"
        f"{f'[{grade}级]' if grade else ''} "
        f"{fmt_px('左沿', hit['left_rim_price'], hit.get('left_rim_date'))} "
        f"{fmt_px('杯底', hit['cup_bottom_price'], hit.get('cup_bottom_date'))} "
        f"{fmt_px('右沿', hit['right_rim_price'], hit.get('right_rim_date'))} "
        f"{fmt_px('柄低', hit['handle_low_price'], hit.get('handle_low_date'))} "
        f"杯深={hit.get('cup_depth_pct')}% "
        f"柄回撤={hit.get('handle_retrace_pct')}%杯深"
    )
    if status == "confirmed" and hit.get("confirm_date"):
        reason = f"{reason} 确认日={hit['confirm_date']}"
    vs = hit.get("volume_score")
    if vs is not None:
        reason = f"{reason} 量价分={vs}/4"

    extra: Dict[str, Any] = {
        "confirm_date": hit.get("confirm_date"),
        "handle_end_date": hit.get("handle_end_date"),
        "cupb_aligned": True,
        "grade": grade or None,
        "volume_score": hit.get("volume_score"),
        "volume_flags": hit.get("volume_flags"),
        "quality_flags": hit.get("quality_flags"),
    }
    if hit.get("_cup_price_basis"):
        extra["cup_price_basis"] = hit["_cup_price_basis"]
    if hit.get("_qfq_prices"):
        extra["qfq_prices"] = hit["_qfq_prices"]

    return [
        make_hit(
            pattern_family="cup_handle",
            pattern_type="cup_with_handle",
            status=status,
            confidence=conf,
            reason=reason,
            key_levels={
                "upper": round(rim, 4),
                "lower": round(handle_low, 4),
                "rim": round(rim, 4),
                "cup_bottom": round(bottom, 4),
                "left_rim": round(left, 4),
                "right_rim": round(right, 4),
                "handle_low": round(handle_low, 4),
                "last_close": round(last_c, 4),
                "cup_depth_pct": hit.get("cup_depth_pct"),
                "handle_retrace_pct_of_cup": hit.get("handle_retrace_pct"),
                "handle_retrace_of_rim_pct": hit.get("handle_retrace_of_rim_pct"),
                "grade": grade or None,
                "volume_score": hit.get("volume_score"),
            },
            pivots=[
                {"role": "left_rim", "date": hit.get("left_rim_date"), "price": left},
                {"role": "cup_bottom", "date": hit.get("cup_bottom_date"), "price": bottom},
                {"role": "right_rim", "date": hit.get("right_rim_date"), "price": right},
                {"role": "handle_low", "date": hit.get("handle_low_date"), "price": handle_low},
            ],
            extra=extra,
        )
    ]
