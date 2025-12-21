
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from sqlalchemy import text

def check_data():
    session = SessionLocal()
    try:
        # Check if MACD data exists for 300446
        macd_count = session.execute(text("SELECT COUNT(*) FROM macd_indicators WHERE code = '300446'")).scalar()
        print(f"MACD count for 300446: {macd_count}")
        
        if macd_count > 0:
            # Check a sample
            sample = session.execute(text("SELECT date, dif, dea, macd FROM macd_indicators WHERE code = '300446' ORDER BY date DESC LIMIT 3")).fetchall()
            print("Latest 3 MACD records:")
            for row in sample:
                print(row)
        
        # Check if basic historical data exists
        hist_count = session.execute(text("SELECT COUNT(*) FROM historical_quotes WHERE code = '300446'")).scalar()
        print(f"Historical quotes count for 300446: {hist_count}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_data()
