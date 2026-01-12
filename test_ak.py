
import akshare as ak
import warnings
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 禁用 SSL 验证
requests.packages.urllib3.disable_warnings()
# 简单的 Monkeypatch
class UnverifiedContextAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['cert_reqs'] = 'CERT_NONE'
        return super(UnverifiedContextAdapter, self).init_poolmanager(*args, **kwargs)

s = requests.Session()
s.verify = False
requests.Session = lambda: s # 尝试强制全系统使用

def test(symbol):
    print(f"Testing {symbol}...")
    try:
        df = ak.stock_hk_hist(symbol=symbol, period='daily', start_date='20251101', end_date='20260112')
        print(f"  {symbol} Success: {len(df)} rows")
    except Exception as e:
        print(f"  {symbol} Error: {e}")

test("00700")
