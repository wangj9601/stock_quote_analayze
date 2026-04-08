import os
import sys
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # 生产环境可无 python-dotenv，依赖系统环境变量
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from backend_core.data_collectors.akshare.realtime import AkshareRealtimeQuoteCollector
from backend_core.data_collectors.akshare.historical_turnover_rate import HistoricalTurnoverRateCollector
from backend_core.data_collectors.akshare.stock_shares_collector import StockSharesCollector
from backend_core.data_collectors.tushare.historical import HistoricalQuoteCollector
from backend_core.data_collectors.tushare.realtime import RealtimeQuoteCollector
from backend_core.config.config import DATA_COLLECTORS
from backend_core.data_collectors.akshare.realtime_index_spot_ak import RealtimeIndexSpotAkCollector
from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import RealtimeStockIndustryBoardCollector
from backend_core.data_collectors.akshare.realtime_stock_notice_report_ak import AkshareStockNoticeReportCollector
from backend_core.data_collectors.akshare.hk_realtime import HKRealtimeQuoteCollector
from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector
from backend_core.data_collectors.akshare.hk_index_realtime import HKIndexRealtimeCollector
from backend_core.data_collectors.akshare.hk_index_historical_collector import HKIndexHistoricalCollector
from apscheduler.schedulers.background import BackgroundScheduler
from backend_core.data_collectors.akshare.watchlist_history_collector import collect_watchlist_history
from backend_core.data_collectors.news_collector import NewsCollector
from backend_core.data_collectors.akshare.weekly_collector import WeeklyDataGenerator
from backend_core.data_collectors.akshare.hk_weekly_collector import HKWeeklyDataGenerator
from backend_core.data_collectors.akshare.monthly_collector import MonthlyDataGenerator
from backend_core.data_collectors.akshare.hk_monthly_collector import HKMonthlyDataGenerator
from backend_core.data_collectors.akshare.quarterly_collector import QuarterlyDataGenerator
from backend_core.data_collectors.akshare.hk_quarterly_collector import HKQuarterlyDataGenerator
from backend_core.data_collectors.akshare.semiannual_collector import SemiAnnualDataGenerator
from backend_core.data_collectors.akshare.hk_semiannual_collector import HKSemiAnnualDataGenerator
from backend_core.data_collectors.akshare.annual_collector import AnnualDataGenerator
from backend_core.data_collectors.akshare.hk_annual_collector import HKAnnualDataGenerator
import time
from backend_api.database import SessionLocal as ApiSessionLocal
from sqlalchemy import text

# 加载项目根目录 .env（有 python-dotenv 时；生产环境无则使用系统环境变量）
_project_root = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(_project_root / ".env")


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# 初始化采集器
ak_collector = AkshareRealtimeQuoteCollector(DATA_COLLECTORS.get('akshare', {}))
ak_turnover_collector = HistoricalTurnoverRateCollector(DATA_COLLECTORS.get('akshare', {}))
stock_shares_collector = StockSharesCollector(DATA_COLLECTORS.get('akshare', {}))
tushare_hist_collector = HistoricalQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
tushare_realtime_collector = RealtimeQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
index_collector = RealtimeIndexSpotAkCollector()
industry_board_collector = RealtimeStockIndustryBoardCollector()
notice_collector = AkshareStockNoticeReportCollector(DATA_COLLECTORS.get('akshare', {}))
news_collector = NewsCollector()
hk_realtime_collector = HKRealtimeQuoteCollector(DATA_COLLECTORS.get('akshare', {}))
hk_historical_collector = HKHistoricalQuoteCollector(DATA_COLLECTORS.get('akshare', {}))
hk_index_collector = HKIndexRealtimeCollector()
hk_index_historical_collector = HKIndexHistoricalCollector()
weekly_generator = WeeklyDataGenerator()
hk_weekly_generator = HKWeeklyDataGenerator()
monthly_generator = MonthlyDataGenerator()
hk_monthly_generator = HKMonthlyDataGenerator()
quarterly_generator = QuarterlyDataGenerator()
hk_quarterly_generator = HKQuarterlyDataGenerator()
semiannual_generator = SemiAnnualDataGenerator()
hk_semiannual_generator = HKSemiAnnualDataGenerator()
annual_generator = AnnualDataGenerator()
hk_annual_generator = HKAnnualDataGenerator()

scheduler = BlockingScheduler()


