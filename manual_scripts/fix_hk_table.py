from backend_api.database import SessionLocal
from backend_api.models import StockBasicInfoHK
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_hk_table():
    db = SessionLocal()
    try:
        # 1. Delete specific wrong code 002415
        count1 = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == '002415').delete()
        logger.info(f"Deleted {count1} records of 002415")
        
        # 2. Delete any other 6-digit codes (typical for A-shares)
        # In SQL: DELETE FROM stock_basic_info_hk WHERE code ~ '^[0-9]{6}$'
        # In SQLAlchemy with postgres, we can use op('~') or filter by length
        # Simplest way is to filter by string length if code is a string
        # sqlalchemy.func.length(StockBasicInfoHK.code) == 6
        from sqlalchemy import func
        count2 = db.query(StockBasicInfoHK).filter(func.length(StockBasicInfoHK.code) == 6).delete(synchronize_session=False)
        logger.info(f"Deleted {count2} other 6-digit codes")
        
        db.commit()
    except Exception as e:
        logger.error(f"Error fixing table: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_hk_table()
