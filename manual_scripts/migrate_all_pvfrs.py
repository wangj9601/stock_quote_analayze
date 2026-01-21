import sys
import os
from sqlalchemy import text, inspect

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def migrate_schema():
    print("正在检查并全面修复 PVFRS 数据架构...")
    
    with engine.connect() as conn:
        # 1. 检查 pvfrs_backtest_tasks_enhanced
        try:
            print("检查 pvfrs_backtest_tasks_enhanced...")
            conn.execute(text("ALTER TABLE pvfrs_backtest_tasks_enhanced ADD COLUMN IF NOT EXISTS total_stocks INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE pvfrs_backtest_tasks_enhanced ADD COLUMN IF NOT EXISTS processed_stocks INTEGER DEFAULT 0"))
            conn.commit()
            print("✅ pvfrs_backtest_tasks_enhanced 补全成功")
        except Exception as e:
            print(f"❌ pvfrs_backtest_tasks_enhanced 补全失败: {e}")
            conn.rollback()

        # 2. 检查 pvfrs_backtest_results_enhanced (之前可能已经执行过，但为了稳妥再跑一次)
        try:
            print("检查 pvfrs_backtest_results_enhanced...")
            conn.execute(text("ALTER TABLE pvfrs_backtest_results_enhanced ADD COLUMN IF NOT EXISTS report_id VARCHAR(50)"))
            conn.execute(text("ALTER TABLE pvfrs_backtest_results_enhanced ADD COLUMN IF NOT EXISTS config_snapshot JSON"))
            conn.execute(text("ALTER TABLE pvfrs_backtest_results_enhanced ADD COLUMN IF NOT EXISTS summary_data JSON"))
            conn.commit()
            print("✅ pvfrs_backtest_results_enhanced 补全成功")
        except Exception as e:
            print(f"❌ pvfrs_backtest_results_enhanced 补全失败: {e}")
            conn.rollback()

    print("全面修复工作完成！")

if __name__ == "__main__":
    migrate_schema()
