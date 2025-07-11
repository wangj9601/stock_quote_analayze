"""
检查数据库中的用户数据（SQLAlchemy版，适配PostgreSQL）
"""

from sqlalchemy.orm import Session
from backend_api.database import SessionLocal
from backend_api.models import User

def check_users():
    """检查用户表中的数据"""
    try:
        db: Session = SessionLocal()
        # 检查用户表结构
        print("\n用户表结构:")
        for column in User.__table__.columns:
            print(f"  {column.name} ({column.type})")
        # 检查用户数据
        users = db.query(User).all()
        print("\n用户数据:")
        for user in users:
            print(f"\n用户ID: {user.id}")
            print(f"用户名: {user.username}")
            print(f"邮箱: {user.email}")
            print(f"密码哈希: {user.password_hash}")
            print(f"状态: {user.status}")
            print(f"创建时间: {user.created_at}")
            print(f"最后登录: {user.last_login}")
        db.close()
    except Exception as e:
        print(f"检查数据库时出错: {str(e)}")

if __name__ == "__main__":
    check_users() 