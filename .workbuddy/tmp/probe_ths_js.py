# -*- coding: utf-8 -*-
import re
import requests

url = "https://s.thsi.cn/website/datacenter/newJs/main_v2-4.js"
r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
text = r.text
out = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\.workbuddy\tmp\main_v2-4.js"
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
print("status", r.status_code, "len", len(text))
for key in ("page_info", "ggzjl", "ajax", "free/1", "hexin", "page_num"):
    print(key, text.count(key))

# print contexts around ggzjl
for m in re.finditer("ggzjl", text):
    i = m.start()
    print("---", text[max(0, i - 120) : i + 180].replace("\n", " ")[:300])
    break
