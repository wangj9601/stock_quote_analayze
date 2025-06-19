#!/usr/bin/env python3
"""
测试配置文件是否正确
"""

import sys
from pathlib import Path

def test_config():
    print("=== 测试配置文件 ===")
    
    try:
        # 测试 backend_core 配置
        print("1. 测试 backend_core 配置...")
        from backend_core.config.config import ROOT_DIR, DB_DIR, DATA_COLLECTORS
        print(f"   项目根目录: {ROOT_DIR}")
        print(f"   数据库目录: {DB_DIR}")
        print(f"   数据库文件: {DATA_COLLECTORS['tushare']['db_file']}")
        print("   ✓ backend_core 配置正常")
        
        # 测试 backend_api 配置
        print("2. 测试 backend_api 配置...")
        from backend_api.config import DB_DIR as API_DB_DIR, DB_PATH
        print(f"   API数据库目录: {API_DB_DIR}")
        print(f"   API数据库文件: {DB_PATH}")
        print("   ✓ backend_api 配置正常")
        
        # 测试数据库目录是否存在
        print("3. 测试数据库目录...")
        if DB_DIR.exists():
            print(f"   ✓ 数据库目录存在: {DB_DIR}")
        else:
            print(f"   ⚠ 数据库目录不存在，将创建: {DB_DIR}")
            DB_DIR.mkdir(parents=True, exist_ok=True)
            print(f"   ✓ 数据库目录已创建: {DB_DIR}")
        
        # 测试日志目录
        print("4. 测试日志目录...")
        log_dir = ROOT_DIR / 'backend_core' / 'logs'
        if log_dir.exists():
            print(f"   ✓ 日志目录存在: {log_dir}")
        else:
            print(f"   ⚠ 日志目录不存在，将创建: {log_dir}")
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"   ✓ 日志目录已创建: {log_dir}")
        
        print("\n=== 所有配置测试通过 ===")
        return True
        
    except Exception as e:
        print(f"   ✗ 配置测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_config()
    sys.exit(0 if success else 1) 