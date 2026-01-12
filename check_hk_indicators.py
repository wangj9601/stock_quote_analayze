
from sqlalchemy import create_engine, text
import pandas as pd
import sys
import os

# 确保能找到 backend_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from backend_api.config import DATABASE_CONFIG
    engine = create_engine(DATABASE_CONFIG["url"])
except Exception as e:
    print(f"Failed to load config: {e}")
    engine = create_engine("postgresql://postgres:postgres@localhost:5432/stock_analysis")

def check_stock(code):
    print(f"\n--- Checking Stock: {code} ---")
    try:
        with engine.connect() as conn:
            # 检查历史行情
            quotes_count = conn.execute(text("SELECT COUNT(*) FROM historical_quotes_hk WHERE code = :code"), {"code": code}).scalar()
            print(f"Historical Quotes (HK): {quotes_count}")
            
            # 检查主要指标表
            indicators = ["ma_indicators", "macd_indicators", "rsi_indicators", "kdj_indicators", "boll_indicators", "mavol_indicators"]
            for table in indicators:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE code = :code AND market_type = 'HK'"), {"code": code}).scalar()
                print(f"{table}: {count}")
            
            # 如果有行情但没指标，查看一下行情数据的日期
            if quotes_count > 0:
                last_quote = conn.execute(text("SELECT date FROM historical_quotes_hk WHERE code = :code ORDER BY date DESC LIMIT 1"), {"code": code}).fetchone()
                print(f"Last Quote Date: {last_quote[0] if last_quote else 'N/A'}")
                
                # 检查最近10天的行情数据
                quotes = conn.execute(text("SELECT date, close, volume FROM historical_quotes_hk WHERE code = :code ORDER BY date DESC LIMIT 10"), {"code": code}).fetchall()
                print("Recent Quotes:")
                for q in quotes:
                    print(f"  {q[0]}: close={q[1]}, volume={q[2]}")
    except Exception as e:
        print(f"Error checking stock {code}: {e}")

if __name__ == "__main__":
    check_stock("02565")
    check_stock("00700")
