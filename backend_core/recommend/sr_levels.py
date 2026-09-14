"""筹码峰支撑阻力：Volume Profile + 近端极值校验。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.recommend.config import (
    SR_BAND_PCT_HIGH,
    SR_BAND_PCT_LOW,
    SR_EXTREMA_LOOKBACK,
    SR_VP_LOOKBACK,
    SR_VP_MAX_CODES,
)

logger = logging.getLogger(__name__)


def _load_bars(
    db: Session, codes: Sequence[str], asof_date: str, lookback: int
) -> Dict[str, List[Dict[str, Any]]]:
    if not codes:
        return {}
    # 多取一些交易日
    limit_days = max(int(lookback) + 10, 70)
    out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in codes}
    try:
        rows = db.execute(
            text(
                """
                SELECT code, date::text, open, high, low, close, volume
                FROM historical_quotes
                WHERE code IN :codes
                  AND date <= :asof
                ORDER BY code, date DESC
                """
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": list(codes), "asof": asof_date},
        ).fetchall()
        counts: Dict[str, int] = {}
        for r in rows:
            code = str(r[0]).strip()
            if code not in out:
                continue
            n = counts.get(code, 0)
            if n >= limit_days:
                continue
            counts[code] = n + 1
            out[code].append(
                {
                    "date": str(r[1])[:10] if r[1] else None,
                    "open": float(r[2]) if r[2] is not None else None,
                    "high": float(r[3]) if r[3] is not None else None,
                    "low": float(r[4]) if r[4] is not None else None,
                    "close": float(r[5]) if r[5] is not None else None,
                    "volume": float(r[6]) if r[6] is not None else None,
                }
            )
        for c in out:
            out[c] = list(reversed(out[c]))
    except Exception as e:
        logger.warning("sr_levels load bars failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def _extrema_support_resistance(
    bars: List[Dict[str, Any]], lookback: int
) -> Dict[str, Optional[float]]:
    seq = bars[-max(5, lookback) :] if bars else []
    lows = [float(b["low"]) for b in seq if b.get("low") is not None]
    highs = [float(b["high"]) for b in seq if b.get("high") is not None]
    return {
        "ext_support": min(lows) if lows else None,
        "ext_resistance": max(highs) if highs else None,
    }


def _score_sr(close: Optional[float], p_sup: Optional[float], p_res: Optional[float]) -> float:
    if close is None or p_sup is None:
        return 0.0
    try:
        c = float(close)
        s = float(p_sup)
    except (TypeError, ValueError):
        return 0.0
    if s <= 0:
        return 0.0
    # 贴近支撑：距离越小分越高；跌破支撑大幅降分
    dist = (c - s) / s
    if dist < -0.03:
        return 10.0
    if dist < 0:
        return 40.0
    # 0~8% 内线性 100→40
    if dist <= 0.08:
        return round(100.0 - dist / 0.08 * 60.0, 2)
    # 靠近阻力也给一点结构分
    if p_res is not None:
        try:
            r = float(p_res)
            if r > c:
                up = (r - c) / c
                if up <= 0.05:
                    return 55.0
        except (TypeError, ValueError):
            pass
    return 25.0


def build_floating_zones(
    p_sup: Optional[float],
    p_res: Optional[float],
    *,
    band_low: float = SR_BAND_PCT_LOW,
    band_high: float = SR_BAND_PCT_HIGH,
) -> Dict[str, Any]:
    if p_sup is None:
        return {"buy_zone": None, "stop_zone": None}
    try:
        s = float(p_sup)
    except (TypeError, ValueError):
        return {"buy_zone": None, "stop_zone": None}
    lo = s * (1.0 - float(band_high))
    hi = s * (1.0 + float(band_low))
    buy_zone = {"low": round(lo, 3), "price": round(s, 3), "high": round(hi, 3), "label": "VP支撑区"}
    stop = s * (1.0 - float(band_high))
    stop_zone = {"price": round(stop, 3), "label": "VP支撑下沿"}
    take = None
    if p_res is not None:
        try:
            take = {"price": round(float(p_res), 3), "label": "VP阻力"}
        except (TypeError, ValueError):
            take = None
    return {"buy_zone": buy_zone, "stop_zone": stop_zone, "take_profit": take}


def compute_sr_for_codes(
    db: Session,
    codes: Sequence[str],
    asof_date: str,
    *,
    quotes: Optional[Dict[str, Dict[str, Any]]] = None,
    max_codes: int = SR_VP_MAX_CODES,
) -> Dict[str, Dict[str, Any]]:
    """code -> {p_sup, p_res, s_sr, buy_zone, stop_zone, take_profit, ok}。"""
    from backend_core.analysis.volume_profile import compute_volume_profile_from_bars

    uniq = []
    for c in codes:
        s = str(c or "").strip()
        if s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        if s and s not in uniq:
            uniq.append(s)
    uniq = uniq[: max(1, int(max_codes))]
    bars_map = _load_bars(db, uniq, asof_date, SR_VP_LOOKBACK)
    out: Dict[str, Dict[str, Any]] = {}
    for code in uniq:
        bars = bars_map.get(code) or []
        close = None
        if quotes and quotes.get(code) and quotes[code].get("close") is not None:
            close = quotes[code]["close"]
        elif bars:
            close = bars[-1].get("close")
        try:
            vp = compute_volume_profile_from_bars(
                bars, last_close=close, lookback=SR_VP_LOOKBACK
            )
        except Exception as e:
            logger.debug("VP failed %s: %s", code, e)
            vp = {"ok": False}
        ext = _extrema_support_resistance(bars, SR_EXTREMA_LOOKBACK)
        p_sup = vp.get("nearest_support") if isinstance(vp, dict) else None
        p_res = vp.get("nearest_resistance") if isinstance(vp, dict) else None
        # 极值二次校验：取更近的下方支撑 / 上方阻力
        try:
            if close is not None:
                c = float(close)
                es = ext.get("ext_support")
                er = ext.get("ext_resistance")
                if es is not None and es < c:
                    if p_sup is None or abs(c - float(es)) < abs(c - float(p_sup)):
                        p_sup = float(es)
                if er is not None and er > c:
                    if p_res is None or abs(float(er) - c) < abs(float(p_res) - c):
                        p_res = float(er)
        except (TypeError, ValueError):
            pass
        zones = build_floating_zones(p_sup, p_res)
        s_sr = _score_sr(close, p_sup, p_res)
        out[code] = {
            "ok": bool(isinstance(vp, dict) and vp.get("ok")),
            "p_sup": round(float(p_sup), 3) if p_sup is not None else None,
            "p_res": round(float(p_res), 3) if p_res is not None else None,
            "s_sr": s_sr,
            "buy_zone": zones.get("buy_zone"),
            "stop_zone": zones.get("stop_zone"),
            "take_profit": zones.get("take_profit"),
            "vp_poc": (vp or {}).get("poc") if isinstance(vp, dict) else None,
        }
    return out


def merge_advice_with_sr(
    advice: Dict[str, Any],
    sr: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """策略价位优先；缺失时用 VP 浮动区补齐。"""
    out = dict(advice or {})
    if not sr:
        return out
    if not out.get("buy_zone") and sr.get("buy_zone"):
        out["buy_zone"] = sr["buy_zone"]
    if not out.get("stop_zone") and sr.get("stop_zone"):
        out["stop_zone"] = sr["stop_zone"]
    if not out.get("take_profit") and sr.get("take_profit"):
        out["take_profit"] = sr["take_profit"]
    return out
