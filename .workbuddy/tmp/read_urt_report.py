# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from sqlalchemy import create_engine, text

for f, tag in [(r"reports/csv/urt_7_20261022_125901.xlsx","user7"),
               (r"reports/csv/urt_6_20261022_125950.xlsx","user6")]:
    df = pd.read_excel(f)
    score_col = [c for c in df.columns if 'score' in str(c).lower() or '得分' in str(c)]
    col = score_col[0] if score_col else df.columns[-1]
    df[col] = pd.to_numeric(df[col], errors='coerce')
    top = df.nlargest(3, col)
    print(f"== {tag}: rows={len(df)} max={df[col].max():.1f} mean={df[col].mean():.1f}")
    for _, r in top.iterrows():
        code = r.get('stock_code', r.get('code','?')); name = r.get('stock_name', r.get('name','?'))
        print(f"  top {code} {name} {r[col]:.1f}")

eng = create_engine("postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis")
with eng.connect() as c:
    rows = c.execute(text("SELECT date, count(*) FROM historical_quotes WHERE date >= '2026-10-20' GROUP BY date ORDER BY date")).fetchall()
    print("recent hist dates:", [(str(r[0]), r[1]) for r in rows])
    rows = c.execute(text("SELECT signal_date, count(*) FROM urt_signal_trace WHERE signal_date >= '2026-10-20' GROUP BY signal_date ORDER BY signal_date")).fetchall()
    print("trace:", [(str(r[0]), r[1]) for r in rows])
