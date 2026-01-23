"""
测试 PVFRS 报告列表 API
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend_api.models.pvfrs_enhanced import PVFRSBacktestResultEnhanced

def test_reports():
    """测试报告数据"""
    # 创建数据库连接
    db_url = "mysql+pymysql://root:123456@localhost:3306/stock_data?charset=utf8mb4"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 查询所有回测结果
        results = session.query(PVFRSBacktestResultEnhanced).all()
        
        print(f"数据库中共有 {len(results)} 条回测结果记录")
        print("-" * 80)
        
        if results:
            for i, result in enumerate(results[:5], 1):  # 只显示前5条
                print(f"\n记录 {i}:")
                print(f"  ID: {result.id}")
                print(f"  Task ID: {result.task_id}")
                print(f"  Report ID: {result.report_id}")
                print(f"  Stock Code: {result.stock_code}")
                print(f"  Total Return: {result.total_return}")
                print(f"  Sharpe Ratio: {result.sharpe_ratio}")
                print(f"  Win Rate: {result.win_rate}")
                print(f"  Created At: {result.created_at}")
        else:
            print("\n⚠️ 数据库中没有回测结果记录！")
            print("这就是为什么报告列表显示不了的原因。")
            print("\n建议：")
            print("1. 先运行一次回测任务来生成报告数据")
            print("2. 或者检查是否使用了正确的数据库")
            
    except Exception as e:
        print(f"❌ 查询失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_reports()
