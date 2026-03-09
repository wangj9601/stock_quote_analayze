
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

DATABASE_URL = "postgresql+psycopg2://postgres:qidianspacetime@192.168.31.237:5446/stock_analysis"

# 添加连接参数来减少死锁
engine = create_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接数
    pool_pre_ping=True,  # 连接前ping检查
    pool_recycle=3600,  # 连接回收时间（秒）
    connect_args={
        "options": "-c deadlock_timeout=1s -c lock_timeout=5s -c statement_timeout=30s"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        # 设置会话级别的优化参数
        db.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED;"))
        yield db
    finally:
        if db.is_active:
            db.close()