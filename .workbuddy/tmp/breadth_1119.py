import os, re
from pathlib import Path
root = Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
env = {}
for line in (root/".env").read_text(encoding="utf-8", errors="ignore").splitlines():
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
import psycopg2
conn = psycopg2.connect(host=env.get("DB_HOST","localhost"), port=env.get("DB_PORT","5446"),
                        user=env.get("DB_USER","postgres"), password=env.get("DB_PASSWORD",""),
                        dbname=env.get("DB_NAME","stock_analysis"))
cur = conn.cursor()
for d in ("2026-11-18","2026-11-19"):
    cur.execute("""select sum(case when close>pre_close then 1 else 0 end),
                          sum(case when close<pre_close then 1 else 0 end),
                          avg((close-pre_close)/pre_close)*100
                   from historical_quotes where date=%s and pre_close>0""", (d,))
    up, down, avg = cur.fetchone()
    print(d, "涨", up, "跌", down, "均%.2f%%" % (avg or 0))
conn.close()
