# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from sqlalchemy import create_engine, text

for f, tag in [(r"reports/csv/urt_7_20261022_125901.xlsx","user7"),
               (r"reports/csv/urt_6_20261022_125950.xlsx","user6")]:
    df = pd.read_excel(f)
    print(f"== {tag} columns: {list(df.columns)}")
    col = [c for c in df.columns if 'score' in str(c).lower() or '得分' in str(c)][0]
    df[col] = pd.to_numeric(df[col], errors='coerce')
    for _, r in df.nlargest(3, col).iterrows():
        print("  top:", " | ".join(f"{c}={r[c]}" for c in df.columns[:5]), f"score={r[col]:.1f}")

eng = create_engine("postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis")
with eng.connect() as c:
    cols = c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='urt_signal_trace'")).fetchall()
    print("trace cols:", [r[0] for r in cols])
