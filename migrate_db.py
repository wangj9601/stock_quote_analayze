#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本（SQLAlchemy+PostgreSQL 版）
"""
from backend_api.database import SessionLocal, init_db
from backend_api.models import User, Admin
from sqlalchemy import inspect
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

def migrate_database():
    """
迁移数据库，添加缺失的列和表（适配PostgreSQL，推荐直接用Alembic管理迁移）
"""
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        # 检查users表是否有status列
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'status' not in columns:
            print("添加status列到users表...")
            db.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR DEFAULT 'active'"))
            print("✅ 成功添加status列")
        else:
            print("✅ users表已存在status列")
        # 检查admins表是否存在
        if not inspector.has_table('admins'):
            print("创建admins表...")
            init_db()  # 直接用SQLAlchemy自动建表
            print("✅ 成功创建admins表")
        else:
            print("✅ admins表已存在")
        # 检查是否有默认管理员
        admin = db.query(Admin).first()
        if not admin:
            from backend_api.auth import get_password_hash
            admin = Admin(
                username="admin",
                password_hash=get_password_hash("123456"),
                role="super_admin"
            )
            db.add(admin)
            db.commit()
            print("✅ 成功创建默认管理员账号")
        db.commit()
        print("🎉 数据库迁移完成")
    except ProgrammingError as e:
        print(f"❌ 迁移失败: {e}")
        db.rollback()
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    migrate_database() 