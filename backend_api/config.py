"""
backend_api配置文件
"""

from pathlib import Path
import os


# 加载环境变量
#load_dotenv()

# # 数据库目录 - 使用相对路径
# DB_DIR = Path(__file__).parent.parent / 'database'
# DB_DIR.mkdir(parents=True, exist_ok=True)

# # 数据库文件路径
# DB_PATH = str(DB_DIR / 'stock_analysis.db')

# 数据库配置
DATABASE_CONFIG = {
    "url": "postgresql+psycopg2://postgres:qidianspacetime@192.168.31.237:5446/stock_analysis",
    "pool_size": 5,
    "max_overflow": 10,
    "echo": False
}

print("数据库连接URL字节:", DATABASE_CONFIG["url"].encode("utf-8"))

# JWT配置
JWT_CONFIG = {
    "secret_key": "your-secret-key-here",
    "algorithm": "HS256",
    "access_token_expire_minutes": 1440  # 24小时
}

# API配置
API_CONFIG = {
    "title": "股票分析系统API",
    "description": "股票分析系统的后端API服务",
    "version": "1.0.0"
}

# CORS配置
CORS_CONFIG = {
    "allow_origins": ["*"],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"]
} 