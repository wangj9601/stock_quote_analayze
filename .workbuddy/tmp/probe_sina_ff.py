# -*- coding: utf-8 -*-
import requests

ua = "Mozilla/5.0"
urls = [
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_ssggzj?page=1&num=5&sort=netamount&asc=0&bankuai=&shichang=",
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_ssggzj?page=1&num=5&sort=netamount&asc=0",
]
for u in urls:
    try:
        r = requests.get(u, timeout=20, headers={"User-Agent": ua, "Referer": "https://vip.stock.finance.sina.com.cn/"})
        print("status", r.status_code, "len", len(r.content), "ctype", r.headers.get("content-type"))
        print(r.content[:500])
    except Exception as e:
        print("ERR", type(e).__name__, e)
    print("---")
