
import sys
import os
import logging
import time
from datetime import datetime, timedelta

# 确保能找到 backend_core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend_core.database.db import get_db, SessionLocal
from backend_core.data_collectors.akshare.watchlist_history_collector import (
    normalize_stock_code, is_hk_stock, insert_historical_quotes_hk, log_collection
)
import akshare as ak
from sqlalchemy import text

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def force_collect_hk(stock_code):
    db = SessionLocal()
    try:
        stock_code = normalize_stock_code(stock_code)
        logger.info(f"强制采集港股 {stock_code} 的完整历史数据...")
        
        end_date = datetime.now().strftime('%Y%m%d')
        
        df = None
        for retry in range(3):
            try:
                logger.info(f"尝试采集 {stock_code} (第 {retry+1} 次)...")
                df = ak.stock_hk_hist(symbol=stock_code, period='daily', start_date='20200101', end_date=end_date, adjust='')
                if not df.empty:
                    break
            except Exception as e:
                logger.warning(f"采集 {stock_code} 失败: {e}")
                time.sleep(2)
        
        if df is None or df.empty:
            logger.error(f"未能获取到 {stock_code} 的历史数据")
            return
        
        logger.info(f"获取到 {len(df)} 条历史数据，正在存入数据库...")
        
        # 删除旧数据
        db.execute(text("DELETE FROM historical_quotes_hk WHERE code = :code"), {"code": stock_code})
        db.commit()
        
        affected_rows = insert_historical_quotes_hk(db, stock_code, df)
        log_collection(db, stock_code, affected_rows, 'success')
        
        logger.info(f"成功存入 {affected_rows} 条数据。")
        
        # 触发指标计算
        from backend_core.data_collectors.akshare.hk_historical import HKHistoricalQuoteCollector
        collector = HKHistoricalQuoteCollector()
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"正在计算 {target_date} 的各项指标...")
        # 注意：需要自选股里有这个股，为了确保能跑通，我们手动传入代码
        collector._calculate_and_save_ma_hk([stock_code], target_date, db)
        collector._calculate_and_save_macd_hk([stock_code], target_date, db)
        collector._calculate_and_save_kdj_hk([stock_code], target_date, db)
        collector._calculate_and_save_rsi_hk([stock_code], target_date, db)
        collector._calculate_and_save_boll_hk([stock_code], target_date, db)
        collector._calculate_and_save_mavol_hk([stock_code], target_date, db)
        
        db.commit()
        logger.info(f"{stock_code} 指标计算完成。")
        
    except Exception as e:
        logger.error(f"采集失败: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    force_collect_hk("00700")
