"""
港股历史接口成交量单位排查脚本

用法示例:
python test/test_hk_hist_volume_unit.py --symbol 00700 --start 20260301 --end 20260320
"""

import argparse
import math
import time
import akshare as ak
import pandas as pd


def to_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f):
            return None
        return f
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="港股历史接口成交量单位排查")
    parser.add_argument("--symbol", default="00700", help="港股代码，如 00700")
    parser.add_argument("--start", default="20260301", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default="20260320", help="结束日期 YYYYMMDD")
    args = parser.parse_args()

    print("=" * 72)
    print("AKShare 港股历史接口成交量单位排查")
    print(f"symbol={args.symbol}, start={args.start}, end={args.end}")
    print("=" * 72)

    def fetch_with_retry(fetch_name, fetch_func):
        data = None
        last_err = None
        for i in range(1, 4):
            try:
                data = fetch_func()
                print(f"{fetch_name} 第{i}次调用成功")
                return data, None
            except Exception as e:
                last_err = e
                print(f"{fetch_name} 第{i}次调用失败: {e}")
                if i < 3:
                    print("2秒后重试...")
                    time.sleep(2)
        return None, last_err

    # 1) 优先东方财富历史接口
    df, last_error = fetch_with_retry(
        "stock_hk_hist",
        lambda: ak.stock_hk_hist(
            symbol=args.symbol,
            period="daily",
            start_date=args.start,
            end_date=args.end,
            adjust="",
        ),
    )

    # 2) 失败则降级到新浪日线接口
    source_name = "stock_hk_hist"
    if df is None:
        print(f"stock_hk_hist 连续失败，降级尝试新浪 stock_hk_daily。最后错误: {last_error}")
        df, daily_error = fetch_with_retry(
            "stock_hk_daily",
            lambda: ak.stock_hk_daily(symbol=args.symbol, adjust=""),
        )
        source_name = "stock_hk_daily"
        if df is None:
            print(f"stock_hk_daily 也失败，无法完成排查。最后错误: {daily_error}")
            return

        # 对新浪日线做日期过滤
        if "日期" in df.columns:
            df = df.copy()
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            start_dt = pd.to_datetime(args.start, format="%Y%m%d", errors="coerce")
            end_dt = pd.to_datetime(args.end, format="%Y%m%d", errors="coerce")
            if pd.notna(start_dt) and pd.notna(end_dt):
                df = df[(df["日期"] >= start_dt) & (df["日期"] <= end_dt)]
                df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
                df = df.reset_index(drop=True)

    if df is None or df.empty:
        print("接口返回为空。")
        return

    print(f"数据来源: {source_name}")
    print(f"返回行数: {len(df)}")
    print(f"字段列表: {list(df.columns)}")

    # 兼容不同字段名
    date_col = "日期" if "日期" in df.columns else df.columns[0]
    close_col = "收盘" if "收盘" in df.columns else None
    volume_col = "成交量" if "成交量" in df.columns else None
    amount_col = "成交额" if "成交额" in df.columns else None

    print("\n前10行原始数据:")
    print(df.head(10).to_string(index=False))

    if not close_col or not volume_col or not amount_col:
        print("\n未找到 收盘/成交量/成交额 全部字段，无法做单位反推。")
        return

    calc_rows = []
    for _, row in df.iterrows():
        close = to_float(row.get(close_col))
        volume = to_float(row.get(volume_col))
        amount = to_float(row.get(amount_col))
        if close and volume and amount and close > 0 and volume > 0 and amount > 0:
            ratio = amount / (close * volume)
            calc_rows.append(
                {
                    "date": row.get(date_col),
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "ratio_amount_div_close_mul_volume": ratio,
                }
            )

    if not calc_rows:
        print("\n没有可用于计算 ratio 的有效数据行。")
        return

    calc_df = pd.DataFrame(calc_rows)
    print("\n可计算行(前15行):")
    print(calc_df.head(15).to_string(index=False))

    ratio_s = calc_df["ratio_amount_div_close_mul_volume"]
    print("\nratio=成交额/(收盘*成交量) 统计:")
    print(
        f"min={ratio_s.min():.6f}, p25={ratio_s.quantile(0.25):.6f}, "
        f"median={ratio_s.median():.6f}, p75={ratio_s.quantile(0.75):.6f}, max={ratio_s.max():.6f}"
    )

    print("\n判读建议:")
    print("- ratio 接近 1   => 成交量更像“股”")
    print("- ratio 接近 100 => 成交量更像“手”")


if __name__ == "__main__":
    main()

