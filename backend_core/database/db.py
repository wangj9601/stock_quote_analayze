import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 加载本地 .env：优先项目根目录（backend_core 的上一级）
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

Base = declarative_base()

# 数据库连接：必须从 .env 读取，缺项则报错
def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val or not str(val).strip():
        raise RuntimeError(f"缺少必填环境变量: {name}，请在项目根目录 .env 中配置")
    return str(val).strip()

_db_user = _require_env("DB_USER")
_db_password = _require_env("DB_PASSWORD")
_db_host = _require_env("DB_HOST")
_db_port = _require_env("DB_PORT")
_db_name = _require_env("DB_NAME")

# 若 .env 中已配置完整 DATABASE_URL 则直接使用，否则按上述变量拼接
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{_db_user}:{_db_password}@{_db_host}:{_db_port}/{_db_name}",
)

# 连接池与连接参数：从 .env 读取，未设置时用默认值
_db_pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
_db_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_db_pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("true", "1", "yes")
_db_pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
_db_connect_options = os.getenv(
    "DB_CONNECT_OPTIONS",
    "-c deadlock_timeout=1s -c lock_timeout=5s -c statement_timeout=30s",
)
_db_echo = os.getenv("DB_ECHO", "false").lower() in ("true", "1", "yes")

engine = create_engine(
    DATABASE_URL,
    echo=_db_echo,
    pool_size=_db_pool_size,
    max_overflow=_db_max_overflow,
    pool_pre_ping=_db_pool_pre_ping,
    pool_recycle=_db_pool_recycle,
    connect_args={"options": _db_connect_options} if _db_connect_options else {},
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