"""
数据库配置和工具函数
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from .config import DATABASE_CONFIG
from fastapi import Depends
from typing import Generator

# 创建数据库引擎
engine = create_engine(
    DATABASE_CONFIG["url"],
    pool_size=DATABASE_CONFIG["pool_size"],
    max_overflow=DATABASE_CONFIG["max_overflow"],
    echo=DATABASE_CONFIG["echo"]
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    from .models import (
        Base, User, Admin, Watchlist, WatchlistGroup,
        StockBasicInfo, QuoteData, QuoteSyncTask
    )
    
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        
        # 创建默认管理员账号
        db = SessionLocal()
        try:
            from .auth import get_password_hash
            
            # 检查是否已存在管理员账号
            admin = db.query(Admin).first()
            if not admin:
                # 创建默认管理员账号
                admin = Admin(
                    username="admin",
                    password_hash=get_password_hash("123456"),
                    role="admin"
                )
                db.add(admin)
                db.commit()
                print("✅ 已创建默认管理员账号: admin / 123456")
        finally:
            db.close()
        
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        raise 