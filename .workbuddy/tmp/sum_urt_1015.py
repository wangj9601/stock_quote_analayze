# -*- coding: utf-8 -*-
import pandas as pd

files = {
    "user7(wangxw1)": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261014_130029.xlsx",
    "user6(wangxw)": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261014_130141.xlsx",
}

for tag, f in files.items():
    df = pd.read_excel(f, sheet_name="URT策略信号列表")
    df["股票代码"] = df["股票代码"].astype(str).str.strip().str.replace("\u200b", "", regex=False)
    df["是否买点"] = df["是否买点"].astype(str).str.strip()
    buys = df[df["是否买点"] == "是"]
    print("=" * 100)
    print(f"### {tag} | 总行数={len(df)} | 正式买点={len(buys)} | 得分区间 {df['得分'].min():.1f}–{df['得分'].max():.1f} | 信号日 {df['信号日'].astype(str).unique().tolist()}")
    print("--- 正式买点明细 ---")
    if len(buys):
        cols = ["股票代码", "股票名称", "收盘", "得分", "结构盈亏比", "风险", "买点建议"]
        for _, r in buys.iterrows():
            print(f"  {r['股票代码']} {r['股票名称']} 收盘{r['收盘']} 得分{r['得分']:.1f} RR{r['结构盈亏比']} 风险[{r['风险']}]")
    else:
        print("  （无）")
    print("--- 得分 Top15（含观察） ---")
    cols = ["股票代码", "股票名称", "收盘", "得分", "是否买点", "结构盈亏比", "风险"]
    top = df.sort_values("得分", ascending=False).head(15)
    print(top[cols].to_string(index=False))
    print("--- 风险标签频次 ---")
    risk_cnt = {}
    for s in df["风险"].dropna().astype(str):
        for x in str(s).replace("；", ";").split(";"):
            x = x.strip()
            if x:
                risk_cnt[x] = risk_cnt.get(x, 0) + 1
    for k, v in sorted(risk_cnt.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
