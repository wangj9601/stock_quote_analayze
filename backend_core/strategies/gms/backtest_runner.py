"""
GMS 策略回测执行器
按「信号日后 20 个交易日内最高价是否达到 entry*(1+target_pct)」计算目标命中率（准确率）。
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from .frontend_interface import GMSFrontendInterface

logger = logging.getLogger(__name__)


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


def _get_entry_close_cn(db: Session, code: str, trade_date: str) -> Optional[float]:
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    date_str = str(trade_date).strip()[:10]
    row = (
        db.query(HistoricalQuotes.close)
        .filter(
            HistoricalQuotes.code == code,
            cast(HistoricalQuotes.date, String) == date_str,
        )
        .first()
    )
    if row and row[0] is not None:
        return float(row[0])
    return None


def _get_entry_close_hk(db: Session, code: str, trade_date: str) -> Optional[float]:
    from backend_api.models import HistoricalQuotesHK
    row = (
        db.query(HistoricalQuotesHK.close)
        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date == trade_date)
        .first()
    )
    if row and row[0] is not None:
        return float(row[0])
    return None


def _get_future_highs_cn(db: Session, code: str, after_date: str, limit: int) -> List[float]:
    """信号日之后 limit 个交易日的 high，按日期升序。"""
    from sqlalchemy import cast, String
    from backend_api.models import HistoricalQuotes

    after_str = str(after_date).strip()[:10]
    rows = (
        db.query(HistoricalQuotes.high)
        .filter(
            HistoricalQuotes.code == code,
            cast(HistoricalQuotes.date, String) > after_str,
        )
        .order_by(HistoricalQuotes.date)
        .limit(limit)
        .all()
    )
    return [float(r[0]) for r in rows if r[0] is not None]


def _get_future_highs_hk(db: Session, code: str, after_date: str, limit: int) -> List[float]:
    from backend_api.models import HistoricalQuotesHK
    rows = (
        db.query(HistoricalQuotesHK.high)
        .filter(HistoricalQuotesHK.code == code, HistoricalQuotesHK.date > after_date)
        .order_by(HistoricalQuotesHK.date)
        .limit(limit)
        .all()
    )
    return [float(r[0]) for r in rows if r[0] is not None]


def run_gms_backtest(
    db: Session,
    start_date: str,
    end_date: str,
    market: str = "all",
    target_pct: float = 0.05,
    horizon_days: int = 20,
    min_score: float = 0,
    stock_pool: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """
    执行 GMS 回测：对每个交易日取 GMS 买入信号，统计信号后 horizon_days 日内
    最高价是否 >= 入场价*(1+target_pct)，汇总命中率等。

    Args:
        db: 数据库会话
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        market: all / cn / hk
        target_pct: 目标涨幅，如 0.05 表示 5%
        horizon_days: 观察窗口交易日数
        min_score: GMS 最低总分
        stock_pool: 股票代码列表；None 表示全市场（由 GMSFrontendInterface 按 market 取）
                    单股回测传 [code]，自定义列表传多码
        progress_callback: (percent, message) 进度回调
        cancel_check: 无参可调用，返回 True 表示取消

    Returns:
        {
            "summary": {"total_samples", "hit_count", "hit_rate", "by_buy_type", "by_score_bucket", ...},
            "details": [{"code", "date", "market", "buy_type", "score_total", "entry_close", "max_high_20d", "max_gain_20d", "hit"}, ...]
        }
    """
    start_str = str(start_date).strip()[:10]
    end_str = str(end_date).strip()[:10]

    # 单股/自定义股票池时只跑该池所属市场，避免“选单股仍跑全市场”
    def _is_a_share(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "6039"

    if market == "all":
        dates_cn = _get_trading_dates_cn(db, start_str, end_str)
        dates_hk = _get_trading_dates_hk(db, start_str, end_str)
        all_dates = sorted(set(dates_cn) | set(dates_hk))
        if stock_pool:
            cn_codes = [c for c in stock_pool if _is_a_share(c)]
            hk_codes = [c for c in stock_pool if c not in cn_codes]
            if cn_codes and not hk_codes:
                markets_to_run = [("cn", dates_cn)]
                all_dates = dates_cn
            elif hk_codes and not cn_codes:
                markets_to_run = [("hk", dates_hk)]
                all_dates = dates_hk
            else:
                markets_to_run = [("cn", dates_cn), ("hk", dates_hk)]
        else:
            markets_to_run = [("cn", dates_cn), ("hk", dates_hk)]
    elif market == "cn":
        all_dates = _get_trading_dates_cn(db, start_str, end_str)
        markets_to_run = [("cn", all_dates)]
    else:
        all_dates = _get_trading_dates_hk(db, start_str, end_str)
        markets_to_run = [("hk", all_dates)]

    total_dates = len(all_dates)
    if total_dates == 0:
        return {"summary": {"total_samples": 0, "hit_count": 0, "hit_rate": 0.0}, "details": []}

    # GMSFrontendInterface 已实现：优先从 gms_signal_trace 取策略信号，不存在或缺失则增量计算并回填
    interface = GMSFrontendInterface(db)
    interface.set_selection_config(min_score=min_score, max_results=10000)

    details: List[Dict[str, Any]] = []
    processed = 0

    for market_key, date_list in markets_to_run:
        for i, trade_date in enumerate(date_list):
            if cancel_check and cancel_check():
                logger.info("GMS 回测被取消")
                break
            try:
                results = interface.get_selection_results(date=trade_date, stock_pool=stock_pool, market=market_key)
            except Exception as e:
                logger.warning("GMS 选股失败 %s: %s", trade_date, e)
                continue

            for r in results:
                if not (r.get("left_buy_signal") or r.get("right_buy_signal")):
                    continue
                code = r.get("code") or r.get("symbol") or ""
                if not code:
                    continue
                buy_type = r.get("buy_type") or ("左侧" if r.get("left_buy_signal") else "右侧")
                score_total = r.get("score_total")
                if score_total is not None:
                    try:
                        score_total = float(score_total)
                    except (TypeError, ValueError):
                        score_total = None

                if market_key == "cn":
                    entry_close = _get_entry_close_cn(db, code, trade_date)
                    future_highs = _get_future_highs_cn(db, code, trade_date, horizon_days)
                else:
                    entry_close = _get_entry_close_hk(db, code, trade_date)
                    future_highs = _get_future_highs_hk(db, code, trade_date, horizon_days)

                if entry_close is None or entry_close <= 0:
                    continue
                max_high = max(future_highs) if future_highs else entry_close
                max_gain = (max_high / entry_close - 1.0) if entry_close else 0.0
                hit = max_high >= entry_close * (1.0 + target_pct)

                details.append({
                    "code": code,
                    "date": trade_date,
                    "market": "CN" if market_key == "cn" else "HK",
                    "buy_type": buy_type,
                    "score_total": score_total,
                    "entry_close": round(entry_close, 4),
                    "max_high_20d": round(max_high, 4),
                    "max_gain_20d": round(max_gain, 4),
                    "hit": hit,
                })

            processed += 1
            if progress_callback and total_dates > 0:
                pct = int(100 * (processed / total_dates))
                progress_callback(pct, f"已处理 {trade_date}")

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
    for k, v in by_buy_type.items():
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
    for k, v in by_score_bucket.items():
        v["hit_rate"] = (v["hit"] / v["total"]) if v["total"] else 0.0

    summary = {
        "total_samples": total_samples,
        "hit_count": hit_count,
        "hit_rate": round(hit_rate, 4),
        "target_pct": target_pct,
        "horizon_days": horizon_days,
        "start_date": start_str,
        "end_date": end_str,
        "market": market,
        "by_buy_type": by_buy_type,
        "by_score_bucket": by_score_bucket,
    }
    return {"summary": summary, "details": details}
