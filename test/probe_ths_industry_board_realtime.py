#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测同花顺行业板实时接口可用性，并核对采集器是否优先走 THS。

用法（项目根目录）::

    python test/probe_ths_industry_board_realtime.py
"""

from __future__ import annotations

import inspect
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_priority_in_source() -> None:
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    src = inspect.getsource(RealtimeStockIndustryBoardCollector.fetch_data)
    print("=== 代码优先顺序（fetch_data）===")
    has_ths_first = "stock_board_industry_summary_ths" in src
    has_em_fallback = "stock_board_industry_name_em" in src
    ths_pos = src.find("stock_board_industry_summary_ths")
    em_pos = src.find("stock_board_industry_name_em")
    print(f"包含同花顺 summary_ths: {has_ths_first}")
    print(f"包含东财 name_em 回退: {has_em_fallback}")
    if has_ths_first and has_em_fallback:
        print(
            f"调用顺序: 同花顺优先={ths_pos < em_pos} "
            f"(ths_pos={ths_pos}, em_pos={em_pos})"
        )
    print()


def probe_akshare_ths() -> None:
    import akshare as ak

    print("=== 直接调用 ak.stock_board_industry_summary_ths() ===")
    try:
        df = ak.stock_board_industry_summary_ths()
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        traceback.print_exc()
        return
    if df is None:
        print("FAIL: 返回 None")
        return
    print(f"OK: rows={len(df)} cols={list(df.columns)}")
    if not df.empty:
        print("样例前 3 行:")
        print(df.head(3).to_string(index=False))
        # 关键字段
        for col in ("板块", "涨跌幅", "总成交额", "净流入", "均价", "最新价"):
            if col in df.columns:
                nn = int(df[col].notna().sum())
                print(f"  列[{col}] 非空={nn}/{len(df)}")
    print()


def probe_collector_fetch() -> None:
    from backend_core.data_collectors.akshare.industry_board_normalize import (
        industry_board_to_english_df,
    )
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    print("=== 采集器 RealtimeStockIndustryBoardCollector.fetch_data() ===")
    coll = RealtimeStockIndustryBoardCollector()
    try:
        df = coll.fetch_data()
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        traceback.print_exc()
        print(f"_last_fetch_source={coll._last_fetch_source}")
        return

    src = getattr(coll, "_last_fetch_source", None)
    print(f"_last_fetch_source={src}  (期望 ths)")
    print(f"返回 rows={0 if df is None else len(df)}")
    if df is None or df.empty:
        print("FAIL: 无数据")
        return

    # fetch_data 对 THS 已 normalize_ths_industry_df；EM 为原始东财列
    eng = industry_board_to_english_df(df)

    print(f"英文字段列: {list(eng.columns)}")
    if "latest_price" in eng.columns:
        nn = int(eng["latest_price"].notna().sum())
        print(f"latest_price 非空={nn}/{len(eng)}  (同花顺路径预期多为 0)")
    if "change_percent" in eng.columns:
        nn = int(eng["change_percent"].notna().sum())
        print(f"change_percent 非空={nn}/{len(eng)}")
    if "amount" in eng.columns:
        nn = int(eng["amount"].notna().sum())
        print(f"amount 非空={nn}/{len(eng)}")
    if "board_name" in eng.columns:
        print("样例板块名:", eng["board_name"].head(5).tolist())
    print()
    print("结论:")
    if src == "ths" and len(df) > 0:
        print("  - 同花顺实时接口可采到数据，且采集器优先走了 THS")
    elif src == "em" and len(df) > 0:
        print("  - 有数据，但来源是东财回退（同花顺失败或未优先）")
    else:
        print("  - 未采到有效数据")


def main() -> int:
    check_priority_in_source()
    probe_akshare_ths()
    probe_collector_fetch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
