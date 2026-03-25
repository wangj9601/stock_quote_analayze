"""
AKShare：雪球个股实时行情 stock_individual_spot_xq，打印 DataFrame。

运行（项目根目录）：
  python test/test_stock_individual_spot_xq_print.py
  python test/test_stock_individual_spot_xq_print.py SH600000
  python test/test_stock_individual_spot_xq_print.py SH513520 --timeout 10
  python test/test_stock_individual_spot_xq_print.py SH600000 --token your_token
"""

import argparse
import sys

import akshare as ak


def main() -> None:
    parser = argparse.ArgumentParser(description="打印 ak.stock_individual_spot_xq 结果")
    parser.add_argument(
        "symbol",
        nargs="?",
        default="SH513520",
        help="证券代码，默认 SH513520",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="雪球 token，默认不传",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="请求超时秒数，默认不传",
    )
    args = parser.parse_args()

    symbol = str(args.symbol).strip()
    if not symbol:
        print("symbol 不能为空", file=sys.stderr)
        sys.exit(1)

    try:
        df = ak.stock_individual_spot_xq(
            symbol=symbol,
            token=args.token,
            timeout=args.timeout,
        )
        print(df)
    except KeyError as e:
        # 雪球接口偶发返回反爬/未登录结构，AKShare 内部按 data.quote 取值会触发 KeyError
        print(
            f"调用失败: {e}。接口返回中缺少预期字段，可能是雪球风控或 token 无效。",
            file=sys.stderr,
        )
        print("建议重试方式：", file=sys.stderr)
        print("1) 增加 --token 参数（有效雪球 token）", file=sys.stderr)
        print("2) 更换 symbol 后重试，例如 SH513520", file=sys.stderr)
        print("3) 稍后再试，避免高频请求", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"调用异常: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
