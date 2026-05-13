import os
import sys
import logging
from pathlib import Path
from typing import Union

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # 生产环境可无 python-dotenv，依赖系统环境变量
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from backend_core.data_collectors.akshare.realtime import AkshareRealtimeQuoteCollector
from backend_core.data_collectors.akshare.historical_turnover_rate import HistoricalTurnoverRateCollector
from backend_core.data_collectors.akshare.stock_shares_collector import StockSharesCollector, StockSharesSyncAbortError
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
from backend_core.data_collectors.akshare.etf_collector import ETFCollector
from backend_core.data_collectors.akshare.quarterly_collector import QuarterlyDataGenerator
from backend_core.data_collectors.akshare.hk_quarterly_collector import HKQuarterlyDataGenerator
from backend_core.data_collectors.akshare.semiannual_collector import SemiAnnualDataGenerator
from backend_core.data_collectors.akshare.hk_semiannual_collector import HKSemiAnnualDataGenerator
from backend_core.data_collectors.akshare.annual_collector import AnnualDataGenerator
from backend_core.data_collectors.akshare.hk_annual_collector import HKAnnualDataGenerator
import time
import pandas as pd
from backend_api.database import SessionLocal as ApiSessionLocal
from backend_api.utils.trading_calendar_utils import is_market_session_closed
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
etf_collector_instance = ETFCollector()

scheduler = BlockingScheduler()


def _cn_session_closed_today() -> bool:
    """A 股侧今日是否休市：周六日或 trading_calendar(CN)。查询失败时不跳过。"""
    session = ApiSessionLocal()
    try:
        return is_market_session_closed(session, "CN", datetime.now().date())
    except Exception as e:
        logging.warning(f"A股休市判定异常，不跳过采集: {e}")
        return False
    finally:
        session.close()


def _hk_session_closed_today() -> bool:
    """港股侧今日是否休市：周六日或 trading_calendar(HK)。查询失败时不跳过。"""
    session = ApiSessionLocal()
    try:
        return is_market_session_closed(session, "HK", datetime.now().date())
    except Exception as e:
        logging.warning(f"港股休市判定异常，不跳过采集: {e}")
        return False
    finally:
        session.close()

def collect_akshare_realtime():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _cn_session_closed_today():
            logging.info(f"[定时任务] A股 {today_str} 为休市日（周末或 trading_calendar），跳过实时行情采集。")
            return
        logging.info("[定时任务] AKShare 实时行情采集开始...")
        df = ak_collector.collect_quotes()
    except Exception as e:
        logging.error(f"[定时任务] AKShare 实时行情采集异常: {e}")

def collect_akshare_index_realtime(): 
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _cn_session_closed_today():
            logging.info(f"[定时任务] A股 {today_str} 为休市日，跳过指数实时行情采集。")
            return
        logging.info("[定时任务] AKShare 指数实时行情采集开始...")
        df = index_collector.collect_quotes()
        logging.info(f"[定时任务] AKShare 指数实时行情采集完成，采集到 {len(df)} 条数据")
    except Exception as e:
        logging.error(f"[定时任务] 实时行情采集异常: {e}")

def collect_tushare_historical():
    try:
        today = datetime.now()
        today_str_dash = today.strftime('%Y-%m-%d')
        if _cn_session_closed_today():
            logging.info(f"[定时任务] A股 {today_str_dash} 为休市日，跳过历史行情采集。")
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


def run_job_triple_volume_scan():
    """日终：3倍量爆量扫描入库（受 TRIPLE_VOLUME_OBSERVE_ENABLED 控制）。"""
    try:
        db = ApiSessionLocal()
        try:
            from backend_core.strategies.triple_volume_observe.scan_job import run_triple_volume_scan

            out = run_triple_volume_scan(db)
            if out.get("skipped"):
                logging.info("[定时任务] 3倍量观察股爆量扫描跳过: %s", out.get("reason"))
        finally:
            db.close()
    except Exception as e:
        logging.error("[定时任务] 3倍量观察股爆量扫描异常: %s", e)


