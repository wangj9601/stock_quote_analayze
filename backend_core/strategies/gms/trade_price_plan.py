"""
GMS 交易观察 / 正式交易：买入价、止损价、止盈价与参考卖点计算。
与回测规则对齐：T+1 开盘价入场、百分比止损兜底、目标涨幅止盈。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend_core.strategies.gms.backtest_runner import (
    _get_entry_open_next_day_cn,
    _get_entry_open_next_day_etf,
    _get_entry_open_next_day_hk,
)
from backend_core.strategies.gms.config import GMSConfigManager

DEFAULT_TARGET_PCT = 0.05
DEFAULT_STOP_LOSS_PCT = 0.05


def _round_price(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 4)


def _market_key(market: Optional[str], code: str) -> str:
    m = (market or "").strip().upper()
    if m in ("CN", "HK", "ETF"):
        return m.lower() if m == "ETF" else ("hk" if m == "HK" else "cn")
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return "hk"
    return "cn"


def _get_entry_open_next_day(
    db: Session,
    market: str,
    code: str,
    signal_date: str,
) -> Optional[float]:
    mk = _market_key(market, code)
    if mk == "etf":
        return _get_entry_open_next_day_etf(db, code, signal_date)
    if mk == "hk":
        return _get_entry_open_next_day_hk(db, code, signal_date)
    return _get_entry_open_next_day_cn(db, code, signal_date)


def _resolve_d20(snapshot: Dict[str, Any]) -> Optional[float]:
    raw = snapshot.get("d_ma20")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    sd = snapshot.get("score_detail")
    if isinstance(sd, dict):
        for key in ("d20", "d"):
            raw = sd.get(key)
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    continue
    return None


def _resolve_signal_close(snapshot: Dict[str, Any]) -> Optional[float]:
    raw = snapshot.get("current_price")
    if raw is not None:
        try:
            v = float(raw)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return None


def _resolve_buy_type(snapshot: Dict[str, Any]) -> str:
    bt = str(snapshot.get("buy_type") or "").strip()
    if bt in ("左侧", "右侧"):
        return bt
    if snapshot.get("left_buy_signal"):
        return "左侧"
    if snapshot.get("right_buy_signal"):
        return "右侧"
    return ""


def _effective_stop_loss_pct(stop_loss_pct: float) -> float:
    pct = float(stop_loss_pct or 0)
    return pct if pct > 0 else DEFAULT_STOP_LOSS_PCT


def _resolve_overbought_ratio(overbought_ratio: Optional[float]) -> float:
    if overbought_ratio is not None:
        return float(overbought_ratio)
    try:
        cfg = GMSConfigManager().get_config()
        exit_cfg = cfg.get("exit") or {}
        return float(exit_cfg.get("overbought_ratio", 0.15))
    except Exception:
        return 0.15


def compute_price_plan(
    db: Session,
    *,
    market: str,
    code: str,
    signal_date: date,
    snapshot: Optional[Dict[str, Any]] = None,
    target_pct: float = DEFAULT_TARGET_PCT,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
    overbought_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    """
    计算 GMS 交易价格计划。

    返回字段：buy_price_suggested、buy_price_source、buy_price_alt、
    stop_loss_price、take_profit_price、reference_sell_price、params、notes、computed_at。
    """
    snap = snapshot if isinstance(snapshot, dict) else {}
    signal_date_str = signal_date.strftime("%Y-%m-%d") if hasattr(signal_date, "strftime") else str(signal_date)[:10]
    buy_type = _resolve_buy_type(snap)
    signal_close = _resolve_signal_close(snap)
    d20 = _resolve_d20(snap)
    ob_ratio = _resolve_overbought_ratio(overbought_ratio)
    eff_stop_pct = _effective_stop_loss_pct(stop_loss_pct)
    tgt_pct = float(target_pct or DEFAULT_TARGET_PCT)

    notes: list[str] = []
    t1_open = _get_entry_open_next_day(db, market, code, signal_date_str)

    if t1_open is not None and t1_open > 0:
        entry = float(t1_open)
        buy_source = "t_plus_1_open"
    elif signal_close is not None and signal_close > 0:
        entry = signal_close
        buy_source = "signal_close"
        notes.append("T+1 开盘价暂不可用，已用信号日收盘价作为建议买入价")
    else:
        entry = None
        buy_source = "unavailable"
        notes.append("无法获取 T+1 开盘价或信号日收盘价，暂无法给出建议买入价")

    buy_price_alt: Dict[str, Any] = {}
    if buy_type == "左侧" and d20 is not None and d20 > 0:
        buy_price_alt["conservative_ma20"] = _round_price(d20)
        notes.append("左侧备选：可关注 MA20 附近分批吸纳")
    elif buy_type == "右侧" and signal_close is not None and signal_close > 0:
        buy_price_alt["signal_close"] = _round_price(signal_close)
        notes.append("右侧备选：信号日收盘已站稳均线上方，可作突破参考")

    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    reference_sell_price: Optional[float] = None

    if entry is not None and entry > 0:
        stop_loss_price = entry * (1.0 - eff_stop_pct)
        if stop_loss_price >= entry:
            stop_loss_price = entry * 0.99
        take_profit_price = entry * (1.0 + tgt_pct)

    if d20 is not None and d20 > 0:
        reference_sell_price = d20 * (1.0 + ob_ratio)

    return {
        "buy_price_suggested": _round_price(entry),
        "buy_price_source": buy_source,
        "buy_price_alt": buy_price_alt,
        "stop_loss_price": _round_price(stop_loss_price),
        "take_profit_price": _round_price(take_profit_price),
        "reference_sell_price": _round_price(reference_sell_price),
        "params": {
            "target_pct": tgt_pct,
            "stop_loss_pct": eff_stop_pct,
            "overbought_ratio": ob_ratio,
            "buy_type": buy_type or None,
            "signal_date": signal_date_str,
        },
        "notes": notes,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
    }


def attach_price_plan_to_snapshot(
    db: Session,
    snapshot: Optional[Dict[str, Any]],
    *,
    market: str,
    code: str,
    signal_date: date,
) -> Dict[str, Any]:
    """在快照 dict 中写入/覆盖 price_plan 字段。"""
    snap = dict(snapshot) if isinstance(snapshot, dict) else {}
    plan = compute_price_plan(
        db,
        market=market,
        code=code,
        signal_date=signal_date,
        snapshot=snap,
    )
    snap["price_plan"] = plan
    return snap
