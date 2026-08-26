"""节点执行适配：直接调用采集器，避免 import main.py 触发调度注册。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Optional

from backend_core.config.config import DATA_COLLECTORS
from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext
from backend_core.data_collectors.workflow.session_guard import (
    cn_session_closed_today,
    hk_session_closed_today,
)

logger = logging.getLogger(__name__)


def _env_bool(k: str, default: bool = True) -> bool:
    v = (os.getenv(k) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _env_int(k: str, default: int) -> int:
    try:
        return int(os.getenv(k, str(default)))
    except ValueError:
        return default


def _wrap_cn(fn: Callable[[], Any], name: str) -> Callable[[WorkflowContext], NodeResult]:
    def _exec(ctx: WorkflowContext) -> NodeResult:
        if cn_session_closed_today():
            return NodeResult.skip(f"A股休市，跳过{name}")
        try:
            out = fn()
            return NodeResult.ok(f"{name}完成", data={"result": _safe(out)})
        except Exception as e:
            logger.exception("%s 异常", name)
            return NodeResult.fail(str(e), message=f"{name}失败")

    return _exec


def _wrap_hk(fn: Callable[[], Any], name: str) -> Callable[[WorkflowContext], NodeResult]:
    def _exec(ctx: WorkflowContext) -> NodeResult:
        if hk_session_closed_today():
            return NodeResult.skip(f"港股休市，跳过{name}")
        try:
            out = fn()
            return NodeResult.ok(f"{name}完成", data={"result": _safe(out)})
        except Exception as e:
            logger.exception("%s 异常", name)
            return NodeResult.fail(str(e), message=f"{name}失败")

    return _exec


def _wrap_plain(fn: Callable[[], Any], name: str) -> Callable[[WorkflowContext], NodeResult]:
    def _exec(ctx: WorkflowContext) -> NodeResult:
        try:
            out = fn()
            return NodeResult.ok(f"{name}完成", data={"result": _safe(out)})
        except Exception as e:
            logger.exception("%s 异常", name)
            return NodeResult.fail(str(e), message=f"{name}失败")

    return _exec


def _safe(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _safe(val) for k, val in v.items()}
    if hasattr(v, "__len__") and not isinstance(v, (str, bytes)):
        try:
            return {"len": len(v)}
        except Exception:
            return str(v)
    return str(v)


# ---- 具体采集实现 ----

def _cn_realtime() -> Any:
    from backend_core.data_collectors.akshare.realtime import AkshareRealtimeQuoteCollector

    return AkshareRealtimeQuoteCollector(DATA_COLLECTORS.get("akshare", {})).collect_quotes()


def _cn_historical() -> Any:
    from backend_core.data_collectors.tushare.historical import HistoricalQuoteCollector

    today_str = datetime.now().strftime("%Y%m%d")
    collector = HistoricalQuoteCollector(DATA_COLLECTORS.get("tushare", {}))
    if collector.collect_historical_quotes_from_realtime(today_str):
        return {"source": "realtime", "date": today_str}
    collector.collect_historical_quotes(today_str)
    return {"source": "tushare", "date": today_str}


def _cn_index_realtime() -> Any:
    from backend_core.data_collectors.akshare.realtime_index_spot_ak import RealtimeIndexSpotAkCollector

    df = RealtimeIndexSpotAkCollector().collect_quotes()
    return {"rows": 0 if df is None else len(df)}


def _cn_industry_board() -> Any:
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    RealtimeStockIndustryBoardCollector().run()
    return True


def _cn_industry_constituents() -> Any:
    from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
        IndustryBoardConstituentsCollector,
    )

    IndustryBoardConstituentsCollector().run()
    return True


def _cn_turnover() -> Any:
    if not _env_bool("SCHED_AKSHARE_TURNOVER_ENABLED", False):
        return {"skipped": True, "reason": "SCHED_AKSHARE_TURNOVER_ENABLED=false"}
    from backend_core.data_collectors.akshare.historical_turnover_rate import (
        HistoricalTurnoverRateCollector,
    )

    days = _env_int("COLLECTOR_TURNOVER_RATE_DAYS", 30)
    ok = HistoricalTurnoverRateCollector(DATA_COLLECTORS.get("akshare", {})).collect_missing_turnover_rate(
        days
    )
    return {"success": ok, "days": days}


def _stock_shares() -> Any:
    from backend_core.data_collectors.akshare.stock_shares_collector import StockSharesCollector

    return StockSharesCollector(DATA_COLLECTORS.get("akshare", {})).run(mode="incremental")


def _hk_realtime() -> Any:
    from backend_core.data_collectors.akshare.hk_realtime import HKRealtimeQuoteCollector

    return HKRealtimeQuoteCollector(DATA_COLLECTORS.get("akshare", {})).collect_quotes()


def _hk_historical() -> Any:
    from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector

    today = datetime.now().strftime("%Y%m%d")
    ok = HKHistoricalQuoteCollector(DATA_COLLECTORS.get("akshare", {})).collect_historical_quotes(today)
    return {"success": ok, "date": today}


def _hk_index_realtime() -> Any:
    from backend_core.data_collectors.akshare.hk_index_realtime import HKIndexRealtimeCollector

    result = HKIndexRealtimeCollector().collect_realtime_quotes()
    return {"rows": 0 if not result else len(result)}


def _hk_index_historical() -> Any:
    from backend_core.data_collectors.akshare.hk_index_historical_collector import (
        HKIndexHistoricalCollector,
    )

    return HKIndexHistoricalCollector().collect_daily_to_historical()


def _is_period_end(market: str, period: str) -> bool:
    from datetime import date as date_cls

    from backend_api.database import SessionLocal
    from backend_api.utils.trading_calendar_utils import is_market_session_closed
    from backend_core.data_collectors.akshare.period_agg import is_last_session_day_of_period

    day = date_cls.today()
    session = SessionLocal()
    try:

        def _closed(x):
            try:
                return is_market_session_closed(session, market, x)
            except Exception:
                return False

        return is_last_session_day_of_period(day, period, is_session_closed=_closed)
    except Exception as e:
        logger.warning("%s 周期末日判定异常 period=%s: %s", market, period, e)
        return False
    finally:
        session.close()


def _etf_realtime() -> Any:
    """
    ETF 实时：拉取行情后写入 fund_realtime_quote（逻辑对齐 main.collect_etf_realtime）。
    """
    import akshare as ak
    import pandas as pd
    from sqlalchemy import text

    from backend_core.data_collectors.akshare.etf_collector import ETFCollector

    if not _env_bool("ENABLE_ETF", True):
        return {"skipped": True, "reason": "ENABLE_ETF=false"}

    df = None
    source = "em"
    for src, fetcher in (
        ("em", lambda: ak.fund_etf_spot_em()),
        ("sina", lambda: ak.fund_etf_category_sina(symbol="ETF基金")),
        ("ths", lambda: ak.fund_etf_spot_ths()),
    ):
        try:
            df = fetcher()
            source = src
            if df is not None and not getattr(df, "empty", True):
                break
        except Exception as e:
            logger.warning("ETF 实时源 %s 失败: %s", src, e)
            df = None

    if df is None or getattr(df, "empty", True):
        return {"success": False, "message": "无 ETF 实时数据"}

    collector = ETFCollector()
    session = collector.session
    now = datetime.now()
    trade_date = now.strftime("%Y-%m-%d")
    count = 0
    for _, row in df.iterrows():
        if source == "ths":
            code = str(row.get("基金代码", "") or "")
            name = str(row.get("基金名称", "") or "")
            current_price = row.get("当前-单位净值") or row.get("最新-单位净值")
            change_percent = row.get("增长率")
            pre_close = row.get("前一日-单位净值")
            volume = amount = high = low = open_price = turnover_rate = total_mv = circulating_mv = None
        else:
            code = str(row.get("代码", "") or "")
            name = str(row.get("名称", "") or "")
            current_price = row.get("最新价")
            change_percent = row.get("涨跌幅")
            volume = row.get("成交量")
            amount = row.get("成交额")
            high = row.get("最高")
            low = row.get("最低")
            open_price = row.get("今开")
            pre_close = row.get("昨收")
            turnover_rate = row.get("换手率") if source == "em" else None
            total_mv = row.get("总市值") if source == "em" else None
            circulating_mv = row.get("流通市值") if source == "em" else None

        if not code:
            continue
        if code.startswith("sh") or code.startswith("sz"):
            code = code[2:]

        def _f(v):
            try:
                return float(v) if v is not None and pd.notna(v) else None
            except Exception:
                return None

        session.execute(
            text(
                """
                INSERT INTO fund_basic_info (code, name, fund_type, collect_enabled, created_at, updated_at)
                VALUES (:code, :name, 'ETF', TRUE, :now, :now)
                ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, updated_at = EXCLUDED.updated_at
                """
            ),
            {"code": code, "name": name, "now": now},
        )
        session.execute(
            text(
                """
                INSERT INTO fund_realtime_quote (
                    code, trade_date, name, current_price, change_percent, volume, amount,
                    high, low, open, pre_close, turnover_rate, total_market_value,
                    circulating_market_value, update_time
                ) VALUES (
                    :code, :trade_date, :name, :current_price, :change_percent, :volume, :amount,
                    :high, :low, :open, :pre_close, :turnover_rate, :total_market_value,
                    :circulating_market_value, :update_time
                )
                ON CONFLICT (code, trade_date) DO UPDATE SET
                    name = EXCLUDED.name,
                    current_price = EXCLUDED.current_price,
                    change_percent = EXCLUDED.change_percent,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    open = EXCLUDED.open,
                    pre_close = EXCLUDED.pre_close,
                    turnover_rate = EXCLUDED.turnover_rate,
                    total_market_value = EXCLUDED.total_market_value,
                    circulating_market_value = EXCLUDED.circulating_market_value,
                    update_time = EXCLUDED.update_time
                """
            ),
            {
                "code": code,
                "trade_date": trade_date,
                "name": name,
                "current_price": _f(current_price),
                "change_percent": _f(change_percent),
                "volume": _f(volume),
                "amount": _f(amount),
                "high": _f(high),
                "low": _f(low),
                "open": _f(open_price),
                "pre_close": _f(pre_close),
                "turnover_rate": _f(turnover_rate),
                "total_market_value": _f(total_mv),
                "circulating_market_value": _f(circulating_mv),
                "update_time": now,
            },
        )
        count += 1
    session.commit()
    return {"rows": count, "source": source}


def _etf_historical() -> Any:
    from backend_core.data_collectors.akshare.etf_collector import ETFCollector

    if not _env_bool("ENABLE_ETF", True):
        return {"skipped": True, "reason": "ENABLE_ETF=false"}
    today_str = datetime.now().strftime("%Y-%m-%d")
    collector = ETFCollector()
    collector.sync_etf_list()
    if collector.collect_historical_quotes_from_realtime(today_str):
        return {"source": "realtime", "date": today_str}
    collector.collect_historical_data(start_date=today_str, end_date=today_str)
    return {"source": "api", "date": today_str}


def _gen_cn_weekly() -> Any:
    from backend_core.data_collectors.akshare.weekly_collector import WeeklyDataGenerator

    return WeeklyDataGenerator().generate_current_week_data()


def _gen_cn_monthly() -> Any:
    from backend_core.data_collectors.akshare.monthly_collector import MonthlyDataGenerator

    return MonthlyDataGenerator().generate_current_month_data()


def _gen_cn_quarterly() -> Any:
    from backend_core.data_collectors.akshare.quarterly_collector import QuarterlyDataGenerator

    if not _is_period_end("CN", "quarterly"):
        return {"skipped": True, "reason": "非季末交易日"}
    return QuarterlyDataGenerator().generate_current_quarter_data()


def _gen_cn_semiannual() -> Any:
    from backend_core.data_collectors.akshare.semiannual_collector import SemiAnnualDataGenerator

    if not _is_period_end("CN", "semiannual"):
        return {"skipped": True, "reason": "非半年末交易日"}
    return SemiAnnualDataGenerator().generate_current_semiannual_data()


def _gen_cn_annual() -> Any:
    from backend_core.data_collectors.akshare.annual_collector import AnnualDataGenerator

    if not _is_period_end("CN", "annual"):
        return {"skipped": True, "reason": "非年末交易日"}
    return AnnualDataGenerator().generate_current_annual_data()


def _gen_hk_weekly() -> Any:
    from backend_core.data_collectors.akshare.hk_weekly_collector import HKWeeklyDataGenerator

    return HKWeeklyDataGenerator().generate_current_week_data()


def _gen_hk_monthly() -> Any:
    from backend_core.data_collectors.akshare.hk_monthly_collector import HKMonthlyDataGenerator

    return HKMonthlyDataGenerator().generate_current_month_data()


def _gen_hk_quarterly() -> Any:
    from backend_core.data_collectors.akshare.hk_quarterly_collector import HKQuarterlyDataGenerator

    if not _is_period_end("HK", "quarterly"):
        return {"skipped": True, "reason": "非季末交易日"}
    return HKQuarterlyDataGenerator().generate_current_quarter_data()


def _gen_hk_semiannual() -> Any:
    from backend_core.data_collectors.akshare.hk_semiannual_collector import HKSemiAnnualDataGenerator

    if not _is_period_end("HK", "semiannual"):
        return {"skipped": True, "reason": "非半年末交易日"}
    return HKSemiAnnualDataGenerator().generate_current_semiannual_data()


def _gen_hk_annual() -> Any:
    from backend_core.data_collectors.akshare.hk_annual_collector import HKAnnualDataGenerator

    if not _is_period_end("HK", "annual"):
        return {"skipped": True, "reason": "非年末交易日"}
    return HKAnnualDataGenerator().generate_current_annual_data()

def _gms_cn() -> Any:
    from backend_core.strategies.gms.scheduled_precompute import scheduled_gms_signals_cn

    scheduled_gms_signals_cn()
    return True


def _urt_cn() -> Any:
    from backend_core.strategies.urt.scheduled_precompute import scheduled_urt_signals_cn

    scheduled_urt_signals_cn()
    return True


def _gms_hk() -> Any:
    from backend_core.strategies.gms.scheduled_precompute import scheduled_gms_signals_hk

    scheduled_gms_signals_hk()
    return True


def _urt_hk() -> Any:
    from backend_core.strategies.urt.scheduled_precompute import scheduled_urt_signals_hk

    scheduled_urt_signals_hk()
    return True


def _sbbr_cn() -> Any:
    from backend_core.strategies.sbbr.scheduled_precompute import scheduled_sbbr_signals_cn

    scheduled_sbbr_signals_cn()
    return True


def _rpe_cn() -> Any:
    from backend_core.strategies.rpe.scheduled_precompute import scheduled_rpe_signals_cn

    scheduled_rpe_signals_cn()
    return True


def _market_news() -> Any:
    from backend_core.data_collectors.news_collector import NewsCollector

    return NewsCollector().collect_and_save_market_news()


def _watchlist_history() -> Any:
    from backend_core.data_collectors.akshare.watchlist_history_collector import (
        collect_watchlist_history,
    )

    return collect_watchlist_history()


def _triple_volume_scan() -> Any:
    from backend_api.database import SessionLocal
    from backend_core.strategies.triple_volume_observe.scan_job import run_triple_volume_scan

    db = SessionLocal()
    try:
        return run_triple_volume_scan(db)
    finally:
        db.close()


# 导出包装后的执行器
exec_cn_realtime = _wrap_cn(_cn_realtime, "A股实时采集")
exec_cn_historical = _wrap_cn(_cn_historical, "A股日K采集")
exec_cn_index_realtime = _wrap_cn(_cn_index_realtime, "A股指数实时")
exec_cn_industry_board = _wrap_cn(_cn_industry_board, "行业板块实时")
exec_cn_industry_constituents = _wrap_plain(_cn_industry_constituents, "行业板块成分股")
exec_cn_turnover = _wrap_plain(_cn_turnover, "历史换手率")
exec_stock_shares = _wrap_plain(_stock_shares, "股本同步")
exec_hk_realtime = _wrap_hk(_hk_realtime, "港股实时采集")
exec_hk_historical = _wrap_hk(_hk_historical, "港股日K采集")
exec_hk_index_realtime = _wrap_hk(_hk_index_realtime, "港股指数实时")
exec_hk_index_historical = _wrap_hk(_hk_index_historical, "港股指数历史")
exec_etf_realtime = _wrap_cn(_etf_realtime, "ETF实时")
exec_etf_historical = _wrap_cn(_etf_historical, "ETF历史")
exec_cn_weekly = _wrap_cn(_gen_cn_weekly, "A股周K")
exec_cn_monthly = _wrap_cn(_gen_cn_monthly, "A股月K")
exec_cn_quarterly = _wrap_cn(_gen_cn_quarterly, "A股季K")
exec_cn_semiannual = _wrap_cn(_gen_cn_semiannual, "A股半年K")
exec_cn_annual = _wrap_cn(_gen_cn_annual, "A股年K")
exec_hk_weekly = _wrap_hk(_gen_hk_weekly, "港股周K")
exec_hk_monthly = _wrap_hk(_gen_hk_monthly, "港股月K")
exec_hk_quarterly = _wrap_hk(_gen_hk_quarterly, "港股季K")
exec_hk_semiannual = _wrap_hk(_gen_hk_semiannual, "港股半年K")
exec_hk_annual = _wrap_hk(_gen_hk_annual, "港股年K")
exec_gms_cn = _wrap_plain(_gms_cn, "GMS信号预计算(A股)")
exec_gms_hk = _wrap_plain(_gms_hk, "GMS信号预计算(港股)")
exec_urt_cn = _wrap_plain(_urt_cn, "URT信号预计算(A股)")
exec_urt_hk = _wrap_plain(_urt_hk, "URT信号预计算(港股)")
exec_sbbr_cn = _wrap_plain(_sbbr_cn, "SBBR信号预计算")
exec_rpe_cn = _wrap_plain(_rpe_cn, "RPE信号预计算")
exec_market_news = _wrap_plain(_market_news, "市场新闻采集")
exec_watchlist_history = _wrap_plain(_watchlist_history, "自选股历史")
exec_triple_volume_scan = _wrap_plain(_triple_volume_scan, "3倍量扫描")
