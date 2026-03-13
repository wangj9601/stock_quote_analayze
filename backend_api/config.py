"""
backend_api 配置文件，参数均从项目根目录 .env 读取。
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # 生产环境可无 python-dotenv

# 加载项目根目录 .env（有 python-dotenv 时）；生产环境无则使用系统环境变量
_project_root = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(_project_root / ".env")


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = (os.getenv(key) or "").lower().strip()
    if not v:
        return default
    return v in ("true", "1", "yes")


# 数据库配置（与 backend_core/database/db.py 共用 DB_* 或 DATABASE_URL）
_db_url = _env("DATABASE_URL")
if not _db_url:
    _db_url = "postgresql+psycopg2://{user}:{pw}@{host}:{port}/{name}".format(
        user=_env("DB_USER"),
        pw=_env("DB_PASSWORD"),
        host=_env("DB_HOST"),
        port=_env("DB_PORT"),
        name=_env("DB_NAME"),
    )
DATABASE_CONFIG = {
    "url": _db_url,
    "pool_size": _env_int("DB_POOL_SIZE", 5),
    "max_overflow": _env_int("DB_MAX_OVERFLOW", 10),
    "echo": _env_bool("DB_ECHO", False),
}

# JWT 配置
JWT_CONFIG = {
    "secret_key": _env("JWT_SECRET_KEY", "your-secret-key-here"),
    "algorithm": _env("JWT_ALGORITHM", "HS256"),
    "access_token_expire_minutes": _env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440),
}

# API 配置
API_CONFIG = {
    "title": _env("API_TITLE", "股票分析系统API"),
    "description": _env("API_DESCRIPTION", "股票分析系统的后端API服务"),
    "version": _env("API_VERSION", "1.0.0"),
}

# CORS 配置（CORS_ORIGINS 逗号分隔，未设则为 *）
_cors_origins = _env("CORS_ORIGINS")
CORS_CONFIG = {
    "allow_origins": [x.strip() for x in _cors_origins.split(",")] if _cors_origins else ["*"],
    "allow_credentials": _env_bool("CORS_ALLOW_CREDENTIALS", True),
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

# Gemini AI API Key
GEMINI_API_KEY = _env("GEMINI_API_KEY")

# SMTP 邮件配置
SMTP_CONFIG = {
    "host": _env("SMTP_HOST", "smtp.gmail.com"),
    "port": _env_int("SMTP_PORT", 587),
    "username": _env("SMTP_USERNAME"),
    "password": _env("SMTP_PASSWORD"),
    "use_tls": _env_bool("SMTP_USE_TLS", True),
    "from_email": _env("SMTP_FROM_EMAIL"),
    "from_name": _env("SMTP_FROM_NAME", "股票分析系统"),
}

# 推送配置
_default_push_times = _env("PUSH_DEFAULT_TIMES", "09:30,15:30")
PUSH_CONFIG = {
    "max_retry_count": _env_int("MAX_RETRY_COUNT", 3),
    "push_batch_size": _env_int("PUSH_BATCH_SIZE", 100),
    "report_dir": _env("REPORT_DIR", "./reports"),
    "default_push_times": [x.strip() for x in _default_push_times.split(",") if x.strip()] or ["09:30", "15:30"],
}

# 微信配置
WECHAT_CONFIG = {
    "corp_id": _env("WECHAT_CORP_ID"),
    "agent_id": _env("WECHAT_AGENT_ID"),
    "secret": _env("WECHAT_SECRET"),
    "token": _env("WECHAT_TOKEN"),
    "encoding_aes_key": _env("WECHAT_ENCODING_AES_KEY"),
}