def run_job_triple_volume_eval():
    """日终：3倍量观察股 VSB 状态复核（受 TRIPLE_VOLUME_OBSERVE_ENABLED 控制）。"""
    try:
        db = ApiSessionLocal()
        try:
            from backend_core.strategies.triple_volume_observe.eval_job import run_triple_volume_eval

            out = run_triple_volume_eval(db)
            if out.get("skipped"):
                logging.info("[定时任务] 3倍量观察股VSB复核跳过: %s", out.get("reason"))
        finally:
            db.close()
    except Exception as e:
        logging.error("[定时任务] 3倍量观察股VSB复核异常: %s", e)


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
    if not _env_bool("SCHED_AKSHARE_TURNOVER_ENABLED", False):
        logging.info("[定时任务] AKShare 历史换手率数据采集已关闭（SCHED_AKSHARE_TURNOVER_ENABLED 未设为 true），跳过。")
        return
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
    if not _env_bool("SCHED_STOCK_SHARES_ENABLED", True):
        logging.info("[定时任务] 股本定时同步已关闭（SCHED_STOCK_SHARES_ENABLED=false），跳过。")
        return
    source = _env("STOCK_SHARES_UPDATE_SOURCE", "akshare").lower()
    try:
        logging.info("[定时任务] 股本数据更新开始... source=%s", source)
        if source == "excel":
            xls = _resolve_optional_project_path(_env("STOCK_SHARES_EXCEL_PATH", ""))
            if not xls:
                logging.error(
                    "[定时任务] STOCK_SHARES_UPDATE_SOURCE=excel 但未配置 STOCK_SHARES_EXCEL_PATH"
                )
                return
            sheet_raw = _env("STOCK_SHARES_EXCEL_SHEET", "").strip()
            sheet_kw: Union[int, str] = 0
            if sheet_raw:
                try:
                    sheet_kw = int(sheet_raw)
                except ValueError:
                    sheet_kw = sheet_raw
            result = stock_shares_collector.collect_shares_from_excel(
                xls, sheet_name=sheet_kw
            )
        else:
            if source not in ("akshare", ""):
                logging.warning(
                    "[定时任务] STOCK_SHARES_UPDATE_SOURCE=%s 未识别，按 akshare 处理",
                    source,
                )
            result = stock_shares_collector.run(mode="incremental")
        if result and result.get("success", 0) > 0:
            logging.info(f"[定时任务] 股本数据更新完成: {result}")
        else:
            logging.warning(f"[定时任务] 股本数据更新结果: {result}")
    except StockSharesSyncAbortError as e:
        logging.critical(f"[定时任务] 股本数据更新触发强制退出: {e}")
        # 按需求：失败股票数超过阈值后，强制结束整个同步程序进程
        os._exit(1)
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
        if _hk_session_closed_today():
            logging.info(f"[定时任务] 港股 {today_str} 为休市日（周末或 trading_calendar），跳过实时行情采集。")
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
        if _hk_session_closed_today():
            logging.info(f"[定时任务] 港股 {today_str_dash} 为休市日，跳过历史行情采集。")
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
        if _cn_session_closed_today():
            logging.info("[定时任务] A股休市日，跳过周线数据生成。")
            return
        logging.info("[定时任务] A股当前周线数据生成开始...")
        result = weekly_generator.generate_current_week_data()
        logging.info(f"[定时任务] A股当前周线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前周线数据生成异常: {e}")

def generate_hk_weekly_data():
    try:
        if _hk_session_closed_today():
            logging.info("[定时任务] 港股休市日，跳过周线数据生成。")
            return
        logging.info("[定时任务] 港股当前周线数据生成开始...")
        result = hk_weekly_generator.generate_current_week_data()
        logging.info(f"[定时任务] 港股当前周线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前周线数据生成异常: {e}")

def generate_monthly_data():
    try:
        if _cn_session_closed_today():
            logging.info("[定时任务] A股休市日，跳过月线数据生成。")
            return
        logging.info("[定时任务] A股当前月线数据生成开始...")
        result = monthly_generator.generate_current_month_data()
        logging.info(f"[定时任务] A股当前月线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前月线数据生成异常: {e}")

