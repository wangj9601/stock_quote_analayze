#!/usr/bin/env python3
"""
测试系统监控功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.monitoring import system_monitor, alert_manager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_system_monitoring():
    """测试系统监控功能"""
    try:
        print("测试系统监控功能...")
        
        # 1. 测试系统健康状态
        print("\n1. 测试系统健康状态...")
        health = system_monitor.get_system_health()
        print(f"✅ 系统健康状态获取成功:")
        print(f"   CPU使用率: {health.cpu_usage}%")
        print(f"   内存使用率: {health.memory_usage}%")
        print(f"   磁盘使用率: {health.disk_usage}%")
        print(f"   服务数量: {len(health.service_status)}")
        
        # 2. 测试告警管理
        print("\n2. 测试告警管理...")
        
        # 创建测试告警
        alert_id = alert_manager.create_alert(
            level="LOW",
            title="测试告警",
            message="这是一个测试告警",
            alert_type="test",
            source="test_script"
        )
        
        if alert_id:
            print(f"✅ 告警创建成功: ID {alert_id}")
        else:
            print("❌ 告警创建失败")
            return False
        
        # 获取告警列表
        alerts = alert_manager.get_alerts(limit=5)
        print(f"✅ 告警列表获取成功: {len(alerts)} 条告警")
        
        # 确认告警
        if alerts:
            first_alert_id = alerts[0]["id"]
            success = alert_manager.acknowledge_alert(first_alert_id, "test_user")
            if success:
                print(f"✅ 告警确认成功: ID {first_alert_id}")
            else:
                print(f"❌ 告警确认失败: ID {first_alert_id}")
        
        # 3. 测试指标记录
        print("\n3. 测试指标记录...")
        system_monitor.record_metric("test_metric", 0.85, {"test": "monitoring"})
        print("✅ 指标记录成功")
        
        # 获取性能指标
        metrics = system_monitor.get_performance_metrics("1h", "1m")
        print(f"✅ 性能指标获取成功: {len(metrics)} 个指标")
        
        # 4. 测试监控概览
        print("\n4. 测试监控概览...")
        overview = system_monitor.get_monitoring_data()
        print(f"✅ 监控概览获取成功:")
        print(f"   状态: {overview.get('status', 'unknown')}")
        print(f"   告警数量: {overview.get('alerts', {}).get('total_24h', 0)}")
        
        print("\n🎉 所有系统监控测试通过!")
        return True
        
    except Exception as e:
        logger.error(f"系统监控测试失败: {e}")
        print(f"❌ 系统监控测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system_monitoring()
    sys.exit(0 if success else 1)
