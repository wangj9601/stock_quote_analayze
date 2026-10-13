# -*- coding: utf-8 -*-
"""读取今日推送生成的 URT 报告明细，供推送预览/汇总。"""
import json
import os
import pandas as pd

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"
os.chdir(ROOT)

res = json.load(open(os.path.join(".workbuddy", "tmp", "push_urt_daily_result.json"), encoding="utf-8"))

for t in res["targets"]:
    fp = t["report_file_path"].replace("\\", "/")
    print("=" * 90)
    print("USER", t["user_id"], t["username"], "| record", t["record_id"], "| file", fp)
    df = pd.read_excel(fp, sheet_name="URT策略信号列表")
    is_buy = df["是否买点"].astype(str).str.contains("是|买点|√|True", na=False)
    print("rows:", len(df), "| buy points:", int(is_buy.sum()))
    print("score range:", df["得分"].min(), "-", df["得分"].max())
    print("signal days:", list(df["信号日"].astype(str).unique()[:5]))
    cols = ["股票代码", "股票名称", "信号日", "收盘", "得分", "是否买点", "买点建议", "风险", "结构盈亏比", "换手%", "量比"]
    print(df[cols].to_string(index=False))
