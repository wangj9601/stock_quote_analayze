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
# Gemini AI API Key
GEMINI_API_KEY = "AIzaSyDhgCArPllwqHBfwRBNjDreqI3l8r0gyxY0"

# SMTP邮件配置
SMTP_CONFIG = {
    "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "port": int(os.getenv("SMTP_PORT", "587")),
    "username": os.getenv("SMTP_USERNAME", ""),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    "from_email": os.getenv("SMTP_FROM_EMAIL", ""),
    "from_name": os.getenv("SMTP_FROM_NAME", "股票分析系统")
}

# 推送配置
PUSH_CONFIG = {
    "max_retry_count": int(os.getenv("MAX_RETRY_COUNT", "3")),
    "push_batch_size": int(os.getenv("PUSH_BATCH_SIZE", "100")),
    "report_dir": os.getenv("REPORT_DIR", "./reports"),  # 报告文件存储目录
    "default_push_times": ["09:30", "15:30"]  # 默认推送时间
}

# 微信配置
WECHAT_CONFIG = {
    "corp_id": os.getenv("WECHAT_CORP_ID", ""),  # 企业微信Corp ID
    "agent_id": os.getenv("WECHAT_AGENT_ID", ""),  # 企业微信Agent ID
    "secret": os.getenv("WECHAT_SECRET", ""),  # 企业微信Secret
    "token": os.getenv("WECHAT_TOKEN", ""),  # 微信公众号Token
    "encoding_aes_key": os.getenv("WECHAT_ENCODING_AES_KEY", "")  # 微信公众号EncodingAESKey
}
