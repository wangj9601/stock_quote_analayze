"""
AKShare：东方财富个股资料 stock_individual_info_em，打印 DataFrame。
运行（项目根目录）：python test/test_stock_individual_info_em_print.py
可选参数：python test/test_stock_individual_info_em_print.py 600519

批量写库（行业/上市日期/股本等）请用：python manual_scripts/update_stock_basic_info_em.py
"""

import argparse
import sys

import akshare as ak


def main() -> None:
    parser = argparse.ArgumentParser(description="打印 ak.stock_individual_info_em 结果")
    parser.add_argument(
        "symbol",
        nargs="?",
        default="000001",
        help="股票代码，默认 000001",
    )
    args = parser.parse_args()
    symbol = str(args.symbol).strip()
    if not symbol:
        print("股票代码为空", file=sys.stderr)
        sys.exit(1)

    stock_individual_info_em_df = ak.stock_individual_info_em(symbol=symbol)
    print(stock_individual_info_em_df)


if __name__ == "__main__":
    main()
