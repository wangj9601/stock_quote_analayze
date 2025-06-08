"""
财务报告数据打印工具
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    import argparse
    import akshare as ak
    
    parser = argparse.ArgumentParser(description='财务报告数据打印工具')
    parser.add_argument('--symbol', type=str, required=True,
                      help='股票代码')
    
    args = parser.parse_args()
    
    try:
        # 获取财务报告数据
        df = ak.stock_financial_abstract(symbol=args.symbol)
        print(f"\n成功获取 {args.symbol} 的财务报告数据:")
        print(f"共 {len(df)} 条记录")
        print("\n=== 财务报告数据（逐行打印）===")
        
        # 逐行打印数据
        for index, row in df.iterrows():
            print(f"\n第 {index+1} 行:")
            for col in df.columns:
                print(f"{col}: {row[col]}")
                
    except Exception as e:
        print(f"获取财务报告数据失败: {str(e)}")
        sys.exit(1)