def _is_market_holiday(market: str, trade_date: str) -> bool:
    """
    按 trading_calendar 判断是否节假日（优先级最高）。
    market: CN / HK
    trade_date: YYYY-MM-DD
    """
    session = ApiSessionLocal()
    try:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM trading_calendar
                WHERE market = :market
                  AND holiday_date = CAST(:trade_date AS DATE)
                LIMIT 1
                """
            ),
            {"market": str(market).upper(), "trade_date": trade_date},
        ).fetchone()
        return row is not None
    except Exception as e:
        # 节假日表查询失败时不阻断采集，避免误停全链路。
        logging.warning(f"查询 trading_calendar 失败，跳过节假日短路: market={market}, date={trade_date}, err={e}")
        return False
    finally:
        session.close()

def collect_akshare_realtime():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _is_market_holiday('CN', today_str):
            logging.info(f"[定时任务] A股 {today_str} 为节假日（trading_calendar），跳过实时行情采集。")
            return
        logging.info("[定时任务] AKShare 实时行情采集开始...")
        df = ak_collector.collect_quotes()
    except Exception as e:
        logging.error(f"[定时任务] AKShare 实时行情采集异常: {e}")

def collect_akshare_index_realtime(): 
    try:
        logging.info("[定时任务] AKShare 指数实时行情采集开始...")
        df = index_collector.collect_quotes()
        logging.info(f"[定时任务] AKShare 指数实时行情采集完成，采集到 {len(df)} 条数据")
    except Exception as e:
        logging.error(f"[定时任务] 实时行情采集异常: {e}")

def collect_tushare_historical():
    try:
        today = datetime.now()
        today_str_dash = today.strftime('%Y-%m-%d')
        if _is_market_holiday('CN', today_str_dash):
            logging.info(f"[定时任务] A股 {today_str_dash} 为节假日（trading_calendar），跳过历史行情采集。")
            return
        if today.weekday() in (5, 6):
            logging.info("[定时任务] 今天是周末，不执行 A 股历史行情采集。")
            return
        today_str = today.strftime('%Y%m%d')
        logging.info(f"[定时任务] A 股历史行情采集开始，日期: {today_str}")
        # 优先从 A 股实时行情表同步；若无对应交易日数据再走 tushare 接口
        if tushare_hist_collector.collect_historical_quotes_from_realtime(today_str):
            logging.info("[定时任务] A 股历史行情已从实时表同步完成")
        else:
            tushare_hist_collector.collect_historical_quotes(today_str)
            logging.info("[定时任务] A 股历史行情从 Tushare 采集完成")
    except Exception as e:
        logging.error(f"[定时任务] A 股历史行情采集异常: {e}")

def collect_tushare_realtime():
    try:
        logging.info("[定时任务] Tushare 实时行情采集开始...")
        tushare_realtime_collector.collect_quotes()
        logging.info("[定时任务] Tushare 实时行情采集完成")
    except Exception as e:
        logging.error(f"[定时任务] Tushare 实时行情采集异常: {e}")

def collect_akshare_industry_board_realtime():
    try:
        logging.info("[定时任务] 行业板块实时行情采集开始...")
        industry_board_collector.run()
        logging.info("[定时任务] 行业板块实时行情采集完成")
    except Exception as e:
        logging.error(f"[定时任务] 行业板块实时行情采集异常: {e}")

def collect_akshare_stock_notices():
    try:
        logging.info("[定时任务] A股公告数据采集开始...")
        result = notice_collector.collect_stock_notices(symbol="全部")
        if result:
            logging.info("[定时任务] A股公告数据采集完成")
        else:
            logging.warning("[定时任务] A股公告数据采集失败")
    except Exception as e:
        logging.error(f"[定时任务] A股公告数据采集异常: {e}")

def collect_akshare_turnover_rate():
    try:
        logging.info("[定时任务] AKShare 历史换手率数据采集开始...")
        turnover_days = _env_int("COLLECTOR_TURNOVER_RATE_DAYS", 30)
        success = ak_turnover_collector.collect_missing_turnover_rate(turnover_days)
        if success:
            logging.info("[定时任务] AKShare 历史换手率数据采集完成")
        else:
            logging.warning("[定时任务] AKShare 历史换手率数据采集部分失败")
    except Exception as e:
        logging.error(f"[定时任务] AKShare 历史换手率数据采集异常: {e}")

def update_stock_shares():
    try:
        logging.info("[定时任务] 股本数据更新开始...")
        result = stock_shares_collector.run(mode='incremental')
        if result and result.get('success', 0) > 0:
            logging.info(f"[定时任务] 股本数据更新完成: {result}")
        else:
            logging.warning(f"[定时任务] 股本数据更新结果: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 股本数据更新异常: {e}")

def run_watchlist_history_collection():
    try:
        logging.info("[定时任务] 自选股历史行情采集开始...")
        result = collect_watchlist_history()
        if result:
            logging.info("[定时任务] 自选股历史行情采集完成")
            print(f"自选股历史行情采集成功个股数量: {result.get('success', 0)}，失败个股数量: {result.get('fail', 0)}")
    except Exception as e:
        logging.error(f"[定时任务] 自选股历史行情采集异常: {e}")

def collect_market_news():
    try:
        logging.info("[定时任务] 市场新闻采集开始...")
        result = news_collector.collect_and_save_market_news()
        if result["success"]:
            logging.info(f"[定时任务] 市场新闻采集完成: {result['message']}")
        else:
            logging.error(f"[定时任务] 市场新闻采集失败: {result['message']}")
    except Exception as e:
        logging.error(f"[定时任务] 市场新闻采集异常: {e}")

def update_hot_news():
    try:
        logging.info("[定时任务] 热门资讯更新开始...")
        success = news_collector.update_hot_news()
        if success:
            logging.info("[定时任务] 热门资讯更新完成")
        else:
            logging.error("[定时任务] 热门资讯更新失败")
    except Exception as e:
        logging.error(f"[定时任务] 热门资讯更新异常: {e}")

def cleanup_old_news():
    try:
        logging.info("[定时任务] 旧新闻清理开始...")
        deleted_count = news_collector.cleanup_old_news(days=30)
        logging.info(f"[定时任务] 旧新闻清理完成，删除了 {deleted_count} 条记录")
    except Exception as e:
        logging.error(f"[定时任务] 旧新闻清理异常: {e}")

def collect_hk_realtime():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _is_market_holiday('HK', today_str):
            logging.info(f"[定时任务] 港股 {today_str} 为节假日（trading_calendar），跳过实时行情采集。")
            return
        logging.info("[定时任务] 港股实时行情采集开始...")
        success = hk_realtime_collector.collect_quotes()
        if success:
            logging.info("[定时任务] 港股实时行情采集完成")
        else:
            logging.warning("[定时任务] 港股实时行情采集失败")
    except Exception as e:
        logging.error(f"[定时任务] 港股实时行情采集异常: {e}")

def collect_hk_historical():
    try:
        today = datetime.now()
        today_str_dash = today.strftime('%Y-%m-%d')
        if _is_market_holiday('HK', today_str_dash):
            logging.info(f"[定时任务] 港股 {today_str_dash} 为节假日（trading_calendar），跳过历史行情采集。")
            return
        if today.weekday() in (5, 6):
            logging.info("[定时任务] 今天是周末，不执行港股历史行情采集。")
            return
        today = today.strftime('%Y%m%d')
        logging.info(f"[定时任务] 港股历史行情采集开始，日期: {today}")
        success = hk_historical_collector.collect_historical_quotes(today)
        if success:
            logging.info("[定时任务] 港股历史行情采集完成")
        else:
            logging.warning("[定时任务] 港股历史行情采集失败")
    except Exception as e:
        logging.error(f"[定时任务] 港股历史行情采集异常: {e}")

def generate_weekly_data():
    try:
        logging.info("[定时任务] A股当前周线数据生成开始...")
        result = weekly_generator.generate_current_week_data()
        logging.info(f"[定时任务] A股当前周线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前周线数据生成异常: {e}")

def generate_hk_weekly_data():
    try:
        logging.info("[定时任务] 港股当前周线数据生成开始...")
        result = hk_weekly_generator.generate_current_week_data()
        logging.info(f"[定时任务] 港股当前周线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前周线数据生成异常: {e}")

def generate_monthly_data():
    try:
        logging.info("[定时任务] A股当前月线数据生成开始...")
        result = monthly_generator.generate_current_month_data()
        logging.info(f"[定时任务] A股当前月线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前月线数据生成异常: {e}")

def generate_hk_monthly_data():
    try:
        logging.info("[定时任务] 港股当前月线数据生成开始...")
        result = hk_monthly_generator.generate_current_month_data()
        logging.info(f"[定时任务] 港股当前月线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前月线数据生成异常: {e}")

def generate_quarterly_data():
    try:
        logging.info("[定时任务] A股当前季线数据生成开始...")
        result = quarterly_generator.generate_current_quarter_data()
        logging.info(f"[定时任务] A股当前季线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前季线数据生成异常: {e}")

def generate_hk_quarterly_data():
    try:
        logging.info("[定时任务] 港股当前季线数据生成开始...")
        result = hk_quarterly_generator.generate_current_quarter_data()
        logging.info(f"[定时任务] 港股当前季线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前季线数据生成异常: {e}")

def generate_semiannual_data():
    try:
        logging.info("[定时任务] A股当前半年线数据生成开始...")
        result = semiannual_generator.generate_current_semiannual_data()
        logging.info(f"[定时任务] A股当前半年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前半年线数据生成异常: {e}")

def generate_hk_semiannual_data():
    try:
        logging.info("[定时任务] 港股当前半年线数据生成开始...")
        result = hk_semiannual_generator.generate_current_semiannual_data()
        logging.info(f"[定时任务] 港股当前半年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前半年线数据生成异常: {e}")

def generate_annual_data():
    try:
        logging.info("[定时任务] A股当前年线数据生成开始...")
        result = annual_generator.generate_current_annual_data()
        logging.info(f"[定时任务] A股当前年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前年线数据生成异常: {e}")

def generate_hk_annual_data():
    try:
        logging.info("[定时任务] 港股当前年线数据生成开始...")
        result = hk_annual_generator.generate_current_annual_data()
        logging.info(f"[定时任务] 港股当前年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前年线数据生成异常: {e}")

def collect_hk_index_realtime():
    try:
        logging.info("[定时任务] 港股指数实时行情采集开始...")
        result = hk_index_collector.collect_realtime_quotes()
        if result:
            logging.info(f"[定时任务] 港股指数实时行情采集完成，采集到 {len(result)} 条数据")
        else:
            logging.warning("[定时任务] 港股指数实时行情采集失败")
    except Exception as e:
        logging.error(f"[定时任务] 港股指数实时行情采集异常: {e}")

def collect_hk_index_historical():
    try:
        logging.info("[定时任务] 港股指数历史行情采集开始...")
        result = hk_index_historical_collector.collect_daily_to_historical()
        if result and result.get('success', 0) > 0:
            logging.info(f"[定时任务] 港股指数历史行情采集完成: {result.get('message', '')}")
        else:
            logging.warning(f"[定时任务] 港股指数历史行情采集失败: {result.get('message', '未知错误')}")
    except Exception as e:
        logging.error(f"[定时任务] 港股指数历史行情采集异常: {e}")

# 定时任务配置：从 .env 读取 cron 参数，未设置则用下方默认值
def _cron(k: str, default: str) -> str:
    return _env(k, default)

def _cron_int(k: str, default: int):
    return _env_int(k, default)


def _env_bool(k: str, default: bool = True) -> bool:
    v = (os.getenv(k) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _register_gms_signal_precompute_jobs():
    """定时将 GMS 信号写入 gms_signal_trace（全 A、全港股、自定义池、全量自关注并集），供选股页优先读库。"""
    if not _env_bool("ENABLE_GMS_PRECOMPUTE", True):
        logging.info("GMS 信号预计算已禁用（ENABLE_GMS_PRECOMPUTE=false）")
        return
    try:
        from backend_core.strategies.gms.scheduled_precompute import (
            scheduled_gms_signals_cn,
            scheduled_gms_signals_hk,
            scheduled_gms_signals_custom,
            scheduled_gms_signals_watchlist,
        )
    except Exception as e:
        logging.error("导入 GMS 预计算任务失败，跳过注册: %s", e)
        return

    scheduler.add_job(
        scheduled_gms_signals_cn,
        "cron",
        day_of_week=_cron("SCHED_GMS_SIGNALS_CN_DOW", "mon-fri"),
        hour=_cron_int("SCHED_GMS_SIGNALS_CN_HOUR", 18),
        minute=_cron_int("SCHED_GMS_SIGNALS_CN_MINUTE", 20),
        id="gms_signals_cn",
    )
    scheduler.add_job(
        scheduled_gms_signals_hk,
        "cron",
        day_of_week=_cron("SCHED_GMS_SIGNALS_HK_DOW", "mon-fri"),
        hour=_cron_int("SCHED_GMS_SIGNALS_HK_HOUR", 18),
        minute=_cron_int("SCHED_GMS_SIGNALS_HK_MINUTE", 50),
        id="gms_signals_hk",
    )
    scheduler.add_job(
        scheduled_gms_signals_custom,
        "cron",
        day_of_week=_cron("SCHED_GMS_SIGNALS_CUSTOM_DOW", "mon-fri"),
        hour=_cron_int("SCHED_GMS_SIGNALS_CUSTOM_HOUR", 19),
        minute=_cron_int("SCHED_GMS_SIGNALS_CUSTOM_MINUTE", 10),
        id="gms_signals_custom",
    )
    scheduler.add_job(
        scheduled_gms_signals_watchlist,
        "cron",
        day_of_week=_cron("SCHED_GMS_SIGNALS_WATCHLIST_DOW", "mon-fri"),
        hour=_cron_int("SCHED_GMS_SIGNALS_WATCHLIST_HOUR", 19),
        minute=_cron_int("SCHED_GMS_SIGNALS_WATCHLIST_MINUTE", 25),
        id="gms_signals_watchlist",
    )
    logging.info(
        "已注册 GMS 信号预计算任务（ENABLE_GMS_PRECOMPUTE=true）：A股/港股/自定义池/自关注并集，"
        "自定义代码见 .env GMS_CUSTOM_STOCK_CODES"
    )


_register_gms_signal_precompute_jobs()

scheduler.add_job(collect_akshare_realtime, 'cron',
    day_of_week=_cron('SCHED_AKSHARE_REALTIME_DOW', 'mon-fri'),
    hour=_cron('SCHED_AKSHARE_REALTIME_HOUR', '15'),
    minute=_cron_int('SCHED_AKSHARE_REALTIME_MINUTE', 31),
    id='akshare_realtime')
scheduler.add_job(collect_tushare_historical, 'cron',
    hour=_cron('SCHED_TUSHARE_HISTORICAL_HOUR', '16'),
    minute=_cron_int('SCHED_TUSHARE_HISTORICAL_MINUTE', 2),
    id='tushare_historical')
scheduler.add_job(collect_akshare_index_realtime, 'cron',
    day_of_week=_cron('SCHED_AKSHARE_INDEX_REALTIME_DOW', 'mon-fri'),
    hour=_cron('SCHED_AKSHARE_INDEX_REALTIME_HOUR', '11,15'),
    minute=_cron_int('SCHED_AKSHARE_INDEX_REALTIME_MINUTE', 59),
    id='akshare_index_realtime')
scheduler.add_job(collect_akshare_industry_board_realtime, 'cron',
    day_of_week=_cron('SCHED_AKSHARE_INDUSTRY_DOW', 'mon-fri'),
    hour=_cron('SCHED_AKSHARE_INDUSTRY_HOUR', '11,16'),
    minute=_cron_int('SCHED_AKSHARE_INDUSTRY_MINUTE', 3),
    id='akshare_industry_board_realtime')
# scheduler.add_job(collect_akshare_stock_notices, 'interval', minutes=2400, id='akshare_stock_notices')
scheduler.add_job(collect_akshare_turnover_rate, 'cron',
    day_of_week=_cron('SCHED_AKSHARE_TURNOVER_DOW', 'mon-fri'),
    hour=_cron('SCHED_AKSHARE_TURNOVER_HOUR', '11'),
    minute=_cron_int('SCHED_AKSHARE_TURNOVER_MINUTE', 13),
    id='akshare_turnover_rate')
scheduler.add_job(update_stock_shares, 'cron',
    day_of_week=_cron('SCHED_STOCK_SHARES_DOW', 'sat'),
    hour=_cron_int('SCHED_STOCK_SHARES_HOUR', 10),
    minute=_cron_int('SCHED_STOCK_SHARES_MINUTE', 0),
    id='stock_shares_update')
# scheduler.add_job(run_watchlist_history_collection, 'cron', minute='*/2', id='watchlist_history_every_5_minutes')
# scheduler.add_job(collect_market_news, 'interval', minutes=1440, id='market_news_collection')
# scheduler.add_job(update_hot_news, 'interval', hours=1, id='hot_news_update')
# scheduler.add_job(cleanup_old_news, 'cron', hour=23, minute=0, id='old_news_cleanup')
scheduler.add_job(collect_hk_realtime, 'cron',
    day_of_week=_cron('SCHED_HK_REALTIME_DOW', 'mon-fri'),
    hour=_cron('SCHED_HK_REALTIME_HOUR', '16'),
    minute=_cron_int('SCHED_HK_REALTIME_MINUTE', 39),
    id='hk_realtime')
scheduler.add_job(collect_hk_historical, 'cron',
    day_of_week=_cron('SCHED_HK_HISTORICAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_HISTORICAL_HOUR', 16),
    minute=_cron_int('SCHED_HK_HISTORICAL_MINUTE', 55),
    id='hk_historical')
scheduler.add_job(generate_weekly_data, 'cron',
    day_of_week=_cron('SCHED_WEEKLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_WEEKLY_HOUR', 16),
    minute=_cron_int('SCHED_WEEKLY_MINUTE', 25),
    id='generate_weekly')
scheduler.add_job(generate_hk_weekly_data, 'cron',
    day_of_week=_cron('SCHED_HK_WEEKLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_WEEKLY_HOUR', 17),
    minute=_cron_int('SCHED_HK_WEEKLY_MINUTE', 1),
    id='generate_hk_weekly')
scheduler.add_job(generate_monthly_data, 'cron',
    day_of_week=_cron('SCHED_MONTHLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_MONTHLY_HOUR', 16),
    minute=_cron_int('SCHED_MONTHLY_MINUTE', 30),
    id='generate_monthly')
scheduler.add_job(generate_hk_monthly_data, 'cron',
    day_of_week=_cron('SCHED_HK_MONTHLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_MONTHLY_HOUR', 17),
    minute=_cron_int('SCHED_HK_MONTHLY_MINUTE', 5),
    id='generate_hk_monthly')
scheduler.add_job(generate_quarterly_data, 'cron',
    day_of_week=_cron('SCHED_QUARTERLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_QUARTERLY_HOUR', 16),
    minute=_cron_int('SCHED_QUARTERLY_MINUTE', 35),
    id='generate_quarterly')
scheduler.add_job(generate_hk_quarterly_data, 'cron',
    day_of_week=_cron('SCHED_HK_QUARTERLY_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_QUARTERLY_HOUR', 17),
    minute=_cron_int('SCHED_HK_QUARTERLY_MINUTE', 9),
    id='generate_hk_quarterly')
#scheduler.add_job(generate_semiannual_data, 'cron',
#    day_of_week=_cron('SCHED_SEMIANNUAL_DOW', 'mon-fri'),
#    hour=_cron_int('SCHED_SEMIANNUAL_HOUR', 16),
#    minute=_cron_int('SCHED_SEMIANNUAL_MINUTE', 42),
#    id='generate_semiannual')
#scheduler.add_job(generate_hk_semiannual_data, 'cron',
#    day_of_week=_cron('SCHED_HK_SEMIANNUAL_DOW', 'mon-fri'),
#    hour=_cron_int('SCHED_HK_SEMIANNUAL_HOUR', 17),
#    minute=_cron_int('SCHED_HK_SEMIANNUAL_MINUTE', 13),
#    id='generate_hk_semiannual')
scheduler.add_job(generate_annual_data, 'cron',
    day_of_week=_cron('SCHED_ANNUAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_ANNUAL_HOUR', 16),
    minute=_cron_int('SCHED_ANNUAL_MINUTE', 47),
    id='generate_annual')
scheduler.add_job(generate_hk_annual_data, 'cron',
    day_of_week=_cron('SCHED_HK_ANNUAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_ANNUAL_HOUR', 17),
    minute=_cron_int('SCHED_HK_ANNUAL_MINUTE', 16),
    id='generate_hk_annual')
scheduler.add_job(collect_hk_index_realtime, 'cron',
    day_of_week=_cron('SCHED_HK_INDEX_REALTIME_DOW', 'mon-fri'),
    hour=_cron('SCHED_HK_INDEX_REALTIME_HOUR', '12,16'),
    minute=_cron_int('SCHED_HK_INDEX_REALTIME_MINUTE', 35),
    id='hk_index_realtime')
scheduler.add_job(collect_hk_index_historical, 'cron',
    day_of_week=_cron('SCHED_HK_INDEX_HISTORICAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_HK_INDEX_HISTORICAL_HOUR', 17),
    minute=_cron_int('SCHED_HK_INDEX_HISTORICAL_MINUTE', 18),
    id='hk_index_historical')

if __name__ == "__main__":
    enable_sched = os.getenv('ENABLE_SCHEDULED_COLLECTION', 'true').lower() in ('true', '1', 'yes')
    if not enable_sched:
        logging.info("定时采集任务已根据 ENABLE_SCHEDULED_COLLECTION 配置禁用。")
        sys.exit(0)

    logging.info("启动定时采集任务...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("定时任务已停止。")