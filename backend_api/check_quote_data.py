
from backend_api.database import SessionLocal
import pandas as pd

def check_db():
    db = SessionLocal()
    try:
        # Check total count of stocks in stock_realtime_quote for the latest date
        latest_date_result = pd.read_sql_query("""
            SELECT MAX(trade_date) as latest_date 
            FROM stock_realtime_quote 
        """, db.bind)
        
        if latest_date_result.empty or latest_date_result.iloc[0]['latest_date'] is None:
            print("No data in stock_realtime_quote")
            return

        latest_date = latest_date_result.iloc[0]['latest_date']
        print(f"Latest date: {latest_date}")

        count_result = pd.read_sql_query(f"""
            SELECT count(*) as count 
            FROM stock_realtime_quote 
            WHERE trade_date = '{latest_date}'
        """, db.bind)
        
        count = count_result.iloc[0]['count']
        print(f"Total stocks in stock_realtime_quote for {latest_date}: {count}")

        # Check if these match watchlist
        watchlist_result = pd.read_sql_query("""
            SELECT stock_code FROM watchlist
        """, db.bind)
        
        watchlist_codes = set(watchlist_result['stock_code'].tolist())
        print(f"Total stocks in watchlist: {len(watchlist_codes)}")
        
        # Check overlap
        quote_codes_result = pd.read_sql_query(f"""
            SELECT code FROM stock_realtime_quote 
            WHERE trade_date = '{latest_date}'
        """, db.bind)
        
        quote_codes = set(quote_codes_result['code'].tolist())
        
        overlap = quote_codes.intersection(watchlist_codes)
        print(f"Overlap between quote and watchlist: {len(overlap)}")
        
        if len(quote_codes) == len(overlap):
            print("WARNING: All stocks in stock_realtime_quote are in watchlist!")
        else:
            print(f"Stocks in quote but not in watchlist: {len(quote_codes - overlap)}")

    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    check_db()
