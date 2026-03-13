# 配置文件：含各个模块的配置信息，优先从项目根目录 .env 读取（有 python-dotenv 时）

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # 生产环境可无 python-dotenv，依赖系统环境变量

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env")

def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()

def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

# 数据库目录 - 使用相对路径
DB_DIR = ROOT_DIR / 'database'
DB_DIR.mkdir(parents=True, exist_ok=True)

# Tushare 配置（从 .env 读取，未设置则用默认）
TUSHARE_CONFIG = {
    'token': _env('TUSHARE_TOKEN', ''),
    'max_retries': _env_int('TUSHARE_MAX_RETRIES', 3),
    'timeout': _env_int('TUSHARE_TIMEOUT', 30),
}

# 数据采集器配置
DATA_COLLECTORS = {
    'tushare': {
        'max_retries': _env_int('TUSHARE_MAX_RETRIES', 3),
        'retry_delay': _env_int('TUSHARE_RETRY_DELAY', 5),
        'timeout': _env_int('TUSHARE_TIMEOUT', 30),
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),
        'db_file': str(DB_DIR / 'stock_analysis.db'),
        'max_connection_errors': _env_int('TUSHARE_MAX_CONNECTION_ERRORS', 10),
        'token': TUSHARE_CONFIG['token'],
    },
    'akshare': {
        'max_retries': _env_int('AKSHARE_MAX_RETRIES', 3),
        'retry_delay': _env_int('AKSHARE_RETRY_DELAY', 5),
        'timeout': _env_int('AKSHARE_TIMEOUT', 30),
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),
        'db_file': str(DB_DIR / 'stock_analysis.db'),
        'max_connection_errors': _env_int('AKSHARE_MAX_CONNECTION_ERRORS', 10),
        'proxy_pool': [],
        'random_delay_range': (1, 3),
        'ssl_verify': os.getenv('AKSHARE_SSL_VERIFY', 'false').lower() in ('true', '1', 'yes'),
        'use_fallback_sources': os.getenv('AKSHARE_USE_FALLBACK_SOURCES', 'true').lower() in ('true', '1', 'yes'),
    }
}

# 创建必要的目录
for dir_path in [
    ROOT_DIR / 'backend_core' / 'logs',
    ROOT_DIR / 'backend_core' / 'data',
    ROOT_DIR / 'backend_core' / 'models'
]:
    dir_path.mkdir(parents=True, exist_ok=True)