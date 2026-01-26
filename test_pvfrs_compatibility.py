#!/usr/bin/env python3
"""
测试PVFRS监控兼容性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.strategies.pvfrs.monitor_service import MonitorService
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pvfrs_monitoring_compatibility():
    """测试PVFRS监控兼容性"""
    try:
        print("测试PVFRS监控兼容性...")
        
        # 获取PVFRS监控服务实例
        pvfrs_monitor = MonitorService()
        print("✅ PVFRS监控服务实例获取成功")
        
        # 测试获取监控数据
        print("\n1. 测试获取监控数据...")
        monitoring_data = pvfrs_monitor.get_monitoring_data()
        print(f"✅ 监控数据获取成功:")
        print(f"   状态: {monitoring_data.get('status', 'unknown')}")
        print(f"   告警数量: {monitoring_data.get('alerts', {}).get('total_24h', 0)}")
        
        # 测试创建告警
        print("\n2. 测试创建PVFRS告警...")
        pvfrs_monitor.add_alert(
            level="MEDIUM",
            title="PVFRS测试告警",
            message="这是一个PVFRS测试告警",
            alert_type="pvfrs_test",
            source="pvfrs"
        )
        print("✅ PVFRS告警创建成功")
        
        # 测试记录指标
        print("\n3. 测试记录PVFRS指标...")
        pvfrs_monitor.record_metric("pvfrs_test_metric", 0.75, {"strategy": "pvfrs"})
        print("✅ PVFRS指标记录成功")
        
        # 测试获取PVFRS特定指标
        print("\n4. 测试获取PVFRS特定指标...")
        pvfrs_metrics = pvfrs_monitor.get_performance_metrics()
        print(f"✅ PVFRS指标获取成功: {len(pvfrs_metrics)} 个指标")
        
        # 测试获取PVFRS告警
        print("\n5. 测试获取PVFRS告警...")
        pvfrs_alerts = pvfrs_monitor.get_monitoring_alerts()
        print(f"✅ PVFRS告警获取成功: {len(pvfrs_alerts)} 条告警")
        
        print("\n🎉 所有PVFRS监控兼容性测试通过!")
        return True
        
    except Exception as e:
        logger.error(f"PVFRS监控兼容性测试失败: {e}")
        print(f"❌ PVFRS监控兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pvfrs_monitoring_compatibility()
    sys.exit(0 if success else 1)