def generate_hk_monthly_data():
    try:
        if _hk_session_closed_today():
            logging.info("[定时任务] 港股休市日，跳过月线数据生成。")
            return
        logging.info("[定时任务] 港股当前月线数据生成开始...")
        result = hk_monthly_generator.generate_current_month_data()
        logging.info(f"[定时任务] 港股当前月线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前月线数据生成异常: {e}")

def generate_quarterly_data():
    try:
        if _cn_session_closed_today():
            logging.info("[定时任务] A股休市日，跳过季线数据生成。")
            return
        logging.info("[定时任务] A股当前季线数据生成开始...")
        result = quarterly_generator.generate_current_quarter_data()
        logging.info(f"[定时任务] A股当前季线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前季线数据生成异常: {e}")

def generate_hk_quarterly_data():
    try:
        if _hk_session_closed_today():
            logging.info("[定时任务] 港股休市日，跳过季线数据生成。")
            return
        logging.info("[定时任务] 港股当前季线数据生成开始...")
        result = hk_quarterly_generator.generate_current_quarter_data()
        logging.info(f"[定时任务] 港股当前季线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前季线数据生成异常: {e}")

def generate_semiannual_data():
    try:
        if _cn_session_closed_today():
            logging.info("[定时任务] A股休市日，跳过半年线数据生成。")
            return
        logging.info("[定时任务] A股当前半年线数据生成开始...")
        result = semiannual_generator.generate_current_semiannual_data()
        logging.info(f"[定时任务] A股当前半年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前半年线数据生成异常: {e}")

def generate_hk_semiannual_data():
    try:
        if _hk_session_closed_today():
            logging.info("[定时任务] 港股休市日，跳过半年线数据生成。")
            return
        logging.info("[定时任务] 港股当前半年线数据生成开始...")
        result = hk_semiannual_generator.generate_current_semiannual_data()
        logging.info(f"[定时任务] 港股当前半年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前半年线数据生成异常: {e}")

def generate_annual_data():
    try:
        if _cn_session_closed_today():
            logging.info("[定时任务] A股休市日，跳过年线数据生成。")
            return
        logging.info("[定时任务] A股当前年线数据生成开始...")
        result = annual_generator.generate_current_annual_data()
        logging.info(f"[定时任务] A股当前年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] A股当前年线数据生成异常: {e}")

def generate_hk_annual_data():
    try:
        if _hk_session_closed_today():
            logging.info("[定时任务] 港股休市日，跳过年线数据生成。")
            return
        logging.info("[定时任务] 港股当前年线数据生成开始...")
        result = hk_annual_generator.generate_current_annual_data()
        logging.info(f"[定时任务] 港股当前年线数据生成完成: {result}")
    except Exception as e:
        logging.error(f"[定时任务] 港股当前年线数据生成异常: {e}")

def collect_hk_index_realtime():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _hk_session_closed_today():
            logging.info(f"[定时任务] 港股 {today_str} 为休市日，跳过指数实时行情采集。")
            return
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
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _hk_session_closed_today():
            logging.info(f"[定时任务] 港股 {today_str} 为休市日，跳过指数历史行情归档。")
            return
        logging.info("[定时任务] 港股指数历史行情采集开始...")
        result = hk_index_historical_collector.collect_daily_to_historical()
        if result and result.get('success', 0) > 0:
            logging.info(f"[定时任务] 港股指数历史行情采集完成: {result.get('message', '')}")
        else:
            logging.warning(f"[定时任务] 港股指数历史行情采集失败: {result.get('message', '未知错误')}")
    except Exception as e:
        logging.error(f"[定时任务] 港股指数历史行情采集异常: {e}")

