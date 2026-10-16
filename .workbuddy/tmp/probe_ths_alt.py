# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import py_mini_racer
from akshare.datasets import get_ths_js

with open(get_ths_js("ths.js"), encoding="utf-8") as f:
    js = f.read()
ctx = py_mini_racer.MiniRacer()
ctx.eval(js)
v = ctx.call("v")
ua = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
s = requests.Session()
s.headers.update({
    "User-Agent": ua,
    "hexin-v": v,
    "Cookie": f"v={v}",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://data.10jqka.com.cn/funds/ggzjl/",
})
urls = [
    "https://data.10jqka.com.cn/funds/ggzjl/order/desc/ajax/1/",
    "https://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/page/1/ajax/1/",
    "https://data.10jqka.com.cn/funds/ggzjl/field/code/order/desc/page/1/ajax/1/",
]
for url in urls:
    r = s.get(url, timeout=20)
    text = r.content.decode("gbk", errors="replace")
    soup = BeautifulSoup(text, "lxml")
    tbody = soup.find("tbody")
    rows = len(tbody.find_all("tr")) if tbody else -1
    pi = soup.find("span", class_="page_info")
    print(url.split("ggzjl/")[-1], "status", r.status_code, "len", len(text), "rows", rows, "page", None if pi is None else pi.get_text(strip=True))
    print(" head", text[:180].replace("\n", " "))

# eastmoney sample
em = "https://push2.eastmoney.com/api/qt/clist/get"
params = {
    "pn": 1,
    "pz": 2,
    "po": 1,
    "np": 1,
    "fltt": 2,
    "invt": 2,
    "fid": "f62",
    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    "fields": "f12,f14,f2,f3,f6,f8,f62,f184,f66,f72,f78,f84,f135,f136,f137,f138,f139,f140,f141,f142",
}
r = requests.get(em, params=params, timeout=20, headers={"User-Agent": ua})
print("em", r.status_code, r.text[:800])
