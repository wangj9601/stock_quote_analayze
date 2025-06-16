"""
启动脚本
用于运行 backend_core 定时采集服务
"""

import os
import sys
from pathlib import Path

def main():
    print("=" * 50)
    print("📊 启动 backend_core 定时采集服务")
    print("=" * 50)

    # 检查依赖
    print("🔍 检查依赖包...")
    try:
        import apscheduler
        import akshare
        import tushare
        import pandas
        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r backend_core/requirements.txt")
        return

    # 启动 backend_core（自动拉起定时采集进程）
    print("\n🚀 启动定时采集进程...")
    try:
        import backend_core
        backend_core.start_collector_process()
        print("✅ backend_core 已启动，定时采集进程已在后台运行")
        print("如需查看日志，请查看 backend_core/logs/ 目录")
        print("按 Ctrl+C 停止服务")
        print("=" * 50)
        # 阻塞主线程，保持进程存活
        import time
        while True:
            time.sleep(60)
    except Exception as e:
        print(f"❌ 启动 backend_core 失败: {e}")

if __name__ == "__main__":
    main() 