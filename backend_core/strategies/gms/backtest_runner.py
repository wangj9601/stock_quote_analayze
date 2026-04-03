"""
GMS 策略回测执行器
按「信号日后 N 个交易日内最高价是否达到 entry*(1+target_pct)」计算目标命中率（准确率）。

与管理端 GMS 回测任务共用同一套逻辑：每个交易日取 GMS 左/右侧买入信号，
经 GMSFrontendInterface 按最低总分筛选后计入样本（单股仅股票池缩为该代码）。
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session

from .frontend_interface import GMSFrontendInterface
from .backtest_storage import normalize_gms_stock_code

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
    执行 GMS 回测（与管理端 create_backtest 任务一致）：
    每交易日取左/右侧买入信号，GMSFrontendInterface 按最低总分筛选；单股时股票池仅含该代码，
    仍按区间内全部交易日扫描，与页面表格是否分页无关。
    """
    start_str = str(start_date).strip()[:10]
    end_str = str(end_date).strip()[:10]

    buy_signal_rule = (
        "与管理端 GMS 回测一致：样本为左/右侧买点，信号总分受「最低总分」参数筛选（GMSFrontendInterface）。"
    )

    # 单股/自定义股票池时只跑该池所属市场，避免“选单股仍跑全市场”
    def _is_a_share(c: str) -> bool:
        s = str(c).strip()
        return len(s) >= 6 and s.isdigit() and s[0] in "6039"

    if market == "all":
        dates_cn = _get_trading_dates_cn(db, start_str, end_str)
        dates_hk = _get_trading_dates_hk(db, start_str, end_str)
        if stock_pool:
            cn_codes = [c for c in stock_pool if _is_a_share(c)]
            hk_codes = [c for c in stock_pool if c not in cn_codes]
            if cn_codes and not hk_codes:
                markets_to_run = [("cn", dates_cn)]
            elif hk_codes and not cn_codes:
                markets_to_run = [("hk", dates_hk)]
            else:
                markets_to_run = [("cn", dates_cn), ("hk", dates_hk)]
        else:
            markets_to_run = [("cn", dates_cn), ("hk", dates_hk)]
    elif market == "cn":
        markets_to_run = [("cn", _get_trading_dates_cn(db, start_str, end_str))]
    else:
        markets_to_run = [("hk", _get_trading_dates_hk(db, start_str, end_str))]

    total_steps = sum(len(dl) for _, dl in markets_to_run)
    if total_steps == 0:
        return _aggregate_details_to_summary(
            [], start_str, end_str, market, target_pct, horizon_days, buy_signal_rule
        )

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
                code = str(code).strip()
                if not code:
                    continue
                mt_key = "CN" if market_key == "cn" else "HK"
                code = normalize_gms_stock_code(code, mt_key)
                if not code:
                    continue
                buy_type = r.get("buy_type") or ("左侧" if r.get("left_buy_signal") else "右侧")
                score_total = _parse_score(r)

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
                    "market": mt_key,
                    "buy_type": buy_type,
                    "score_total": score_total,
                    "entry_close": round(entry_close, 4),
                    "max_high_20d": round(max_high, 4),
                    "max_gain_20d": round(max_gain, 4),
                    "hit": hit,
                })

            processed += 1
            if progress_callback and total_steps > 0:
                pct = int(100 * (processed / total_steps))
                progress_callback(pct, f"已处理 {trade_date}")

    return _aggregate_details_to_summary(
        details, start_str, end_str, market, target_pct, horizon_days, buy_signal_rule
    )
