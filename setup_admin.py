#!/usr/bin/env python3
"""
设置默认管理员账户脚本
用于创建默认的管理员用户
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal
from backend_api.models import Admin
from backend_api.auth import get_password_hash
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_default_admin():
    """创建默认管理员账户"""
    try:
        with SessionLocal() as db:
            # 检查是否已存在管理员
            existing_admin = db.query(Admin).first()
            
            if existing_admin:
                logger.info(f"管理员账户已存在: {existing_admin.username}")
                print(f"✅ 管理员账户已存在: {existing_admin.username}")
                return existing_admin
            
            # 创建默认管理员
            default_username = "admin"
            default_password = "admin123"  # 建议首次登录后修改
            
            logger.info("创建默认管理员账户...")
            
            admin = Admin(
                username=default_username,
                password_hash=get_password_hash(default_password),
                role="admin"
            )
            
            db.add(admin)
            db.commit()
            db.refresh(admin)
            
            logger.info(f"默认管理员账户创建成功: {admin.username}")
            print(f"✅ 默认管理员账户创建成功!")
            print(f"   用户名: {admin.username}")
            print(f"   密码: {default_password}")
            print(f"   ⚠️  请在首次登录后立即修改密码!")
            
            return admin
            
    except Exception as e:
        logger.error(f"创建管理员账户失败: {e}")
        print(f"❌ 创建管理员账户失败: {e}")
        return None

def list_admins():
    """列出所有管理员"""
    try:
        with SessionLocal() as db:
            admins = db.query(Admin).all()
            
            if not admins:
                print("📝 没有找到管理员账户")
                return
            
            print(f"📝 管理员账户列表 ({len(admins)} 个):")
            for admin in admins:
                print(f"   - ID: {admin.id}, 用户名: {admin.username}, 角色: {admin.role}, 创建时间: {admin.created_at}")
                
    except Exception as e:
        logger.error(f"查询管理员账户失败: {e}")
        print(f"❌ 查询管理员账户失败: {e}")

def reset_admin_password(username: str, new_password: str):
    """重置管理员密码"""
    try:
        with SessionLocal() as db:
            admin = db.query(Admin).filter(Admin.username == username).first()
            
            if not admin:
                print(f"❌ 管理员用户 {username} 不存在")
                return False
            
            admin.password_hash = get_password_hash(new_password)
            db.commit()
            
            logger.info(f"管理员 {username} 密码重置成功")
            print(f"✅ 管理员 {username} 密码重置成功")
            print(f"   新密码: {new_password}")
            print(f"   ⚠️  请妥善保管新密码!")
            
            return True
            
    except Exception as e:
        logger.error(f"重置管理员密码失败: {e}")
        print(f"❌ 重置管理员密码失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("管理员账户设置工具")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python setup_admin.py create          # 创建默认管理员")
        print("  python setup_admin.py list            # 列出所有管理员")
        print("  python setup_admin.py reset <用户名>  # 重置指定管理员密码")
        print("\n示例:")
        print("  python setup_admin.py create")
        print("  python setup_admin.py reset admin")
        return
    
    command = sys.argv[1].lower()
    
    if command == "create":
        create_default_admin()
    elif command == "list":
        list_admins()
    elif command == "reset":
        if len(sys.argv) < 3:
            print("❌ 请提供要重置密码的管理员用户名")
            print("用法: python setup_admin.py reset <用户名>")
            return
        
        username = sys.argv[2]
        new_password = input("请输入新密码: ") or "admin123"
        reset_admin_password(username, new_password)
    else:
        print(f"❌ 未知命令: {command}")
        print("可用命令: create, list, reset")

if __name__ == "__main__":
    main()
