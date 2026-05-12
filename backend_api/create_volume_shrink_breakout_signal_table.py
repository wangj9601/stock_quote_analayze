"""
创建 3倍量缩量突破策略信号表 volume_shrink_breakout_signals
"""

import os
import sys

# 允许从任意 cwd 执行：python backend_api/xxx.py 或 python run/backend_api/xxx.py
_pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

from backend_api.database import engine
from backend_api.models import VolumeShrinkBreakoutSignal


def create_volume_shrink_breakout_signal_table():
    print("正在创建 volume_shrink_breakout_signals 表...")
    VolumeShrinkBreakoutSignal.__table__.create(engine, checkfirst=True)
    print("创建完成:", VolumeShrinkBreakoutSignal.__tablename__)
    for column in VolumeShrinkBreakoutSignal.__table__.columns:
        print(f"  - {column.name}: {column.type}")


if __name__ == "__main__":
    create_volume_shrink_breakout_signal_table()
