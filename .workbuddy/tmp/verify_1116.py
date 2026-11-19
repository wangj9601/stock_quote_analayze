import psycopg2
from pathlib import Path
root = Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
env={}
for line in (root/".env").read_text(encoding="utf-8",errors="ignore").splitlines():
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
conn=psycopg2.connect(host=env.get("DB_HOST","localhost"),port=env.get("DB_PORT","5446"),
    user=env.get("DB_USER","postgres"),password=env.get("DB_PASSWORD",""),dbname=env.get("DB_NAME","stock_analysis"))
cur=conn.cursor()
cur.execute("""select count(*), sum(case when pre_close is null or pre_close<=0 then 1 else 0 end),
                 sum(case when volume is null or volume<=0 then 1 else 0 end),
                 sum(case when turnover_rate is null then 1 else 0 end)
              from historical_quotes where date='2026-11-16'""")
print("11-16 total/pre_close缺失/volume缺失/turnover缺失:", cur.fetchone())
cur.execute("""select count(*) from historical_quotes a join historical_quotes b
               on a.code=b.code where a.date='2026-11-16' and b.date='2026-11-13'
               and abs(a.pre_close-b.close) < 0.011""")
print("pre_close 与 11-13 收盘一致条数:", cur.fetchone()[0])
cur.execute("select count(*) from ma_indicators where date='2026-11-16'")
print("ma_indicators 11-16:", cur.fetchone()[0])
cur.execute("select count(*) from mavol_indicators where date='2026-11-16'")
print("mavol_indicators 11-16:", cur.fetchone()[0])
cur.execute("select count(*) from push_records")
print("push_records:", cur.fetchone()[0])
conn.close()
