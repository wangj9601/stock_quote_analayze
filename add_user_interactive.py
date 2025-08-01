#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend_api.database import SessionLocal
from backend_api.models import User
from backend_api.auth import get_password_hash
from datetime import datetime
import re

def validate_username(username):
    """验证用户名格式"""
    if not username:
        return False, "用户名不能为空"
    
    if len(username) < 3:
        return False, "用户名长度至少3个字符"
    
    if len(username) > 20:
        return False, "用户名长度不能超过20个字符"
    
    # 只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含字母、数字和下划线"
    
    return True, "用户名格式正确"

def validate_password(password):
    """验证密码格式"""
    if not password:
        return False, "密码不能为空"
    
    if len(password) < 6:
        return False, "密码长度至少6个字符"
    
    if len(password) > 50:
        return False, "密码长度不能超过50个字符"
    
    return True, "密码格式正确"

def validate_email(email):
    """验证邮箱格式"""
    if not email:
        return False, "邮箱不能为空"
    
    # 简单的邮箱格式验证
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "邮箱格式不正确"
    
    return True, "邮箱格式正确"

def check_user_exists(username, email):
    """检查用户是否已存在"""
    try:
        db = SessionLocal()
        
        # 检查用户名
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            db.close()
            return True, "用户名已存在"
        
        # 检查邮箱
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            db.close()
            return True, "邮箱已被使用"
        
        db.close()
        return False, "用户名和邮箱都可用"
        
    except Exception as e:
        return True, f"检查用户时出错: {str(e)}"

def create_user(username, email, password):
    """创建新用户"""
    try:
        db = SessionLocal()
        
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
        
        # 刷新对象以获取ID
        db.refresh(new_user)
        
        print("\n✅ 用户创建成功！")
        print(f"用户ID: {new_user.id}")
        print(f"用户名: {new_user.username}")
        print(f"邮箱: {new_user.email}")
        print(f"状态: {new_user.status}")
        print(f"创建时间: {new_user.created_at}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"\n❌ 创建用户时出错: {str(e)}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

def get_user_input():
    """获取用户输入"""
    print("=" * 60)
    print("新增用户程序")
    print("=" * 60)
    
    # 获取用户名
    while True:
        username = input("\n请输入用户名 (3-20个字符，只能包含字母、数字、下划线): ").strip()
        is_valid, message = validate_username(username)
        if is_valid:
            break
        else:
            print(f"❌ {message}")
    
    # 获取邮箱
    while True:
        email = input("请输入邮箱: ").strip()
        is_valid, message = validate_email(email)
        if is_valid:
            break
        else:
            print(f"❌ {message}")
    
    # 获取密码
    while True:
        password = input("请输入密码 (至少6个字符): ").strip()
        is_valid, message = validate_password(password)
        if is_valid:
            break
        else:
            print(f"❌ {message}")
    
    # 确认密码
    while True:
        confirm_password = input("请再次输入密码确认: ").strip()
        if password == confirm_password:
            break
        else:
            print("❌ 两次输入的密码不一致，请重新输入")
    
    return username, email, password

def main():
    """主函数"""
    try:
        # 获取用户输入
        username, email, password = get_user_input()
        
        print(f"\n正在验证用户信息...")
        print(f"用户名: {username}")
        print(f"邮箱: {email}")
        
        # 检查用户是否已存在
        exists, message = check_user_exists(username, email)
        if exists:
            print(f"❌ {message}")
            return
        
        print("✅ 用户名和邮箱都可用")
        
        # 确认创建
        confirm = input(f"\n确认创建用户 '{username}' 吗？(y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '是']:
            print("用户取消创建")
            return
        
        # 创建用户
        if create_user(username, email, password):
            print(f"\n🎉 用户 '{username}' 创建成功！")
            print(f"现在可以使用用户名 '{username}' 和密码登录系统。")
        else:
            print(f"\n❌ 用户创建失败")
            
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n程序出错: {str(e)}")

if __name__ == "__main__":
    main() 