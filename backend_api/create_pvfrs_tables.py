"""
创建PVFRS回测相关数据库表
"""

import os
import sys

_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

from backend_api.database import engine
from backend_api.models import (
    PVFRSBacktestTask, PVFRSBacktestResult, 
    PVFRSTradeRecord, PVFRSEquityCurve
)

def create_pvfrs_tables():
    """创建PVFRS回测相关表"""
    print("正在创建PVFRS回测相关数据库表...")
    
    # 创建表
    PVFRSBacktestTask.__table__.create(engine, checkfirst=True)
    PVFRSBacktestResult.__table__.create(engine, checkfirst=True)
    PVFRSTradeRecord.__table__.create(engine, checkfirst=True)
    PVFRSEquityCurve.__table__.create(engine, checkfirst=True)
    
    print("PVFRS回测相关数据库表创建完成！")

if __name__ == "__main__":
    create_pvfrs_tables()
