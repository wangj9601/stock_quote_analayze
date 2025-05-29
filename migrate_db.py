#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def migrate_database():
    """迁移数据库，添加缺失的列"""
    db_path = 'backend_api/database/stock_analysis.db'
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，无需迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查users表是否有status列
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' not in columns:
            print("添加status列到users表...")
            cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
            print("✅ 成功添加status列")
        else:
            print("✅ users表已有status列")
        
        # 检查是否存在admins表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admins'")
        if not cursor.fetchone():
            print("创建admins表...")
            cursor.execute('''
                CREATE TABLE admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            
            # 创建默认管理员账号
            import hashlib
            default_admin_password = hashlib.sha256('123456'.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO admins (username, password_hash, role)
                VALUES (?, ?, ?)
            ''', ('admin', default_admin_password, 'super_admin'))
            print("✅ 成功创建admins表和默认管理员账号")
        else:
            print("✅ admins表已存在")
        
        conn.commit()
        print("🎉 数据库迁移完成")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database() 