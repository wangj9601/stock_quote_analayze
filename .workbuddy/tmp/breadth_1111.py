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
cur.execute("select column_name from information_schema.columns where table_name='historical_quotes' order by ordinal_position")
print([r[0] for r in cur.fetchall()])
for d in ("2026-11-06","2026-11-09","2026-11-10"):
    cur.execute("""select sum(case when close>pre_close then 1 else 0 end),
                          sum(case when close<pre_close then 1 else 0 end),
                          count(*),
                          round(avg((close/pre_close-1)*100)::numeric,2)
                   from historical_quotes where date=%s and close is not null and pre_close>0""",(d,))
    print(d, "涨/跌/总/均涨幅%:", cur.fetchone())
conn.close()
