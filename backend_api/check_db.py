"""
检查数据库中的用户数据
"""

import sqlite3
from pathlib import Path
import os

def check_users():
    """检查用户表中的数据"""
    db_path = Path("database/stock_analysis.db")
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查用户表结构
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("\n用户表结构:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # 检查用户数据
        cursor.execute("SELECT id, username, email, password_hash, status, created_at, last_login FROM users")
        users = cursor.fetchall()
        print("\n用户数据:")
        for user in users:
            print(f"\n用户ID: {user[0]}")
            print(f"用户名: {user[1]}")
            print(f"邮箱: {user[2]}")
            print(f"密码哈希: {user[3]}")
            print(f"状态: {user[4]}")
            print(f"创建时间: {user[5]}")
            print(f"最后登录: {user[6]}")
        
        conn.close()
    except Exception as e:
        print(f"检查数据库时出错: {str(e)}")

if __name__ == "__main__":
    check_users() 