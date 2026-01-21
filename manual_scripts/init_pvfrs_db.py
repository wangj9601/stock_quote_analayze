import sys
import os

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from backend_api.database import engine, Base
from backend_api.models import (
    PVFRSStrategyConfig,
    PVFRSBacktestTask,
    PVFRSBacktestResult,
    PVFRSTradeRecord,
    PVFRSEquityCurve,
    PVFRSAlert,
    PVFRSMonitorMetric
)

def init_pvfrs_tables():
    print("开始初始化 PVFRS 策略管理模块相关数据库表...")
    try:
        # 确保这些模型已经绑定到 Base 并创建
        Base.metadata.create_all(bind=engine, tables=[
            PVFRSStrategyConfig.__table__,
            PVFRSBacktestTask.__table__,
            PVFRSBacktestResult.__table__,
            PVFRSTradeRecord.__table__,
            PVFRSEquityCurve.__table__,
            PVFRSAlert.__table__,
            PVFRSMonitorMetric.__table__
        ])
        print("✅ PVFRS 相关表创建/更新成功！")
    except Exception as e:
        print(f"❌ 初始化失败: {str(e)}")

if __name__ == "__main__":
    init_pvfrs_tables()
