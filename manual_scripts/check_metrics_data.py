import sys
import os
from sqlalchemy import text

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine

def check_metrics():
    print("正在检查 pvfrs_monitor_metrics 数据...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM pvfrs_monitor_metrics ORDER BY timestamp DESC LIMIT 5"))
        rows = result.fetchall()
        if rows:
            print(f"找到 {len(rows)} 条监控数据:")
            for row in rows:
                print(row)
        else:
            print("尚未找到监控数据")

if __name__ == "__main__":
    check_metrics()
