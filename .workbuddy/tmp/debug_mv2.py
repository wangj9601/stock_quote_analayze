from backend_api.stock.margin import _resolve_float_mv
from backend_core.database.db import SessionLocal
from sqlalchemy import text

s = SessionLocal()
print("basic", s.execute(text("SELECT free_float_shares FROM stock_basic_info WHERE code='000001'")).fetchone())
print("hq", s.execute(text("SELECT close FROM historical_quotes WHERE code='000001' ORDER BY date DESC LIMIT 1")).fetchone())
print("rt", s.execute(text("SELECT current_price FROM stock_realtime_quote WHERE code='000001' ORDER BY trade_date DESC LIMIT 1")).fetchone())
try:
    print(_resolve_float_mv(s, "000001", "2024-10-25"))
except Exception as e:
    import traceback
    traceback.print_exc()
s.close()
