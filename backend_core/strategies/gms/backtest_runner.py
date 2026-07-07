"""
GMS 策略回测执行器
按「信号日后 N 个交易日内最高价是否达到 entry*(1+target_pct)」计算目标命中率（准确率）。

买入价 entry：信号日之后的**下一交易日开盘价**（T+1 开盘），非信号日收盘价。

与管理端 GMS 回测任务共用同一套逻辑：每个交易日取 GMS 左/右侧买入信号，
经 GMSFrontendInterface 按最低总分筛选后计入样本（单股仅股票池缩为该代码）。
同一标的在上一笔的观察期（horizon_days 根 K 线，与命中率统计一致）结束后才允许再次开仓。
股票池不少于 2 只时：每个交易日、每个市场一次批量拉取该池在该市场的全部代码（与单市场按日扫描同量级调用）；全市场无固定池时按交易日扫描。
"""

import logging
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Tuple
from sqlalchemy.orm import Session

from .frontend_interface import GMSFrontendInterface
from .backtest_storage import normalize_gms_stock_code

logger = logging.getLogger(__name__)


def _progress_pct(processed: int, total_steps: int) -> int:
    """按步数换算进度百分比，限制在 0–100。"""
    if total_steps <= 0:
        return 0
    return min(100, max(0, int(100 * processed / total_steps)))


def _get_trading_dates_cn(db: Session, start: str, end: str) -> List[str]:
    """A股在 [start,end] 内的所有交易日，升序。

    注意：历史原因，数据库中 historical_quotes.date 实际类型可能为 TEXT，
    为避免出现「text >= date」类型不兼容错误，这里统一按字符串比较。
    """
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    start_str = str(start).strip()[:10]
    end_str = str(end).strip()[:10]

    rows = (
        db.query(HistoricalQuotes.date)
        .filter(
            cast(HistoricalQuotes.date, String) >= start_str,
            cast(HistoricalQuotes.date, String) <= end_str,
        )
        .distinct()
        .order_by(HistoricalQuotes.date)
        .all()
    )
    return [str(r[0])[:10] for r in rows if r[0]]


def _get_trading_dates_hk(db: Session, start: str, end: str) -> List[str]:
    """港股在 [start,end] 内的所有交易日，升序。"""
    from backend_api.models import HistoricalQuotesHK
    rows = (
        db.query(HistoricalQuotesHK.date)
        .filter(HistoricalQuotesHK.date >= start, HistoricalQuotesHK.date <= end)
        .distinct()
        .order_by(HistoricalQuotesHK.date)
        .all()
    )
    return [str(r[0]).strip()[:10] for r in rows if r[0]]


def _get_entry_open_next_day_cn(db: Session, code: str, signal_date: str) -> Optional[float]:
    """信号日之后首个交易日的开盘价（买入价）。"""
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    after_str = str(signal_date).strip()[:10]
    row = (
        db.query(HistoricalQuotes.open)
        .filter(
            HistoricalQuotes.code == code,
            cast(HistoricalQuotes.date, String) > after_str,
        )
        .order_by(HistoricalQuotes.date)
        .first()
    )
    if row and row[0] is not None:
        return float(row[0])
    return None


def _get_entry_open_next_day_hk(db: Session, code: str, signal_date: str) -> Optional[float]:
    """信号日之后首个交易日的开盘价（买入价）。"""
    from backend_api.models import HistoricalQuotesHK

    after_str = str(signal_date).strip()[:10]
    row = (
        db.query(HistoricalQuotesHK.open)
        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date > after_str)
        .order_by(HistoricalQuotesHK.date)
        .first()
    )
    if row and row[0] is not None:
        return float(row[0])
    return None


