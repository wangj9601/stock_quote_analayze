"""
测试港股指数接口，查看返回的数据量
"""
import akshare as ak
import pandas as pd

def test_stock_hk_index_spot_em():
    """测试 stock_hk_index_spot_em 接口"""
    print("=" * 60)
    print("测试 stock_hk_index_spot_em 接口")
    print("=" * 60)
    try:
        df = ak.stock_hk_index_spot_em()
        print(f"数据行数: {len(df)}")
        print(f"数据列名: {list(df.columns)}")
        print(f"\n前10行数据:")
        print(df.head(10))
        print(f"\n所有指数代码和名称:")
        if '代码' in df.columns:
            for idx, row in df.iterrows():
                print(f"  {row.get('代码', 'N/A')}: {row.get('名称', 'N/A')}")
        elif 'code' in df.columns:
            for idx, row in df.iterrows():
                print(f"  {row.get('code', 'N/A')}: {row.get('name', 'N/A')}")
    except Exception as e:
        print(f"调用 stock_hk_index_spot_em 失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_stock_hk_index_spot_em()

