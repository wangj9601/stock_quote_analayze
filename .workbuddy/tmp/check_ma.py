from pathlib import Path
import psycopg2
root = Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
env={}
for line in (root/".env").read_text(encoding="utf-8",errors="ignore").splitlines():
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
conn=psycopg2.connect(host=env["DB_HOST"],port=env["DB_PORT"],user=env["DB_USER"],password=env["DB_PASSWORD"],dbname=env["DB_NAME"])
cur=conn.cursor()
for t in ("ma_indicators","mavol_indicators"):
    cur.execute(f"select date,count(*) from {t} group by date order by date desc limit 5")
    print(t, cur.fetchall())
conn.close()
