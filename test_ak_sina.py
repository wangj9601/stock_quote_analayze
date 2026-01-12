
import akshare as ak

def test_sina(symbol):
    print(f"Testing Sina {symbol}...")
    try:
        # Sina HK daily logic: symbol is just the code
        df = ak.stock_hk_daily(symbol=symbol)
        print(f"  Sina {symbol} Success: {len(df)} rows")
        if not df.empty:
            print(df.head())
    except Exception as e:
        print(f"  Sina {symbol} Error: {e}")

test_sina("00700")
