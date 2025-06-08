import akshare as ak
import pandas as pd
import sys

# 以贵州茅台（sh600519）为例
stock_code = "600519"

try:
    df = ak.stock_financial_abstract(symbol=stock_code)
    print(f"成功获取 {stock_code} 的财务报告数据:")
    
    # 打印所有可用的列名
    print("\n可用的指标列:")
    for col in df.columns:
        print(f"- {col}")
        
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

# 查看返回的DataFrame结构
# print("\n返回数据前5行:")
# print(financial_analysis_df.head())