def collect_etf_realtime():
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        if _cn_session_closed_today():
            logging.info(f"[定时任务] A股(ETF) {today_str} 为休市日，跳过 ETF 实时行情采集。")
            return
        logging.info("[定时任务] ETF 实时行情采集开始...")
        
        df = None
        source = 'em'
        try:
            df = __import__('akshare').fund_etf_spot_em()
        except Exception as em_ex:
            logging.warning(f"东方财富 ETF 实时接口访问失败: {em_ex}，尝试切换新浪接口...")
            
        if df is None or df.empty:
            source = 'sina'
            try:
                df = __import__('akshare').fund_etf_category_sina(symbol="ETF基金")
            except Exception as sina_ex:
                logging.warning(f"新浪 ETF 实时接口也访问失败: {sina_ex}，尝试切换同花顺接口...")
                df = None
        
        if df is None or df.empty:
            source = 'ths'
            try:
                df = __import__('akshare').fund_etf_spot_ths()
            except Exception as ths_ex:
                logging.error(f"同花顺 ETF 实时接口最后也访问失败: {ths_ex}")
                return
                
        if df is not None and not df.empty:
            session = etf_collector_instance.session
            now = datetime.now()
            count = 0
            for _, row in df.iterrows():
                if source == 'em':
                    code = str(row.get('代码', ''))
                    if not code: continue
                    name = str(row.get('名称', ''))
                    current_price = float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else None
                    change_percent = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else None
                    volume = float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else None
                    amount = float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else None
                    high = float(row.get('最高', 0)) if pd.notna(row.get('最高')) else None
                    low = float(row.get('最低', 0)) if pd.notna(row.get('最低')) else None
                    open_price = float(row.get('今开', 0)) if pd.notna(row.get('今开')) else None
                    pre_close = float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else None
                    turnover_rate = float(row.get('换手率', 0)) if pd.notna(row.get('换手率')) else None
                    total_mv = float(row.get('总市值', 0)) if pd.notna(row.get('总市值')) else None
                    circulating_mv = float(row.get('流通市值', 0)) if pd.notna(row.get('流通市值')) else None
                elif source == 'sina':
                    code = str(row.get('代码', ''))
                    if not code: continue
                    name = str(row.get('名称', ''))
                    current_price = float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else None
                    change_percent = float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else None
                    volume = float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else None
                    amount = float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else None
                    high = float(row.get('最高', 0)) if pd.notna(row.get('最高')) else None
                    low = float(row.get('最低', 0)) if pd.notna(row.get('最低')) else None
                    open_price = float(row.get('今开', 0)) if pd.notna(row.get('今开')) else None
                    pre_close = float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else None
                    turnover_rate = total_mv = circulating_mv = None
                else: # ths
                    code = str(row.get('基金代码', ''))
                    if not code: continue
                    name = str(row.get('基金名称', ''))
                    current_price = float(row.get('当前-单位净值', 0)) if pd.notna(row.get('当前-单位净值')) else None
                    if current_price is None or current_price == 0:
                        current_price = float(row.get('最新-单位净值', 0)) if pd.notna(row.get('最新-单位净值')) else None
                    change_percent = float(row.get('增长率', 0)) if pd.notna(row.get('增长率')) else None
                    pre_close = float(row.get('前一日-单位净值', 0)) if pd.notna(row.get('前一日-单位净值')) else None
                    volume = amount = high = low = open_price = turnover_rate = total_mv = circulating_mv = None
                
                # 针对特定代码输出日志用于排查
                if code == '510300' or code == 'sh510300' or code == 'sz510300':
                    logging.info(f"[ETF排查] 代码: {code}, 数据源: {source}, 最新价: {current_price}, 成交量: {volume}, 成交额: {amount}")

                if code.startswith('sh') or code.startswith('sz'):
                    code = code[2:]
                
                # 更新基本信息表
                session.execute(text("""
                    INSERT INTO fund_basic_info (code, name, fund_type, collect_enabled, created_at, updated_at)
                    VALUES (:code, :name, 'ETF', TRUE, :now, :now)
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        updated_at = EXCLUDED.updated_at
                """), {
                    'code': code, 'name': name, 'now': now
                })

                session.execute(text("""
                    INSERT INTO fund_realtime_quote (code, trade_date, name, current_price, change_percent, volume, amount, high, low, open, pre_close, turnover_rate, total_market_value, circulating_market_value, update_time)
                    VALUES (:code, :trade_date, :name, :current_price, :change_percent, :volume, :amount, :high, :low, :open, :pre_close, :turnover_rate, :total_market_value, :circulating_market_value, :update_time)
                    ON CONFLICT (code, trade_date) DO UPDATE SET
                    name = EXCLUDED.name, current_price = EXCLUDED.current_price, change_percent = EXCLUDED.change_percent, volume = EXCLUDED.volume, amount = EXCLUDED.amount, high = EXCLUDED.high, low = EXCLUDED.low, open = EXCLUDED.open, pre_close = EXCLUDED.pre_close, turnover_rate = EXCLUDED.turnover_rate, total_market_value = EXCLUDED.total_market_value, circulating_market_value = EXCLUDED.circulating_market_value, update_time = EXCLUDED.update_time
                """), {
                    'code': code, 'trade_date': today_str, 'name': name, 'current_price': current_price, 'change_percent': change_percent, 'volume': volume, 'amount': amount, 'high': high, 'low': low, 'open': open_price, 'pre_close': pre_close, 'turnover_rate': turnover_rate, 'total_market_value': total_mv, 'circulating_market_value': circulating_mv, 'update_time': now
                })
                count += 1
            session.commit()
            logging.info(f"[定时任务] ETF 实时行情(源: {source})采集完成，更新了 {count} 只ETF")
    except Exception as e:
        logging.error(f"[定时任务] ETF 实时行情采集异常: {e}")

