from sqlalchemy import text
from backend_core.database.db import SessionLocal

s = SessionLocal()
for q, p in [
    ("SELECT circulating_market_value, current_price, trade_date FROM stock_realtime_quote WHERE code='000001' ORDER BY trade_date DESC LIMIT 2", {}),
    ("SELECT free_float_shares, total_shares FROM stock_basic_info WHERE code='000001'", {}),
    ("SELECT date, close FROM historical_quotes WHERE code='000001' AND date>='2024-10-20' ORDER BY date DESC LIMIT 3", {}),
]:
    try:
        rows = s.execute(text(q), p).fetchall()
        print(q[:60], "->", rows)
    except Exception as e:
        print("ERR", e)
s.close()
