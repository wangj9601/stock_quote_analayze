import sys
import os
from sqlalchemy import text

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def migrate_schema():
    print("正在检查并修复 PVFRS 增强版模型数据库架构...")
    
    with engine.connect() as conn:
        # 1. 为 pvfrs_backtest_results_enhanced 增加 report_id
        try:
            print("尝试添加 pvfrs_backtest_results_enhanced.report_id 列...")
            conn.execute(text("ALTER TABLE pvfrs_backtest_results_enhanced ADD COLUMN IF NOT EXISTS report_id VARCHAR(50)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_pvfrs_results_report_id ON pvfrs_backtest_results_enhanced (report_id)"))
            conn.commit()
            print("✅ report_id 列添加成功或已存在")
        except Exception as e:
            print(f"❌ 添加 report_id 失败: {e}")
            conn.rollback()

        # 2. 为其他可能缺少的列进行补全 (根据 pvfrs_enhanced.py)
        try:
            print("正在检查 pvfrs_backtest_results_enhanced 的其他列...")
            # 注意：此处列出的是可能新加的列
            new_columns = [
                ("config_snapshot", "JSON"),
                ("summary_data", "JSON")
            ]
            for col_name, col_type in new_columns:
                conn.execute(text(f"ALTER TABLE pvfrs_backtest_results_enhanced ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            conn.commit()
            print("✅ pvfrs_backtest_results_enhanced 列补全完成")
        except Exception as e:
            print(f"❌ 补全列失败: {e}")
            conn.rollback()

    print("架构修复工作完成！")

if __name__ == "__main__":
    migrate_schema()
