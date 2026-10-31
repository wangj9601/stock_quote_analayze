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
from backend_core.analysis.sepa.screener import evaluate_stock, screen_universe, to_table_rows
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
    "to_table_rows",
]
