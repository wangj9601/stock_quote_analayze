# -*- coding: utf-8 -*-
import pandas as pd

files = {
    "user7": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_7_20261015_125925.xlsx",
    "user6": r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\reports\csv\urt_6_20261015_130015.xlsx",
}

for tag, f in files.items():
    print("=" * 110)
    print(f"### {tag} :: {f}")
    xl = pd.ExcelFile(f)
    print("sheets:", xl.sheet_names)
    for sh in xl.sheet_names:
        df = xl.parse(sh)
        print("-" * 110)
        print(f"[{tag}] sheet={sh} shape={df.shape}")
        print("columns:", list(df.columns))
        with pd.option_context("display.max_columns", None, "display.width", 300,
                               "display.max_rows", 500, "display.unicode.east_asian_width", True):
            print(df.to_string(index=False))
