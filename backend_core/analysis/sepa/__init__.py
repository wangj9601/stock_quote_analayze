# -*- coding: utf-8 -*-
"""SEPA 选股（Specific Entry Point Analysis）：趋势模板 + VCP 收缩 + 枢轴点突破 + 两融旁证。

三层过滤，全部纯函数、只吃行数据，不碰数据库：
    trend.compute_trend_template(bars, rs_rank=...)   -> 八条趋势硬门槛
    vcp.detect_vcp(bars)                              -> 收缩序列 / 枢轴点 / 突破
    margin.assess_margin(margin_rows, circ_mv=...)     -> 杠杆资金出清与回流

用法
----
单票::

    from backend_core.analysis.sepa import evaluate_stock

    res = evaluate_stock(bars, code="600000.SH", rs_rank=88.0,
                         margin_rows=margin_rows, circ_mv=2.1e10)
    res["tier"], res["vcp"]["status_label"], res["margin"]["status_label"]

批量::

    from backend_core.analysis.sepa import screen_universe, to_table_rows
    from backend_core.analysis.sepa.loaders import fetch_inputs

    inputs = fetch_inputs(db, limit_codes=800)          # 只读取数，已适配库内三处口径
    picks = screen_universe(inputs["bars"], margin_by_code=inputs["margin"],
                            circ_mv_by_code=inputs["float_mv"], top=30)
    rows = to_table_rows(picks)   # 直接给前端

bars 行：trade_date/date、open/high/low/close、volume/vol（前复权）
margin 行：trade_date、rzye、rzmre、rzche、float_mv（stock_margin_daily）

实证校准（2024-10 ~ 2026-09，800 只 x 97 个评估日，脚本 scripts/calibrate_sepa.py）
------------------------------------------------------------------------------------
1. "就位待突破"（距枢轴 3% 内 + 最近 10 日振幅 <=8%）三期一致优于"放量突破"：
   10 日胜率 60~63% vs 40~49%，中位 +1.7~2.4% vs -2.2~-0.3%。故默认 prefer_ready=True。
2. 突破加了距离上限 max_breakout_distance=10%：原先只要求 dist>=0.2%，
   距枢轴 50% 的票也会被标成"突破"，实际是追高（样例日 5 个突破全部属此类）。
3. 末次收缩深度 0.10 最优、0.15 以上转负，且从"只打标签"改为真正拦截。
4. 量能倍数 1.0/1.2/1.5 无显著差异；3.0 倍量在牛市段 10 日均值 -3.64%。
5. 两融层样本不足（明细只有 2026-07 起），目前仅"拥挤度 >5%"有强负向证据，
   因此两融只作旁证：拥挤降为观察，没有两融数据不降级。
6. 放量突破与未放量越过都要求至少两段收缩，且突破前 10 日振幅 ≤ 8%。
   突破日会撑开窗口，紧凑度不把当日算进去。距枢轴超过 6% 标为远离枢轴，默认不进名单。
   价格已在枢轴上方但量比不足时单独标为未放量越过，不并入收缩中。
7. 股票池按全市场流动性取：6 位代码、排除 ST/退市、近 20 日均成交额 ≥ 5000 万，
   按成交额从高到低，上限 4000。相对强度在这只池子里计算，不再按代码序截前 800。

库内口径注意（已在本地库实测）
------------------------------
1. historical_quotes.date 是 TEXT，比较用字符串，别写 DATE '2026-10-30'。
2. 代码为裸 6 位（'600000'），不带 .SH/.SZ。
3. stock_realtime_quote.circulating_market_value 当前全为 NULL，
   流通市值需走 stock_basic_info.free_float_shares × 最新收盘（<1e6 视为万股）。
   取不到时 crowd 为空，两融"拥挤"一档不会触发，其余判断照常。
"""

from backend_core.analysis.sepa.config import (
    DISCLAIMER,
    MARGIN_STATUS_LABELS,
    TIER_LABELS,
    VCP_STATUS_LABELS,
    MarginConfig,
    SEPAConfig,
    TrendConfig,
    VCPConfig,
)
from backend_core.analysis.sepa.margin import assess_margin
from backend_core.analysis.sepa.screener import (
    evaluate_stock,
    screen_report,
    screen_universe,
    to_table_rows,
)
from backend_core.analysis.sepa.trend import compute_trend_template
from backend_core.analysis.sepa.vcp import detect_vcp

__all__ = [
    "SEPAConfig",
    "TrendConfig",
    "VCPConfig",
    "MarginConfig",
    "TIER_LABELS",
    "VCP_STATUS_LABELS",
    "MARGIN_STATUS_LABELS",
    "DISCLAIMER",
    "compute_trend_template",
    "detect_vcp",
    "assess_margin",
    "evaluate_stock",
    "screen_universe",
    "screen_report",
    "to_table_rows",
]
