"""
AKShare数据采集器入口文件
用于运行各种数据采集任务
"""

import sys
from pathlib import Path
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


if __name__ == '__main__':
    import argparse
    import akshare as ak
    
    parser = argparse.ArgumentParser(description='AKShare数据采集工具')
    parser.add_argument('--type', type=str, required=True,
                      choices=['realtime_xq', 'historical', 'index', 'indicator','financial_report',
                               'financial_report_sina'],
                      help='采集类型：realtime_xq(雪球实时行情), historical(雪球历史行情), index(指数行情), indicator(技术指标)')
    parser.add_argument('--date', type=str,
                      help='历史行情采集的日期，格式：YYYYMMDD')
    parser.add_argument('--symbol', type=str,
                      help='股票代码，用于获取技术指标数据')
    
    args = parser.parse_args()
    

    if args.type == 'indicator':
        if not args.symbol:
            print("获取技术指标需要指定股票代码参数 --symbol")
            sys.exit(1)
        try:
            # 调用 stock_a_indicator_lg 接口获取技术指标数据
            df = ak.stock_a_indicator_lg(symbol=args.symbol)
            print(f"成功获取 {args.symbol} 的技术指标数据:")
            print(f"共获取到 {len(df)} 条技术指标记录")
            print(df)
        except Exception as e:
            print(f"获取技术指标数据失败: {str(e)}")
            sys.exit(1)
    elif args.type == 'realtime_xq':
        if not args.symbol:
            print("获取实时行情需要指定股票代码参数 --symbol")
            sys.exit(1)
        try:
            # 使用 stock_zh_a_spot_em 接口获取实时行情数据
            df = ak.stock_zh_a_spot_em()
            # 过滤出指定股票的数据
            df = df[df['代码'] == args.symbol]
            if df.empty:
                print(f"未找到股票 {args.symbol} 的实时行情数据")
                sys.exit(1)
            print(f"成功获取 {args.symbol} 的实时行情数据:")
            print(f"共获取到 {len(df)} 条行情记录")
            print(df)
        except Exception as e:
            print(f"获取实时行情数据失败: {str(e)}")
            sys.exit(1)    

    elif args.type == 'financial_report':
    # 在 financial_report 部分
        try:
            df = ak.stock_financial_abstract_ths(symbol=args.symbol,indicator="按报告期")
            print(f"成功获取 {args.symbol} 的财务报告数据:")
            
            # 确保数据按报告日期排序
            if '报告期' in df.columns:
                df = df.sort_values('报告期', ascending=False)
                # 只获取最新报告期的数据
                latest_date = df['报告期'].iloc[0]
                df_latest = df[df['报告期'] == latest_date]
                
                print(f"\n=== 最新报告期 ({latest_date}) 财务数据 ===")
                print(f"共 {len(df_latest)} 条记录")
                print(f"{'='*100}")
                
                # 打印最新报告期的数据
                for index, row in df_latest.iterrows():
                    print(f"\n记录 {index+1}:")
                    for col in df.columns:
                        if col != '报告期':
                            value = row[col]
                            if pd.isna(value):
                                print(f"{col}: NaN")
                            elif isinstance(value, (int, float)):
                                print(f"{col}: {value:,.2f}")
                            else:
                                print(f"{col}: {value}")
            else:
                print("\n警告：数据中没有'报告期'列")
                sys.exit(1)
            
        except Exception as e:
            print(f"获取财务报告数据失败: {str(e)}")
            sys.exit(1)


    elif args.type == 'financial_report_sina':
    # 在 financial_report 部分
        try:
            #df = ak.stock_financial_abstract(symbol=args.symbol)
            #df = ak.stock_financial_report_sina(stock="600519", symbol="利润表")
            df = ak.stock_financial_report_sina(stock="600519", symbol="现金流量表")
            print(f"成功获取 {args.symbol} 的财务报告数据:")
            print(df)

            # 逐行打印
            for index, row in df.iterrows():
                print("\n=== 第 {} 行 ===".format(index + 1))
                for column in df.columns:
                    print(f"{column}: {row[column]}")      

        except Exception as e:
            print(f"获取财务报告数据失败: {str(e)}")
            sys.exit(1)            