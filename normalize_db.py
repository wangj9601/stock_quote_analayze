from backend_core.database.db import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_database():
    session = SessionLocal()
    tables = [
        "ma_indicators",
        "macd_indicators",
        "kdj_indicators",
        "rsi_indicators",
        "boll_indicators",
        "mavol_indicators",
        "mean_frequency_resonance_indicators"
    ]
    
    try:
        for table in tables:
            logger.info(f"Normalizing table: {table}")
            
            # 1. 删除那些同时存在 'CN' 和 'A股' 的记录中的 'A股' 版本
            # 假设 'CN' 版本是更新或更准确的（通常是由 Akshare 或新逻辑产生的）
            delete_sql = f"""
            DELETE FROM {table}
            WHERE market_type = 'A股'
            AND EXISTS (
                SELECT 1 FROM {table} t2
                WHERE t2.code = {table}.code
                AND t2.date = {table}.date
                AND t2.market_type = 'CN'
            )
            """
            res_del = session.execute(text(delete_sql))
            logger.info(f"Deleted {res_del.rowcount} duplicate 'A股' records from {table}")
            
            # 2. 将剩余的 'A股' 记录更新为 'CN'
            update_sql = f"""
            UPDATE {table}
            SET market_type = 'CN'
            WHERE market_type = 'A股'
            """
            res_upd = session.execute(text(update_sql))
            logger.info(f"Updated {res_upd.rowcount} 'A股' records to 'CN' in {table}")
            
        session.commit()
        logger.info("Normalization completed successfully.")
    except Exception as e:
        logger.error(f"Error during normalization: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    normalize_database()
