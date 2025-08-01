#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_api.database import SessionLocal
from backend_api.models import User
from backend_api.auth import get_password_hash
from datetime import datetime

def quick_add_user():
    """快速添加用户"""
    print("快速添加用户程序")
    print("=" * 40)
    
    try:
        # 获取用户输入
        username = input("请输入用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            return
        
        email = input("请输入邮箱: ").strip()
        if not email:
            print("❌ 邮箱不能为空")
            return
        
        password = input("请输入密码: ").strip()
        if not password:
            print("❌ 密码不能为空")
            return
        
        # 检查用户是否已存在
        db = SessionLocal()
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"❌ 用户名 '{username}' 已存在")
            db.close()
            return
        
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"❌ 邮箱 '{email}' 已被使用")
            db.close()
            return
        
        # 生成密码哈希
        password_hash = get_password_hash(password)
        
        # 创建新用户
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            status="active",
            created_at=datetime.now()
        )
        
        # 添加到数据库
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print("\n✅ 用户创建成功！")
        print(f"用户ID: {new_user.id}")
        print(f"用户名: {new_user.username}")
        print(f"邮箱: {new_user.email}")
        print(f"状态: {new_user.status}")
        print(f"创建时间: {new_user.created_at}")
        print(f"\n现在可以使用用户名 '{username}' 和密码登录系统。")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 创建用户时出错: {str(e)}")
        if 'db' in locals():
            db.rollback()
            db.close()

if __name__ == "__main__":
    quick_add_user() 