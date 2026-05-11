"""
创建一阳穿三线策略信号数据库表
"""

import os
import sys

_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

from backend_api.database import engine
from backend_api.models import OneYangThreeLinesSignal

def create_one_yang_signal_table():
    """创建一阳穿三线策略信号表"""
    print("正在创建一阳穿三线策略信号数据库表...")
    
    # 创建表
    OneYangThreeLinesSignal.__table__.create(engine, checkfirst=True)
    
    print("一阳穿三线策略信号数据库表创建完成！")
    print(f"表名: {OneYangThreeLinesSignal.__tablename__}")
    print("包含字段:")
    for column in OneYangThreeLinesSignal.__table__.columns:
        print(f"  - {column.name}: {column.type}")

if __name__ == "__main__":
    create_one_yang_signal_table()
