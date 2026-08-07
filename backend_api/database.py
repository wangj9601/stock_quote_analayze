"""
数据库配置和工具函数
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from backend_api.config import DATABASE_CONFIG
from fastapi import Depends
from typing import Generator

# 创建数据库引擎（pool_pre_ping：取连接前探测，库重启后自动丢弃死连接并重连）
engine = create_engine(
    DATABASE_CONFIG["url"],
    pool_size=DATABASE_CONFIG["pool_size"],
    max_overflow=DATABASE_CONFIG["max_overflow"],
    echo=DATABASE_CONFIG["echo"],
    pool_pre_ping=True,
    pool_recycle=1800,
)

print("数据库连接URL:", repr(DATABASE_CONFIG["url"]))

# 创建会话工厂（autocommit=False：首次 SQL 即开事务，必须 commit/rollback/close）
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求结束时 rollback + close，避免 idle in transaction。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


@contextmanager
def session_scope():
    """短事务上下文：业务代码优先用此替代 next(get_db())。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()
