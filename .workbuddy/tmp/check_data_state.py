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
cur.execute("select date, count(*) from historical_quotes group by date order by date desc limit 12")
print("最近有数据的日期:")
for d,c in cur.fetchall(): print(" ", d, c)
cur.execute("""select id,user_id,report_type,enabled from user_push_configs where report_type='urt_daily' and enabled=true order by id""")
print("enabled urt_daily 配置:", cur.fetchall())
cur.execute("select count(*) from push_records")
print("push_records:", cur.fetchone()[0])
conn.close()
