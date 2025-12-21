
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import SessionLocal
from sqlalchemy import text

def check_data():
    session = SessionLocal()
    try:
        # Check Historical Quotes date format
        print("Checking HistoricalQuotes for 300446:")
        hist_sample = session.execute(text("SELECT date FROM historical_quotes WHERE code = '300446' ORDER BY date DESC LIMIT 3")).fetchall()
        for row in hist_sample:
            print(f"Historical Date: '{row[0]}', Type: {type(row[0])}")
        
        # Check MACD Indicators date format
        print("\nChecking MACDIndicators for 300446:")
        macd_sample = session.execute(text("SELECT date FROM macd_indicators WHERE code = '300446' ORDER BY date DESC LIMIT 3")).fetchall()
        for row in macd_sample:
            print(f"MACD Date: '{row[0]}', Type: {type(row[0])}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_data()
