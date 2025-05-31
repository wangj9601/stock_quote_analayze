"""
backend_api配置文件
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库目录
DB_DIR = Path(r"E:\wangxw\股票分析软件\编码\stock_quote_analayze\database")
DB_DIR.mkdir(parents=True, exist_ok=True)

# 数据库文件路径
DB_PATH = str(DB_DIR / 'stock_analysis.db')

# 数据库配置
DATABASE_CONFIG = {
    "url": os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}"),
    "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "5")),
    "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
    "echo": os.getenv("DATABASE_ECHO", "False").lower() == "true"
}

# JWT配置
JWT_CONFIG = {
    "secret_key": os.getenv("JWT_SECRET_KEY", "your-secret-key-here"),
    "algorithm": "HS256",
    "access_token_expire_minutes": int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24小时
}

# API配置
API_CONFIG = {
    "title": "股票分析系统API",
    "description": "股票分析系统的后端API服务",
    "version": "1.0.0"
}

# CORS配置
CORS_CONFIG = {
    "allow_origins": os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"]
} 