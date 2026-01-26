#!/usr/bin/env python3
"""
初始化系统监控数据库表
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_api.database import engine, Base
from backend_api.models import (
    SystemMonitorMetric, 
    SystemAlert, 
    SystemServiceStatus, 
    SystemAlertRule, 
    SystemPerformanceReport
)
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_monitoring_tables():
    """创建系统监控相关的数据库表"""
    try:
        print("开始创建系统监控数据库表...")
        
        # 创建所有系统监控相关的表
        Base.metadata.create_all(engine, tables=[
            SystemMonitorMetric.__table__,
            SystemAlert.__table__,
            SystemServiceStatus.__table__,
            SystemAlertRule.__table__,
            SystemPerformanceReport.__table__
        ])
        
        print("✅ 系统监控数据库表创建成功!")
        
        # 检查表是否创建成功
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        monitoring_tables = [
            'system_monitor_metrics',
            'system_alerts',
            'system_service_status',
            'system_alert_rules',
            'system_performance_reports'
        ]
        
        print("\n📋 数据库表检查:")
        for table in monitoring_tables:
            if table in tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table}")
        
        return True
        
    except Exception as e:
        logger.error(f"创建系统监控数据库表失败: {e}")
        print(f"❌ 创建系统监控数据库表失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_monitoring_tables()
    sys.exit(0 if success else 1)
