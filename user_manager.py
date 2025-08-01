#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_api.database import SessionLocal
from backend_api.models import User
from backend_api.auth import get_password_hash
from datetime import datetime

def show_menu():
    """显示菜单"""
    print("\n" + "=" * 50)
    print("用户管理系统")
    print("=" * 50)
    print("1. 查看所有用户")
    print("2. 添加新用户")
    print("3. 删除用户")
    print("4. 修改用户状态")
    print("5. 退出")
    print("=" * 50)

def list_all_users():
    """列出所有用户"""
    try:
        db = SessionLocal()
        users = db.query(User).all()
        
        print(f"\n当前共有 {len(users)} 个用户:")
        print("-" * 80)
        print(f"{'ID':<4} {'用户名':<15} {'邮箱':<25} {'状态':<10} {'创建时间':<20}")
        print("-" * 80)
        
        for user in users:
            print(f"{user.id:<4} {user.username:<15} {user.email:<25} {user.status:<10} {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 查询用户时出错: {str(e)}")

def add_new_user():
    """添加新用户"""
    print("\n=== 添加新用户 ===")
    
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
        
        print(f"\n✅ 用户 '{username}' 创建成功！")
        print(f"用户ID: {new_user.id}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 创建用户时出错: {str(e)}")
        if 'db' in locals():
            db.rollback()
            db.close()

def delete_user():
    """删除用户"""
    print("\n=== 删除用户 ===")
    
    try:
        # 先显示所有用户
        list_all_users()
        
        user_id = input("\n请输入要删除的用户ID: ").strip()
        if not user_id.isdigit():
            print("❌ 请输入有效的用户ID")
            return
        
        user_id = int(user_id)
        
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            print(f"❌ 用户ID {user_id} 不存在")
            db.close()
            return
        
        print(f"找到用户: {user.username} ({user.email})")
        confirm = input("确认删除此用户吗？(y/n): ").strip().lower()
        
        if confirm in ['y', 'yes', '是']:
            db.delete(user)
            db.commit()
            print(f"✅ 用户 '{user.username}' 已删除")
        else:
            print("取消删除")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 删除用户时出错: {str(e)}")
        if 'db' in locals():
            db.rollback()
            db.close()

def change_user_status():
    """修改用户状态"""
    print("\n=== 修改用户状态 ===")
    
    try:
        # 先显示所有用户
        list_all_users()
        
        user_id = input("\n请输入要修改的用户ID: ").strip()
        if not user_id.isdigit():
            print("❌ 请输入有效的用户ID")
            return
        
        user_id = int(user_id)
        
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            print(f"❌ 用户ID {user_id} 不存在")
            db.close()
            return
        
        print(f"当前用户: {user.username}")
        print(f"当前状态: {user.status}")
        
        new_status = input("请输入新状态 (active/inactive): ").strip().lower()
        if new_status not in ['active', 'inactive']:
            print("❌ 状态只能是 'active' 或 'inactive'")
            db.close()
            return
        
        user.status = new_status
        db.commit()
        
        print(f"✅ 用户 '{user.username}' 状态已修改为 '{new_status}'")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 修改用户状态时出错: {str(e)}")
        if 'db' in locals():
            db.rollback()
            db.close()

def main():
    """主函数"""
    while True:
        show_menu()
        
        choice = input("\n请选择操作 (1-5): ").strip()
        
        if choice == '1':
            list_all_users()
        elif choice == '2':
            add_new_user()
        elif choice == '3':
            delete_user()
        elif choice == '4':
            change_user_status()
        elif choice == '5':
            print("退出用户管理系统")
            break
        else:
            print("❌ 无效选择，请重新输入")
        
        input("\n按回车键继续...")

if __name__ == "__main__":
    main() 