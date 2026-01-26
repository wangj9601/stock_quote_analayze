#!/usr/bin/env python3
"""
测试管理员认证功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal
from backend_api.auth import authenticate_admin
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_admin_auth():
    """测试管理员认证"""
    try:
        with SessionLocal() as db:
            # 测试管理员认证
            print("测试管理员认证...")
            
            # 测试正确的用户名和密码
            admin = authenticate_admin(db, "admin", "admin123")
            if admin:
                print(f"✅ 认证成功: {admin.username}")
                print(f"   ID: {admin.id}")
                print(f"   角色: {admin.role}")
                print(f"   创建时间: {admin.created_at}")
            else:
                print("❌ 认证失败")
                return False
            
            # 测试错误的密码
            admin_wrong = authenticate_admin(db, "admin", "wrong_password")
            if admin_wrong is None:
                print("✅ 错误密码正确被拒绝")
            else:
                print("❌ 错误密码认证失败")
                return False
            
            # 测试不存在的用户
            admin_nonexistent = authenticate_admin(db, "nonexistent", "password")
            if admin_nonexistent is None:
                print("✅ 不存在的用户正确被拒绝")
            else:
                print("❌ 不存在的用户认证失败")
                return False
            
            print("\n🎉 所有认证测试通过!")
            return True
            
    except Exception as e:
        logger.error(f"认证测试失败: {e}")
        print(f"❌ 认证测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_admin_auth()
    sys.exit(0 if success else 1)