def _get_future_ohlc_cn(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    """信号日之后 limit 个交易日 OHLC（含 date），按日期升序。"""
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    after_str = str(after_date).strip()[:10]
    rows = (
        db.query(HistoricalQuotes.date, HistoricalQuotes.open, HistoricalQuotes.high, HistoricalQuotes.low, HistoricalQuotes.close)
        .filter(
            HistoricalQuotes.code == code,
            cast(HistoricalQuotes.date, String) > after_str,
        )
        .order_by(HistoricalQuotes.date)
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        dt = str(r[0])[:10] if r[0] is not None else ""
        if not dt:
            continue
        out.append(
            {
                "date": dt,
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
            }
        )
    return out


def _get_future_ohlc_hk(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    from backend_api.models import HistoricalQuotesHK
    rows = (
        db.query(HistoricalQuotesHK.date, HistoricalQuotesHK.open, HistoricalQuotesHK.high, HistoricalQuotesHK.low, HistoricalQuotesHK.close)
        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date > after_date)
        .order_by(HistoricalQuotesHK.date)
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        dt = str(r[0]).strip()[:10] if r[0] is not None else ""
        if not dt:
            continue
        out.append(
            {
                "date": dt,
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
            }
        )
    return out


def _get_observation_window_end_cn(
    db: Session, code: str, signal_date: str, horizon_days: int
) -> Optional[str]:
    """信号日之后第 horizon_days 根 K 线所在日期（与 _get_future_highs_cn 取数范围一致，观察期最后一根）。"""
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    after_str = str(signal_date).strip()[:10]
    rows = (
        db.query(HistoricalQuotes.date)
        .filter(
            HistoricalQuotes.code == code,
            cast(HistoricalQuotes.date, String) > after_str,
        )
        .order_by(HistoricalQuotes.date)
        .limit(horizon_days)
        .all()
    )
    if not rows:
        return None
    return str(rows[-1][0])[:10]


def _get_observation_window_end_hk(
    db: Session, code: str, signal_date: str, horizon_days: int
) -> Optional[str]:
    """信号日之后第 horizon_days 根 K 线所在日期（与 _get_future_highs_hk 一致）。"""
    from backend_api.models import HistoricalQuotesHK

    after_str = str(signal_date).strip()[:10]
    rows = (
        db.query(HistoricalQuotesHK.date)
        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date > after_str)
        .order_by(HistoricalQuotesHK.date)
        .limit(horizon_days)
        .all()
    )
    if not rows:
        return None
    return str(rows[-1][0]).strip()[:10]


def _get_entry_open_next_day_etf(db: Session, code: str, signal_date: str) -> Optional[float]:
    """ETF: 信号日之后首个交易日的开盘价（买入价）。"""
    from backend_api.models import FundHistoricalQuotes

    after_str = str(signal_date).strip()[:10]
    row = (
        db.query(FundHistoricalQuotes.open)
        .filter(FundHistoricalQuotes.code == code, FundHistoricalQuotes.date > after_str)
        .order_by(FundHistoricalQuotes.date)
        .first()
    )
    if row and row[0] is not None:
        return float(row[0])
    return None


def _get_future_ohlc_etf(db: Session, code: str, after_date: str, limit: int) -> List[Dict[str, Any]]:
    """ETF: 信号日之后 limit 个交易日 OHLC（含 date），按日期升序。"""
    from backend_api.models import FundHistoricalQuotes

    after_str = str(after_date).strip()[:10]
    rows = (
        db.query(FundHistoricalQuotes.date, FundHistoricalQuotes.open, FundHistoricalQuotes.high, FundHistoricalQuotes.low, FundHistoricalQuotes.close)
        .filter(FundHistoricalQuotes.code == code, FundHistoricalQuotes.date > after_str)
        .order_by(FundHistoricalQuotes.date)
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        dt = str(r[0]).strip()[:10] if r[0] is not None else ""
        if not dt:
            continue
        out.append(
            {
                "date": dt,
                "open": float(r[1]) if r[1] is not None else None,
                "high": float(r[2]) if r[2] is not None else None,
                "low": float(r[3]) if r[3] is not None else None,
                "close": float(r[4]) if r[4] is not None else None,
            }
        )
    return out


def _get_observation_window_end_etf(
    db: Session, code: str, signal_date: str, horizon_days: int
) -> Optional[str]:
    """ETF: 信号日之后第 horizon_days 根 K 线所在日期。"""
    from backend_api.models import FundHistoricalQuotes

    after_str = str(signal_date).strip()[:10]
    rows = (
        db.query(FundHistoricalQuotes.date)
        .filter(FundHistoricalQuotes.code == code, FundHistoricalQuotes.date > after_str)
        .order_by(FundHistoricalQuotes.date)
        .limit(horizon_days)
        .all()
    )
    if not rows:
        return None
    return str(rows[-1][0]).strip()[:10]


def _aggregate_details_to_summary(
    details: List[Dict[str, Any]],
    start_str: str,
    end_str: str,
    market: str,
    target_pct: float,
    horizon_days: int,
    buy_signal_rule: str,
) -> Dict[str, Any]:
    """由明细列表生成 summary 与完整返回结构。"""
    total_samples = len(details)
    hit_count = sum(1 for d in details if d.get("hit"))
    hit_rate = (hit_count / total_samples) if total_samples else 0.0

    by_buy_type: Dict[str, Dict[str, Any]] = {}
    for d in details:
        bt = d.get("buy_type") or "其他"
        if bt not in by_buy_type:
            by_buy_type[bt] = {"total": 0, "hit": 0}
        by_buy_type[bt]["total"] += 1
        if d.get("hit"):
            by_buy_type[bt]["hit"] += 1
    for v in by_buy_type.values():
        v["hit_rate"] = (v["hit"] / v["total"]) if v["total"] else 0.0

    by_score_bucket: Dict[str, Dict[str, Any]] = {}
    for d in details:
        s = d.get("score_total")
        if s is None:
            bucket = "未知"
        elif s < 60:
            bucket = "[0,60)"
        elif s < 70:
            bucket = "[60,70)"
        elif s < 80:
            bucket = "[70,80)"
        elif s < 90:
            bucket = "[80,90)"
        else:
            bucket = "[90,100]"
        if bucket not in by_score_bucket:
            by_score_bucket[bucket] = {"total": 0, "hit": 0}
        by_score_bucket[bucket]["total"] += 1
        if d.get("hit"):
            by_score_bucket[bucket]["hit"] += 1
    for v in by_score_bucket.values():
        v["hit_rate"] = (v["hit"] / v["total"]) if v["total"] else 0.0

    summary: Dict[str, Any] = {
        "summary_schema_version": 2,
        "total_samples": total_samples,
        "hit_count": hit_count,
        "hit_rate": round(hit_rate, 4),
        "target_pct": target_pct,
        "horizon_days": horizon_days,
        "start_date": start_str,
        "end_date": end_str,
        "market": market,
        "buy_signal_rule": buy_signal_rule,
        "by_buy_type": by_buy_type,
        "by_score_bucket": by_score_bucket,
        "holding_days_histogram": _holding_days_histogram(
            [{"bars_held": d.get("horizon_days") or horizon_days} for d in details]
        ),
    }
    return {"summary": summary, "details": details}


def _simulate_trade_exit(
    entry_open: float,
    bars: List[Dict[str, Any]],
    target_pct: float,
    stop_loss_pct: float,
    commission_bps: float,
    slippage_bps: float,
    atr_period: int,
    init_stop_atr_k: float,
    trail_stop_mode: str,
    trail_atr_k: float,
    trail_pct: float,
    breakeven_trigger_r: float,
    profit_lock_trigger_r: float,
    profit_lock_r: float,
    partial_take_profit_r: float,
    partial_take_ratio: float,
    time_stop_bars: int,
) -> Dict[str, Any]:
    """
    利润最大化 + 移动止损：
    1) 初始止损（仅百分比）
    2) 达到 breakeven_trigger_r 后抬保本
    3) 达到 profit_lock_trigger_r 后锁盈到 +profit_lock_r * R
    4) 启用百分比跟踪止损（不使用 ATR）
    5) 可选分批止盈（在 partial_take_profit_r 处）
    6) 时间止损：超过 time_stop_bars 且未达到 +1R，按收盘离场
    """
    if not bars:
        comm = float(commission_bps or 0) / 10000.0
        slip = float(slippage_bps or 0) / 10000.0
        entry_exec = entry_open * (1.0 + slip + comm)
        exit_exec = entry_open * (1.0 - slip - comm)
        pnl_pct = (exit_exec / entry_exec - 1.0) if entry_exec > 0 else 0.0
        return {
            "exit_price": round(float(entry_open), 4),
            "exit_date": "",
            "exit_reason": "时间出场",
            "bars_held": 0,
            "entry_exec_price": round(entry_exec, 4),
            "exit_exec_price": round(exit_exec, 4),
            "pnl_pct": round(pnl_pct, 6),
            "partial_take_profit_applied": False,
            "partial_take_ratio": 0.0,
            "r_multiple": 0.0,
            "initial_risk_pct": 0.0,
            "initial_stop_price": round(float(entry_open), 4),
            "max_favorable_excursion_pct": 0.0,
            "max_adverse_excursion_pct": 0.0,
        }

    highs = [float(b["high"]) for b in bars if b.get("high") is not None]
    if not highs:
        highs = [entry_open]
    pct_stop = entry_open * (1.0 - float(stop_loss_pct or 0)) if float(stop_loss_pct or 0) > 0 else None
    # 简化交易策略：仅使用百分比止损，不再使用 ATR/结构止损
    initial_stop = pct_stop if pct_stop is not None else entry_open * 0.95
    if initial_stop >= entry_open:
        initial_stop = entry_open * 0.99

    initial_risk = max(1e-8, entry_open - initial_stop)
    tp_price = entry_open * (1.0 + target_pct)
    highest = entry_open
    stop_line = initial_stop
    partial_hit = False
    final_pnl = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason = "时间出场"
    bars_held = 0
    mfe = 0.0
    mae = 0.0

    for i, b in enumerate(bars, start=1):
        bars_held = i
        high = float(b.get("high")) if b.get("high") is not None else entry_open
        low = float(b.get("low")) if b.get("low") is not None else entry_open
        close = float(b.get("close")) if b.get("close") is not None else entry_open
        d = str(b.get("date") or "")
        highest = max(highest, high)
        mfe = max(mfe, highest / entry_open - 1.0)
        mae = min(mae, low / entry_open - 1.0)

        r_now = (highest - entry_open) / initial_risk if initial_risk > 0 else 0.0
        if r_now >= float(breakeven_trigger_r or 0):
            stop_line = max(stop_line, entry_open)
        if r_now >= float(profit_lock_trigger_r or 0):
            stop_line = max(stop_line, entry_open + float(profit_lock_r or 0) * initial_risk)
        trail_line = highest * (1.0 - float(trail_pct or 0))
        stop_line = max(stop_line, trail_line)

        if (not partial_hit) and r_now >= float(partial_take_profit_r or 0):
            partial_hit = True

        if low <= stop_line:
            exit_price = float(stop_line)
            exit_date = d
            exit_reason = "止损"
            break
        if high >= tp_price and float(partial_take_ratio or 0) <= 0:
            exit_price = float(tp_price)
            exit_date = d
            exit_reason = "止盈"
            break
        if int(time_stop_bars or 0) > 0 and i >= int(time_stop_bars or 0) and r_now < 1.0:
            exit_price = close
            exit_date = d
            exit_reason = "时间止损"
            break

    if exit_price is None:
        last = bars[-1]
        close_v = last.get("close")
        exit_price = float(close_v) if close_v is not None and float(close_v) > 0 else entry_open
        exit_date = str(last.get("date") or "")
        bars_held = len(bars)
        exit_reason = "时间出场"

    comm = float(commission_bps or 0) / 10000.0
    slip = float(slippage_bps or 0) / 10000.0
    entry_exec = float(entry_open) * (1.0 + slip + comm)
    exit_exec_total = float(exit_price) * (1.0 - slip - comm)

    part_ratio = min(1.0, max(0.0, float(partial_take_ratio or 0)))
    if partial_hit and part_ratio > 0:
        partial_exec = tp_price * (1.0 - slip - comm)
        remain = 1.0 - part_ratio
        blended_exit_exec = part_ratio * partial_exec + remain * exit_exec_total
    else:
        blended_exit_exec = exit_exec_total
        part_ratio = 0.0
    pnl_pct = (blended_exit_exec / entry_exec - 1.0) if entry_exec > 0 else 0.0
    r_multiple = ((float(exit_price) - entry_open) / initial_risk) if initial_risk > 0 else 0.0

    return {
        "exit_price": round(float(exit_price), 4),
        "exit_date": exit_date,
        "exit_reason": exit_reason,
        "bars_held": int(max(0, bars_held)),
        "entry_exec_price": round(entry_exec, 4),
        "exit_exec_price": round(blended_exit_exec, 4),
        "pnl_pct": round(pnl_pct, 6),
        "partial_take_profit_applied": bool(partial_hit and part_ratio > 0),
        "partial_take_ratio": round(part_ratio, 4),
        "r_multiple": round(r_multiple, 6),
        "initial_risk_pct": round(initial_risk / entry_open, 6) if entry_open > 0 else 0.0,
        "initial_stop_price": round(initial_stop, 4),
        "max_favorable_excursion_pct": round(mfe, 6),
        "max_adverse_excursion_pct": round(mae, 6),
    }


def _clamp_position_fraction(raw: Any) -> float:
    """单笔仓位占组合权益比例，(0,1]；非法或不在范围内时按 1（全仓）。"""
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if f <= 0 or f > 1:
        return 1.0
    return f


def _calendar_days_inclusive(start_str: str, end_str: str) -> int:
    """回测区间自然日天数（含首尾），至少为 1。"""
    try:
        da = datetime.strptime(str(start_str).strip()[:10], "%Y-%m-%d").date()
        db = datetime.strptime(str(end_str).strip()[:10], "%Y-%m-%d").date()
        return max(1, (db - da).days + 1)
    except Exception:
        return 1


def _holding_days_histogram(details: List[Dict[str, Any]]) -> Dict[str, int]:
    buckets = {"1-3": 0, "4-10": 0, "11-20": 0, "21+": 0}
    for d in details:
        bars = int(d.get("bars_held") or 0)
        if bars <= 3:
            buckets["1-3"] += 1
        elif bars <= 10:
            buckets["4-10"] += 1
        elif bars <= 20:
            buckets["11-20"] += 1
        else:
            buckets["21+"] += 1
    return buckets


def _monthly_returns_from_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_month: Dict[str, List[float]] = {}
    for d in details:
        dt = str(d.get("exit_date") or d.get("date") or "")[:7]
        if len(dt) < 7:
            continue
        pnl = float(d.get("portfolio_pnl_pct") if d.get("portfolio_pnl_pct") is not None else d.get("pnl_pct") or 0)
        by_month.setdefault(dt, []).append(pnl)
    out = []
    for month in sorted(by_month.keys()):
        vals = by_month[month]
        out.append(
            {
                "month": month,
                "return_pct": round(sum(vals), 6),
                "trade_count": len(vals),
            }
        )
    return out


def _by_signal_type_stats(details: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[str, Dict[str, Any]] = {}
    for d in details:
        sig = str(d.get("buy_type") or d.get("signal_type") or "未知").strip() or "未知"
        if sig not in groups:
            groups[sig] = {"count": 0, "wins": 0, "pnl_sum": 0.0, "r_sum": 0.0}
        g = groups[sig]
        g["count"] += 1
        pnl = float(d.get("pnl_pct") or 0)
        g["pnl_sum"] += pnl
        if pnl > 0:
            g["wins"] += 1
        g["r_sum"] += float(d.get("r_multiple") or 0)
    for sig, g in groups.items():
        cnt = g["count"] or 1
        g["win_rate"] = round(g["wins"] / cnt, 4)
        g["avg_pnl_pct"] = round(g["pnl_sum"] / cnt, 6)
        g["avg_r_multiple"] = round(g["r_sum"] / cnt, 6)
    return groups


def _annotate_trade_position_pnl(details: List[Dict[str, Any]], position_fraction: float) -> None:
    """写入 position_fraction 与 portfolio_pnl_pct（单笔收益率×仓位），供净值与导出。"""
    f = _clamp_position_fraction(position_fraction)
    for d in details:
        r = float(d.get("pnl_pct") or 0)
        d["position_fraction"] = round(f, 6)
        d["portfolio_pnl_pct"] = round(f * r, 6)


def _aggregate_trade_summary(
    details: List[Dict[str, Any]],
    start_str: str,
    end_str: str,
    market: str,
    target_pct: float,
    horizon_days: int,
    buy_signal_rule: str,
    stop_loss_pct: float,
    commission_bps: float,
    slippage_bps: float,
    trail_stop_mode: str,
    trail_atr_k: float,
    trail_pct: float,
    breakeven_trigger_r: float,
    profit_lock_trigger_r: float,
    profit_lock_r: float,
    partial_take_profit_r: float,
    partial_take_ratio: float,
    time_stop_bars: int,
    position_fraction: float = 1.0,
) -> Dict[str, Any]:
    def _quantile(vals: List[float], q: float) -> float:
        if not vals:
            return 0.0
        arr = sorted(vals)
        pos = (len(arr) - 1) * q
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        if lo == hi:
            return float(arr[lo])
        w = pos - lo
        return float(arr[lo] * (1 - w) + arr[hi] * w)

    total_trades = len(details)
    wins = [float(d.get("pnl_pct") or 0) for d in details if float(d.get("pnl_pct") or 0) > 0]
    losses = [float(d.get("pnl_pct") or 0) for d in details if float(d.get("pnl_pct") or 0) < 0]
    win_rate = (len(wins) / total_trades) if total_trades else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    gross_profit = sum(wins)
    gross_loss_abs = abs(sum(losses))
    pf = _clamp_position_fraction(position_fraction)
    total_return_arithmetic = sum(
        float(d.get("portfolio_pnl_pct")) if d.get("portfolio_pnl_pct") is not None else pf * float(d.get("pnl_pct") or 0)
        for d in details
    )
    cal_days = _calendar_days_inclusive(start_str, end_str)
    # 近似年化：算术累计按自然日线性折算到 365 天（不假设收益时间分布，仅供参考）
    approx_annual_return_simple = total_return_arithmetic * (365.0 / float(cal_days))
    avg_portfolio_pnl_per_trade = (total_return_arithmetic / total_trades) if total_trades else 0.0
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else (math.inf if gross_profit > 0 else 0.0)
    avg_hold_bars = (sum(int(d.get("bars_held") or 0) for d in details) / total_trades) if total_trades else 0.0
    max_win = max(wins) if wins else 0.0
    pnl_all = [float(d.get("pnl_pct") or 0) for d in details]
    r_all = [float(d.get("r_multiple") or 0) for d in details]

    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    dd_recovery_bars = 0
    in_recovery = False
    cur_recovery = 0
    equity_curve: List[Dict[str, Any]] = []
    ordered = sorted(details, key=lambda d: (str(d.get("entry_date") or d.get("date") or ""), str(d.get("code") or "")))
    for i, d in enumerate(ordered, start=1):
        r_port = (
            float(d.get("portfolio_pnl_pct"))
            if d.get("portfolio_pnl_pct") is not None
            else pf * float(d.get("pnl_pct") or 0)
        )
        eq *= (1.0 + r_port)
        if eq > peak:
            peak = eq
            if in_recovery:
                dd_recovery_bars = max(dd_recovery_bars, cur_recovery)
                in_recovery = False
                cur_recovery = 0
        dd = (eq / peak - 1.0) if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
        if dd < 0:
            in_recovery = True
            cur_recovery += 1
        equity_curve.append({"step": i, "equity": round(eq, 6), "drawdown": round(dd, 6)})
    if in_recovery:
        dd_recovery_bars = max(dd_recovery_bars, cur_recovery)

    by_exit_reason: Dict[str, int] = {}
    for d in details:
        rs = str(d.get("exit_reason") or "unknown")
        by_exit_reason[rs] = by_exit_reason.get(rs, 0) + 1

    summary: Dict[str, Any] = {
        "summary_schema_version": 2,
        "backtest_type": "trade_simulation",
        "position_fraction": round(pf, 6),
        "total_trades": total_trades,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 6),
        "avg_loss": round(avg_loss, 6),
        "profit_factor": (round(profit_factor, 6) if math.isfinite(profit_factor) else None),
        "total_return_compound": round(eq - 1.0, 6),
        "total_return_arithmetic": round(total_return_arithmetic, 6),
        "backtest_calendar_days": int(cal_days),
        "approx_annual_return_simple": round(approx_annual_return_simple, 6),
        "avg_portfolio_pnl_per_trade": round(avg_portfolio_pnl_per_trade, 6),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_recovery_bars": int(dd_recovery_bars),
        "target_pct": target_pct,
        "horizon_days": horizon_days,
        "stop_loss_pct": float(stop_loss_pct or 0),
        "commission_bps": float(commission_bps or 0),
        "slippage_bps": float(slippage_bps or 0),
        "trail_stop_mode": "percent",
        "trail_atr_k": float(trail_atr_k or 0),
        "trail_pct": float(trail_pct or 0),
        "breakeven_trigger_r": float(breakeven_trigger_r or 0),
        "profit_lock_trigger_r": float(profit_lock_trigger_r or 0),
        "profit_lock_r": float(profit_lock_r or 0),
        "partial_take_profit_r": float(partial_take_profit_r or 0),
        "partial_take_ratio": float(partial_take_ratio or 0),
        "time_stop_bars": int(time_stop_bars or 0),
        "avg_holding_bars": round(avg_hold_bars, 4),
        "avg_win_trade": round(avg_win, 6),
        "max_win_trade": round(max_win, 6),
        "pnl_p50": round(_quantile(pnl_all, 0.5), 6) if pnl_all else 0.0,
        "pnl_p80": round(_quantile(pnl_all, 0.8), 6) if pnl_all else 0.0,
        "pnl_p95": round(_quantile(pnl_all, 0.95), 6) if pnl_all else 0.0,
        "r_multiple_avg": round(sum(r_all) / len(r_all), 6) if r_all else 0.0,
        "r_multiple_p50": round(_quantile(r_all, 0.5), 6) if r_all else 0.0,
        "r_multiple_p80": round(_quantile(r_all, 0.8), 6) if r_all else 0.0,
        "r_multiple_p95": round(_quantile(r_all, 0.95), 6) if r_all else 0.0,
        "start_date": start_str,
        "end_date": end_str,
        "market": market,
        "buy_signal_rule": buy_signal_rule,
        "by_exit_reason": by_exit_reason,
        "equity_curve": equity_curve,
        "holding_days_histogram": _holding_days_histogram(details),
        "monthly_returns": _monthly_returns_from_details(details),
        "by_signal_type": _by_signal_type_stats(details),
    }
    return {"summary": summary, "details": details}


def _parse_score(r: dict) -> Optional[float]:
    st = r.get("score_total")
    if st is None:
        return None
    try:
        return float(st)
    except (TypeError, ValueError):
        return None


def _sort_details_for_export(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """市场（A股优先）→ 股票代码 → 信号日期，便于导出分组。"""
    return sorted(
        details,
        key=lambda d: (
            0 if (d.get("market") or "") == "CN" else 1,
            str(d.get("code") or ""),
            str(d.get("date") or ""),
        ),
    )


def _codes_for_market_from_pool(stock_pool: List[str], market_key: str) -> List[str]:
    """股票池内属于指定市场的代码，规范化后升序去重。"""

    def _is_a_share(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "6039"

    def _is_etf(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "518"

    mt_map = {"cn": "CN", "hk": "HK", "etf": "ETF"}
    mt_key_upper = mt_map.get(market_key, market_key)
    out: List[str] = []
    for c in stock_pool:
        if market_key == "cn" and _is_a_share(c):
            nc = normalize_gms_stock_code(c, "CN")
            if nc:
                out.append(nc)
        elif market_key == "etf" and _is_etf(c):
            nc = str(c).strip()
            out.append(nc)
        elif market_key == "hk" and not _is_a_share(c) and not _is_etf(c):
            nc = normalize_gms_stock_code(c, "HK")
            if nc:
                out.append(nc)
    return sorted(set(out))


def _gms_evaluate_one_signal(
    db: Session,
    r: dict,
    trade_date: str,
    market_key: str,
    horizon_days: int,
    target_pct: float,
    backtest_type: str,
    stop_loss_pct: float,
    commission_bps: float,
    slippage_bps: float,
    atr_period: int,
    init_stop_atr_k: float,
    trail_stop_mode: str,
    trail_atr_k: float,
    trail_pct: float,
    breakeven_trigger_r: float,
    profit_lock_trigger_r: float,
    profit_lock_r: float,
    partial_take_profit_r: float,
    partial_take_ratio: float,
    time_stop_bars: int,
    block_until_obs_end: Dict[Tuple[str, str], str],
) -> Optional[Dict[str, Any]]:
    """单条选股结果：若计入样本则返回明细 dict 并更新观察期锁；否则 None。"""
    if not (r.get("left_buy_signal") or r.get("right_buy_signal")):
        return None
    code = r.get("code") or r.get("symbol") or ""
    code = str(code).strip()
    if not code:
        return None
    mt_map = {"cn": "CN", "hk": "HK", "etf": "ETF"}
    mt_key = mt_map.get(market_key, market_key)
    if mt_key == "ETF":
        code = str(code).strip()
    else:
        code = normalize_gms_stock_code(code, mt_key)
    if not code:
        return None
    once_key = (mt_key, code)
    obs_end_prev = block_until_obs_end.get(once_key)
    if obs_end_prev is not None and trade_date <= obs_end_prev:
        return None
    buy_type = r.get("buy_type") or ("左侧" if r.get("left_buy_signal") else "右侧")
    score_total = _parse_score(r)

    if market_key == "etf":
        entry_open = _get_entry_open_next_day_etf(db, code, trade_date)
        future_bars = _get_future_ohlc_etf(db, code, trade_date, horizon_days)
    elif market_key == "cn":
        entry_open = _get_entry_open_next_day_cn(db, code, trade_date)
        future_bars = _get_future_ohlc_cn(db, code, trade_date, horizon_days)
    else:
        entry_open = _get_entry_open_next_day_hk(db, code, trade_date)
        future_bars = _get_future_ohlc_hk(db, code, trade_date, horizon_days)

    if entry_open is None or entry_open <= 0:
        return None
    if market_key == "etf":
        obs_end = _get_observation_window_end_etf(db, code, trade_date, horizon_days)
    elif market_key == "cn":
        obs_end = _get_observation_window_end_cn(db, code, trade_date, horizon_days)
    else:
        obs_end = _get_observation_window_end_hk(db, code, trade_date, horizon_days)
    block_until_obs_end[once_key] = obs_end if obs_end else trade_date
    future_highs = [float(b.get("high")) for b in future_bars if b.get("high") is not None]
    max_high = max(future_highs) if future_highs else entry_open
    max_gain = (max_high / entry_open - 1.0) if entry_open else 0.0
    hit = max_high >= entry_open * (1.0 + target_pct)
    base_row = {
        "code": code,
        "date": trade_date,
        "market": mt_key,
        "buy_type": buy_type,
        "score_total": score_total,
        "entry_open": round(entry_open, 4),
        "max_high_20d": round(max_high, 4),
        "max_gain_20d": round(max_gain, 4),
        "hit": hit,
    }
    if backtest_type != "trade_simulation":
        return base_row

    trade_row = _simulate_trade_exit(
        entry_open=entry_open,
        bars=future_bars,
        target_pct=target_pct,
        stop_loss_pct=stop_loss_pct,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        atr_period=atr_period,
        init_stop_atr_k=init_stop_atr_k,
        trail_stop_mode=trail_stop_mode,
        trail_atr_k=trail_atr_k,
        trail_pct=trail_pct,
        breakeven_trigger_r=breakeven_trigger_r,
        profit_lock_trigger_r=profit_lock_trigger_r,
        profit_lock_r=profit_lock_r,
        partial_take_profit_r=partial_take_profit_r,
        partial_take_ratio=partial_take_ratio,
        time_stop_bars=time_stop_bars,
    )
    base_row.update(
        {
            "entry_date": future_bars[0]["date"] if future_bars else "",
            "stop_loss_pct": float(stop_loss_pct or 0),
            "commission_bps": float(commission_bps or 0),
            "slippage_bps": float(slippage_bps or 0),
            "atr_period": int(atr_period or 14),
            "init_stop_atr_k": float(init_stop_atr_k or 0),
            "trail_stop_mode": "percent",
            "trail_atr_k": float(trail_atr_k or 0),
            "trail_pct": float(trail_pct or 0),
            "breakeven_trigger_r": float(breakeven_trigger_r or 0),
            "profit_lock_trigger_r": float(profit_lock_trigger_r or 0),
            "profit_lock_r": float(profit_lock_r or 0),
            "partial_take_profit_r": float(partial_take_profit_r or 0),
            "partial_take_ratio": float(partial_take_ratio or 0),
            "time_stop_bars": int(time_stop_bars or 0),
        }
    )
    base_row.update(trade_row)
    return base_row


def run_gms_backtest(
    db: Session,
    start_date: str,
    end_date: str,
    market: str = "all",
    target_pct: float = 0.05,
    horizon_days: int = 20,
    min_score: float = 0,
    backtest_type: str = "signal_hit_rate",
    stop_loss_pct: float = 0,
    commission_bps: float = 0,
    slippage_bps: float = 0,
    atr_period: int = 14,
    init_stop_atr_k: float = 2.2,
    trail_stop_mode: str = "atr",
    trail_atr_k: float = 3.0,
    trail_pct: float = 0.08,
    breakeven_trigger_r: float = 1.0,
    profit_lock_trigger_r: float = 2.0,
    profit_lock_r: float = 0.5,
    partial_take_profit_r: float = 2.0,
    partial_take_ratio: float = 0.4,
    time_stop_bars: int = 15,
    position_fraction: float = 1.0,
    stock_pool: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    strategy_config_id: Optional[int] = None,
    config_params_snapshot: Optional[Dict[str, Any]] = None,
    cn_board_segment: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行 GMS 回测（与管理端 create_backtest 任务一致）：
    每交易日取左/右侧买入信号，GMSFrontendInterface 按最低总分筛选；单股时股票池仅含该代码，
    仍按区间内全部交易日扫描，与页面表格是否分页无关。
    同一标的在上一笔的观察期（horizon_days 根 K 线）结束后才允许再次计入样本。
    股票池不少于 2 只时：按市场、按交易日批量拉取整池选股结果（再逐条评估信号）；否则（含全市场）按交易日遍历。
    """
    start_str = str(start_date).strip()[:10]
    end_str = str(end_date).strip()[:10]
    pos_f = _clamp_position_fraction(position_fraction)
    seg_raw = (cn_board_segment or "").strip().upper() or None
    if seg_raw == "ALL":
        seg_raw = None

    bt = str(backtest_type or "signal_hit_rate").strip().lower()
    if bt not in ("signal_hit_rate", "trade_simulation"):
        bt = "signal_hit_rate"
    if bt == "trade_simulation":
        buy_signal_rule = (
            "交易回测：样本为左/右侧买点，信号总分受最低总分筛选；"
            "买入价为信号日后下一交易日开盘价；"
            "同一标的在上一笔观察期结束前不重复开仓；"
            "出场规则为先止损后止盈（同日同时触发按止损），否则观察期最后一根K线收盘价出场；"
            "净值与最终盈利按「单笔仓位」比例复利计入（其余资金视为现金、无收益）。"
        )
    else:
        buy_signal_rule = (
            "命中率回测：样本为左/右侧买点，信号总分受最低总分筛选；"
            "买入价为信号日后下一交易日开盘价；"
            "统计观察期内最高价是否触达目标涨幅；"
            "同一标的在上一笔观察期结束前不重复计入样本。"
        )

    # 单股/自定义股票池时只跑该池所属市场，避免“选单股仍跑全市场”
    def _is_a_share(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "6039"

    def _is_etf(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "518"

    if market == "all":
        dates_cn = _get_trading_dates_cn(db, start_str, end_str)
        dates_hk = _get_trading_dates_hk(db, start_str, end_str)
        # ETF 使用 A 股交易日历（因为都在沪深交易所）
        dates_etf = dates_cn
        if stock_pool:
            cn_codes = [c for c in stock_pool if _is_a_share(c)]
            etf_codes = [c for c in stock_pool if _is_etf(c)]
            hk_codes = [c for c in stock_pool if c not in cn_codes and c not in etf_codes]
            markets_to_run = []
            if cn_codes:
                markets_to_run.append(("cn", dates_cn))
            if etf_codes:
                markets_to_run.append(("etf", dates_etf))
            if hk_codes:
                markets_to_run.append(("hk", dates_hk))
            if not markets_to_run:
                markets_to_run = [("cn", dates_cn), ("etf", dates_etf), ("hk", dates_hk)]
        else:
            markets_to_run = [("cn", dates_cn), ("etf", dates_etf), ("hk", dates_hk)]
    elif market == "cn":
        markets_to_run = [("cn", _get_trading_dates_cn(db, start_str, end_str))]
    elif market == "etf":
        # ETF 使用 A 股交易日历（沪深 ETF 与 A 股同交易日历）
        markets_to_run = [("etf", _get_trading_dates_cn(db, start_str, end_str))]
    else:
        markets_to_run = [("hk", _get_trading_dates_hk(db, start_str, end_str))]

    if seg_raw and stock_pool:
        from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

        stock_pool = filter_stock_codes_by_board_segment(stock_pool, seg_raw)
        if not stock_pool:
            stock_pool = None

    use_stock_first = stock_pool is not None and len(stock_pool) >= 2
    # 多股模式：仅统计「该市场池内确有代码」时的交易日数，与循环内 processed 次数一致；否则分母过小会导致进度超 100%
    if use_stock_first:
        total_steps = sum(
            len(dl)
            for mk, dl in markets_to_run
            if _codes_for_market_from_pool(stock_pool, mk)
        )
    else:
        total_steps = sum(len(dl) for _, dl in markets_to_run)

    if total_steps == 0:
        if bt == "trade_simulation":
            return _aggregate_trade_summary(
                [],
                start_str,
                end_str,
                market,
                target_pct,
                horizon_days,
                buy_signal_rule,
                stop_loss_pct=stop_loss_pct,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                trail_stop_mode=trail_stop_mode,
                trail_atr_k=trail_atr_k,
                trail_pct=trail_pct,
                breakeven_trigger_r=breakeven_trigger_r,
                profit_lock_trigger_r=profit_lock_trigger_r,
                profit_lock_r=profit_lock_r,
                partial_take_profit_r=partial_take_profit_r,
                partial_take_ratio=partial_take_ratio,
                time_stop_bars=time_stop_bars,
                position_fraction=pos_f,
            )
        return _aggregate_details_to_summary([], start_str, end_str, market, target_pct, horizon_days, buy_signal_rule)

    interface = GMSFrontendInterface(
        db,
        config=config_params_snapshot,
        config_id=strategy_config_id,
    )
    interface.set_selection_config(min_score=min_score, max_results=10000)

    details: List[Dict[str, Any]] = []
    processed = 0
    # (市场, 规范化代码) -> 上一笔样本的观察期最后交易日；新信号须 trade_date > 该日
    block_until_obs_end: Dict[Tuple[str, str], str] = {}

    if use_stock_first:
        stop = False
        for market_key, date_list in markets_to_run:
            if stop:
                break
            codes_m = _codes_for_market_from_pool(stock_pool, market_key)
            if not codes_m or not date_list:
                continue
            for trade_date in date_list:
                if cancel_check and cancel_check():
                    logger.info("GMS 回测被取消")
                    stop = True
                    break
                try:
                    results = interface.get_selection_results(
                        date=trade_date,
                        stock_pool=codes_m,
                        market=market_key,
                        cn_board_segment=seg_raw if market_key == "cn" else None,
                    )
                except Exception as e:
                    logger.warning("GMS 选股失败 %s %s: %s", market_key, trade_date, e)
                    processed += 1
                    if progress_callback and total_steps > 0:
                        pct = min(99, _progress_pct(processed, total_steps))
                        progress_callback(pct, f"{market_key} {trade_date}")
                    continue
                results_sorted = sorted(
                    results,
                    key=lambda r: str((r.get("code") or r.get("symbol") or "")).strip(),
                )
                for r in results_sorted:
                    row = _gms_evaluate_one_signal(
                        db,
                        r,
                        trade_date,
                        market_key,
                        horizon_days,
                        target_pct,
                        bt,
                        stop_loss_pct,
                        commission_bps,
                        slippage_bps,
                        atr_period,
                        init_stop_atr_k,
                        trail_stop_mode,
                        trail_atr_k,
                        trail_pct,
                        breakeven_trigger_r,
                        profit_lock_trigger_r,
                        profit_lock_r,
                        partial_take_profit_r,
                        partial_take_ratio,
                        time_stop_bars,
                        block_until_obs_end,
                    )
                    if row:
                        details.append(row)
                processed += 1
                if progress_callback and total_steps > 0:
                    pct = _progress_pct(processed, total_steps)
                    progress_callback(pct, f"{market_key} {trade_date}")
            if stop:
                break
    else:
        stop = False
        for market_key, date_list in markets_to_run:
            if stop:
                break
            for trade_date in date_list:
                if cancel_check and cancel_check():
                    logger.info("GMS 回测被取消")
                    stop = True
                    break
                try:
                    results = interface.get_selection_results(
                        date=trade_date,
                        stock_pool=stock_pool,
                        market=market_key,
                        cn_board_segment=seg_raw if market_key in ("cn", "all") else None,
                    )
                except Exception as e:
                    logger.warning("GMS 选股失败 %s: %s", trade_date, e)
                    continue

                for r in results:
                    row = _gms_evaluate_one_signal(
                        db,
                        r,
                        trade_date,
                        market_key,
                        horizon_days,
                        target_pct,
                        bt,
                        stop_loss_pct,
                        commission_bps,
                        slippage_bps,
                        atr_period,
                        init_stop_atr_k,
                        trail_stop_mode,
                        trail_atr_k,
                        trail_pct,
                        breakeven_trigger_r,
                        profit_lock_trigger_r,
                        profit_lock_r,
                        partial_take_profit_r,
                        partial_take_ratio,
                        time_stop_bars,
                        block_until_obs_end,
                    )
                    if row:
                        details.append(row)

                processed += 1
                if progress_callback and total_steps > 0:
                    pct = _progress_pct(processed, total_steps)
                    progress_callback(pct, f"已处理 {trade_date}")
            if stop:
                break

    details = _sort_details_for_export(details)
    if bt == "trade_simulation":
        _annotate_trade_position_pnl(details, pos_f)
        return _aggregate_trade_summary(
            details,
            start_str,
            end_str,
            market,
            target_pct,
            horizon_days,
            buy_signal_rule,
            stop_loss_pct=stop_loss_pct,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            trail_stop_mode=trail_stop_mode,
            trail_atr_k=trail_atr_k,
            trail_pct=trail_pct,
            breakeven_trigger_r=breakeven_trigger_r,
            profit_lock_trigger_r=profit_lock_trigger_r,
            profit_lock_r=profit_lock_r,
            partial_take_profit_r=partial_take_profit_r,
            partial_take_ratio=partial_take_ratio,
            time_stop_bars=time_stop_bars,
            position_fraction=pos_f,
        )
    return _aggregate_details_to_summary(details, start_str, end_str, market, target_pct, horizon_days, buy_signal_rule)
