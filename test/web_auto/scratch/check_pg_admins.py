import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 从环境变量或硬编码获取（参考 .env）
DB_URL = "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis"

def check_admins():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("🔍 正在检查 PostgreSQL 中的 admins 表...")
        result = conn.execute(text("SELECT username, password_hash, role FROM admins"))
        admins = result.fetchall()
        
        if not admins:
            print("⚠️ 数据库中没有管理员账号")
        else:
            for admin in admins:
                print(f"👤 用户名: {admin[0]}, 角色: {admin[2]}")
                # 打印哈希的前10位用于比对
                print(f"   哈希前缀: {admin[1][:10]}...")

if __name__ == "__main__":
    try:
        check_admins()
    except Exception as e:
        print(f"❌ 检查失败: {e}")
