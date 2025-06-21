import sys
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from backend_core.data_collectors.akshare.realtime import AkshareRealtimeQuoteCollector
from backend_core.data_collectors.tushare.historical import HistoricalQuoteCollector
from backend_core.data_collectors.tushare.realtime import RealtimeQuoteCollector
from backend_core.config.config import DATA_COLLECTORS
from backend_core.data_collectors.akshare.realtime_index_spot_ak import RealtimeIndexSpotAkCollector
from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import RealtimeStockIndustryBoardCollector


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# 初始化采集器
ak_collector = AkshareRealtimeQuoteCollector(DATA_COLLECTORS.get('akshare', {}))
tushare_hist_collector = HistoricalQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
tushare_realtime_collector = RealtimeQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
index_collector = RealtimeIndexSpotAkCollector()
industry_board_collector = RealtimeStockIndustryBoardCollector()

scheduler = BlockingScheduler()

def collect_akshare_realtime():
    try:
        logging.info("[定时任务] AKShare 实时行情采集开始...")
        df = ak_collector.collect_quotes()
        # 可在此处保存数据到数据库或文件
        #logging.info(f"[定时任务] AKShare 实时行情采集完成，采集到 {len(df)} 条数据")
    except Exception as e:
        logging.error(f"[定时任务] AKShare 实时行情采集异常: {e}")

def collect_akshare_index_realtime(): 
    try:
        logging.info("[定时任务] AKShare 指数实时行情采集开始...")
        df = index_collector.collect_quotes()
        # 可在此处保存数据到数据库或文件
        #logging.info(f"[定时任务] AKShare 实时行情采集完成，采集到 {len(df)} 条数据")
    except Exception as e:
        logging.error(f"[定时任务] AKShare 实时行情采集异常: {e}")

def collect_tushare_historical():
    try:
        today = datetime.now()
        while today.weekday() >= 5:  # 5是周六,6是周日
            today = today - timedelta(days=1)
        today = today - timedelta(days=1)  # 取前一天
        today = today.strftime('%Y%m%d')
        logging.info(f"[定时任务] Tushare 历史行情采集开始，日期: {today}")
        tushare_hist_collector.collect_historical_quotes(today)
        logging.info("[定时任务] Tushare 历史行情采集完成")
    except Exception as e:
        logging.error(f"[定时任务] Tushare 历史行情采集异常: {e}")

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

# 定时任务配置
# 每个交易日上午9:00-11:30、下午13:30-15:30每15分钟采集一次A股实时行情
scheduler.add_job(
    collect_akshare_realtime,
    'cron',
    day_of_week='mon-fri',
    hour='9-11,13-23',
    minute='0,15,30,45',
    id='akshare_realtime',
)
# 每天15:45采集当天历史行情（收盘后）
scheduler.add_job(collect_tushare_historical, 'cron', hour=22, minute=53, id='tushare_historical')

# 每隔5分钟采集一次Tushare实时行情----由于tushare对普通会员，一小时只能调用1次，所以暂时不启用
#scheduler.add_job(collect_tushare_realtime, 'interval', minutes=5, id='tushare_realtime')

# 指数实时行情采集任务，每20分钟采集一次
scheduler.add_job(
    collect_akshare_index_realtime,
    'cron',
    day_of_week='mon-fri',
    hour='9-10,11,13-21',
    minute='1,21,41',
    id='akshare_index_realtime',
)

# 行业板块实时行情采集任务，每30分钟采集一次
scheduler.add_job(
    collect_akshare_industry_board_realtime,
    'cron',
    day_of_week='mon-fri',
    hour='9-10,11,13-21',
    minute='2,32',
    id='akshare_industry_board_realtime',
)

if __name__ == "__main__":
    logging.info("启动定时采集任务...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("定时任务已停止。") 