# -*- coding: utf-8 -*-
import re
import requests
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
headers = {
    "User-Agent": ua,
    "hexin-v": v,
    "Cookie": f"v={v}",
    "Referer": "https://data.10jqka.com.cn/funds/ggzjl/",
}
r = requests.get("https://data.10jqka.com.cn/funds/ggzjl/", headers=headers, timeout=20)
text = r.content.decode("gbk", errors="replace")
out = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\.workbuddy\tmp\ggzjl_main.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
print("status", r.status_code, "len", len(text), "saved", out)
print("page_info", text.count("page_info"), "m-table", text.count("m-table"))
for m in re.finditer(r'<script[^>]+src="([^"]+)"', text):
    print("script", m.group(1)[:220])
idx = text.find("ajax")
print("--- ajax window ---")
print(text[max(0, idx - 300) : idx + 500] if idx >= 0 else "no ajax")