def collect_etf_historical():
    try:
        today = datetime.now()
        today_str_dash = today.strftime('%Y-%m-%d')
        if _cn_session_closed_today():
            logging.info(f"[定时任务] A股(ETF) {today_str_dash} 为休市日，跳过 ETF 历史行情采集。")
            return
        logging.info(f"[定时任务] ETF 历史行情与列表同步采集开始，日期: {today_str_dash}")
        # 先同步一次列表
        etf_collector_instance.sync_etf_list()
        
        # 优先从实时行情表同步到历史表，避免爬虫限流
        if etf_collector_instance.collect_historical_quotes_from_realtime(today_str_dash):
             logging.info(f"[定时任务] {today_str_dash} ETF 历史数据已通过实时表同步完成")
        else:
             logging.info(f"[定时任务] 实时表无数据，尝试通过外部接口采集 {today_str_dash} ETF 历史行情")
             etf_collector_instance.collect_historical_data(start_date=today_str_dash, end_date=today_str_dash)
        
        logging.info("[定时任务] ETF 历史行情采集完成")
    except Exception as e:
        logging.error(f"[定时任务] ETF 历史行情采集异常: {e}")

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


def _resolve_optional_project_path(rel_or_abs: str) -> str:
    """相对路径相对于项目根目录（与 load_dotenv 同一根目录）解析。"""
    p = (rel_or_abs or "").strip()
    if not p:
        return ""
    pp = Path(p).expanduser()
    if pp.is_absolute():
        return str(pp)
    return str(_project_root / pp)


