#!/usr/bin/env python3
import pandas as pd

files = [
    ("基线 10%/10%/1R", r"reports/P0对比-基线_止损10跟踪10保本1R_.xlsx"),
    ("持趋势 8%/14%/1.5R35%", r"reports/P0对比-持趋势_止损8跟踪14保本1_5R分批35__.xlsx"),
    ("稳健 5%/8%/10天", r"reports/P0对比-稳健预设_止损5跟踪8时间10_.xlsx"),
]


def metric(path, key):
    s = pd.read_excel(path, sheet_name="统计摘要", header=None)
    for _, row in s.iterrows():
        if str(row[0]).strip() == key:
            return row[1]
    return None


for name, path in files:
    df = pd.read_excel(path, sheet_name="A股")
    r = df.iloc[0]
    print(name)
    print(f"  胜率={metric(path,'胜率')} 组合年化={metric(path,'组合年化收益')} 最大回撤={metric(path,'最大回撤')}")
    print(
        f"  688006: 观察期涨{r['观察期内最大涨幅']:.1%} 命中目标={r['是否命中目标']} "
        f"持仓{r['持有K线数']}根K 收益{r['单笔收益率']:.2%} R={r['R倍数']:.2f} "
        f"分批={r['是否触发分批止盈']} 出场={r['出场原因']} 最大有利={r['最大有利波动']:.1%}"
    )
    print()
