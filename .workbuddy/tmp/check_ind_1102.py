import os
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
for t in ("ma_indicators","mavol_indicators"):
    cur.execute(f"select date,count(*) from {t} group by date order by date desc limit 4")
    print(t, cur.fetchall())
cur.execute("select count(*) from urt_signal_trace where date='2026-11-02'")
print("trace 11-02:", cur.fetchone()[0])
conn.close()