def _register_stock_shares_job():
    """
    注册股本同步任务，支持 weekly/monthly/quarterly 三种模式。

    .env 参数：
    - SCHED_STOCK_SHARES_ENABLED=true|false（默认 true；false 时不注册定时任务）
    - STOCK_SHARES_UPDATE_SOURCE=akshare|excel（默认 akshare；excel 时需 STOCK_SHARES_EXCEL_PATH）
    - STOCK_SHARES_EXCEL_PATH、STOCK_SHARES_EXCEL_SHEET（可选，sheet 为序号或工作表名）
    - SCHED_STOCK_SHARES_MODE=weekly|monthly|quarterly（默认 weekly）
    - SCHED_STOCK_SHARES_HOUR / SCHED_STOCK_SHARES_MINUTE（与其它 cron 一致，可为单个值或逗号区间，如 10 或 9,15）
    - weekly:    SCHED_STOCK_SHARES_DOW
    - monthly:   SCHED_STOCK_SHARES_DAY（每月几号，1-31）
    - quarterly: SCHED_STOCK_SHARES_DAY + SCHED_STOCK_SHARES_QUARTER_MONTHS
    """
    if not _env_bool("SCHED_STOCK_SHARES_ENABLED", True):
        logging.info("股本定时任务未注册（SCHED_STOCK_SHARES_ENABLED=false）")
        return
    mode = _env("SCHED_STOCK_SHARES_MODE", "weekly").lower()
    hour = _cron("SCHED_STOCK_SHARES_HOUR", "10")
    minute = _cron("SCHED_STOCK_SHARES_MINUTE", "0")
    job_kwargs = {
        "hour": hour,
        "minute": minute,
        "id": "stock_shares_update",
    }

    if mode == "monthly":
        # 每月第 N 天（默认 1 号）
        day = _cron_int("SCHED_STOCK_SHARES_DAY", 1)
        day = min(31, max(1, day))
        job_kwargs["day"] = day
        scheduler.add_job(update_stock_shares, "cron", **job_kwargs)
        logging.info(
            "已注册股本同步任务：mode=monthly, day=%s, hour=%s, minute=%s",
            day, hour, minute
        )
        return

    if mode == "quarterly":
        # 季度月份默认 1,4,7,10；支持自定义逗号表达式
        quarter_months = _cron("SCHED_STOCK_SHARES_QUARTER_MONTHS", "1,4,7,10")
        day = _cron_int("SCHED_STOCK_SHARES_DAY", 1)
        day = min(31, max(1, day))
        job_kwargs["month"] = quarter_months
        job_kwargs["day"] = day
        scheduler.add_job(update_stock_shares, "cron", **job_kwargs)
        logging.info(
            "已注册股本同步任务：mode=quarterly, months=%s, day=%s, hour=%s, minute=%s",
            quarter_months, day, hour, minute
        )
        return

    # 默认 weekly；非法值回退 weekly
    if mode not in ("weekly", "monthly", "quarterly"):
        logging.warning(
            "SCHED_STOCK_SHARES_MODE=%s 非法，已回退 weekly 模式",
            mode
        )
    dow = _cron("SCHED_STOCK_SHARES_DOW", "sat")
    job_kwargs["day_of_week"] = dow
    scheduler.add_job(update_stock_shares, "cron", **job_kwargs)
    logging.info(
        "已注册股本同步任务：mode=weekly, dow=%s, hour=%s, minute=%s",
        dow, hour, minute
    )


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
scheduler.add_job(run_job_triple_volume_scan, 'cron',
    day_of_week=_cron('SCHED_TRIPLE_VOLUME_SCAN_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_TRIPLE_VOLUME_SCAN_HOUR', 16),
    minute=_cron_int('SCHED_TRIPLE_VOLUME_SCAN_MINUTE', 25),
    id='triple_volume_observe_scan')
scheduler.add_job(run_job_triple_volume_eval, 'cron',
    day_of_week=_cron('SCHED_TRIPLE_VOLUME_EVAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_TRIPLE_VOLUME_EVAL_HOUR', 16),
    minute=_cron_int('SCHED_TRIPLE_VOLUME_EVAL_MINUTE', 40),
    id='triple_volume_observe_eval')
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
if _env_bool("SCHED_AKSHARE_TURNOVER_ENABLED", False):
    scheduler.add_job(collect_akshare_turnover_rate, 'cron',
        day_of_week=_cron('SCHED_AKSHARE_TURNOVER_DOW', 'mon-fri'),
        hour=_cron('SCHED_AKSHARE_TURNOVER_HOUR', '11'),
        minute=_cron_int('SCHED_AKSHARE_TURNOVER_MINUTE', 13),
        id='akshare_turnover_rate')
else:
    logging.info("AKShare 历史换手率定时采集未注册（默认关闭，需设置 SCHED_AKSHARE_TURNOVER_ENABLED=true 启用）")
_register_stock_shares_job()
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

scheduler.add_job(collect_etf_realtime, 'cron',
    day_of_week=_cron('SCHED_ETF_REALTIME_DOW', 'mon-fri'),
    hour=_cron('SCHED_ETF_REALTIME_HOUR', '15'),
    minute=_cron_int('SCHED_ETF_REALTIME_MINUTE', 33),
    id='etf_realtime')

scheduler.add_job(collect_etf_historical, 'cron',
    day_of_week=_cron('SCHED_ETF_HISTORICAL_DOW', 'mon-fri'),
    hour=_cron_int('SCHED_ETF_HISTORICAL_HOUR', 16),
    minute=_cron_int('SCHED_ETF_HISTORICAL_MINUTE', 5),
    id='etf_historical')

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