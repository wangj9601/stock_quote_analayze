import psycopg2
from pathlib import Path
root = Path(r"E:/wangxw/股票分析软件/编码/stock_quote_analayze")
env = {}
for line in (root/".env").read_text(encoding="utf-8", errors="ignore").splitlines():
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
conn = psycopg2.connect(host=env.get("DB_HOST","localhost"), port=env.get("DB_PORT","5446"),
                        user=env.get("DB_USER","postgres"), password=env.get("DB_PASSWORD",""),
                        dbname=env.get("DB_NAME","stock_analysis"))
cur = conn.cursor()
for t in ("ma_indicators","mavol_indicators"):
    try:
        cur.execute(f"select date, count(*) from {t} where date >= '2026-11-05' group by date order by date desc")
        print(t, cur.fetchall())
    except Exception as e:
        conn.rollback(); print(t, "ERR", e)
try:
    cur.execute("select date, count(*) from urt_signal_trace where date >= '2026-11-05' group by date order by date desc")
    print("urt_signal_trace", cur.fetchall())
except Exception as e:
    conn.rollback(); print("trace ERR", e)
conn.close()
