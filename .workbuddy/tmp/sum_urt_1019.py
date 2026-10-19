# -*- coding: utf-8 -*-
import pandas as pd

files = {
    "user7 (wangxw1)": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261016_084206.xlsx",
    "user6 (wangxw)": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261016_084330.xlsx",
}

for tag, f in files.items():
    df = pd.read_excel(f, sheet_name="URT策略信号列表")
    n = len(df)
    buy = df[df["是否买点"] == "是"]
    print("=" * 90)
    print(f"### {tag}  行数={n}  买点数={len(buy)}")
    print(f"信号日: {sorted(df['信号日'].astype(str).unique())}")
    print(f"得分范围: {df['得分'].min()} ~ {df['得分'].max()}")
    if len(buy):
        for _, r in buy.iterrows():
            print(f"  [买点] {r['股票代码']} {r['股票名称']} 收盘{r['收盘']} 得分{r['得分']} RR{r['结构盈亏比']} 风险={r['风险']}")
    print("-- Top10 by 得分 --")
    top = df.sort_values("得分", ascending=False).head(10)
    for _, r in top.iterrows():
        print(f"  {r['股票代码']} {r['股票名称']:8s} 得分{r['得分']:>5} 收盘{r['收盘']:>8} MA20={r['MA20']} 量能{r['量能倍数']} 买点={r['是否买点']} 风险={r['风险']}")
    lab = {}
    for s in df["风险"].fillna(""):
        for k in str(s).split("；"):
            k = k.strip()
            if k:
                lab[k] = lab.get(k, 0) + 1
    print("-- 风险标签分布 --")
    for k, v in sorted(lab.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("-- 列名 --")
    print(list(df.columns))
