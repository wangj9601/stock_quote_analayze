import sys
import os
from sqlalchemy import text

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def migrate_schema():
    print("正在升级 PVFRS 数据库架构以支持未结单交易和自定义任务名称...")
    
    with engine.connect() as conn:
        # 1. 为 pvfrs_backtest_tasks_enhanced 增加 task_name
        try:
            print("尝试添加 pvfrs_backtest_tasks_enhanced.task_name 列...")
            conn.execute(text("ALTER TABLE pvfrs_backtest_tasks_enhanced ADD COLUMN IF NOT EXISTS task_name VARCHAR(200)"))
            conn.commit()
            print("✅ task_name 列添加成功")
        except Exception as e:
            print(f"❌ 添加 task_name 失败: {e}")
            conn.rollback()

        # 2. 为 pvfrs_trade_records_enhanced 修改 trade_date 并增加 entry_date
        try:
            print("修改 pvfrs_trade_records_enhanced.trade_date 为 nullable 并添加 entry_date...")
            conn.execute(text("ALTER TABLE pvfrs_trade_records_enhanced ALTER COLUMN trade_date DROP NOT NULL"))
            conn.execute(text("ALTER TABLE pvfrs_trade_records_enhanced ADD COLUMN IF NOT EXISTS entry_date DATE"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pvfrs_trade_entry_date ON pvfrs_trade_records_enhanced (entry_date)"))
            conn.commit()
            print("✅ 交易记录表更新成功")
        except Exception as e:
            print(f"❌ 交易记录表更新失败: {e}")
            conn.rollback()

    print("数据库升级完成！")

if __name__ == "__main__":
    migrate_schema()
