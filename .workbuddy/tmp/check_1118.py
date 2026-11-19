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
cur.execute("select date, count(*) from historical_quotes group by date order by date desc limit 6")
print("最近数据日:", cur.fetchall())
for t in ("ma_indicators","mavol_indicators"):
    cur.execute(f"select count(*) from {t} where date='2026-11-18'")
    print(t, "11-18:", cur.fetchone()[0])
cur.execute("""select count(*) from historical_quotes a join historical_quotes b
  on a.stock_code=b.stock_code and b.date='2026-11-17'
  where a.date='2026-11-18' and abs(a.pre_close-b.close)>0.011""")
print("pre_close 与前日收盘不一致数:", cur.fetchone()[0])
conn.close()
