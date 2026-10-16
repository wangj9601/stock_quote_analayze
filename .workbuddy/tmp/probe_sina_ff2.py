# -*- coding: utf-8 -*-
import json
import requests

ua = {"User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/"}
base = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_ssggzj"

def get(page, num):
    r = requests.get(base, params={"page": page, "num": num, "sort": "netamount", "asc": 0, "bankuai": "", "shichang": ""}, headers=ua, timeout=30)
    text = r.content.decode("utf-8", errors="replace")
    if not text or text.strip() in ("null", "[]"):
        return []
    return json.loads(text)

# find page size limit and a stock sample
for num in (20, 80, 100):
    rows = get(1, num)
    print("num", num, "got", len(rows))

rows = get(1, 80)
stocks = [x for x in rows if str(x.get("symbol","")).startswith(("sh6","sz0","sz3","bj"))]
print("page1 stock-like", len(stocks), "first stock", stocks[0] if stocks else None)
# binary search last page roughly
lo, hi = 1, 200
last = 1
while lo <= hi:
    mid = (lo + hi) // 2
    rs = get(mid, 80)
    print("probe page", mid, "n", len(rs))
    if rs:
        last = mid
        lo = mid + 1
    else:
        hi = mid - 1
print("last non-empty page", last)
