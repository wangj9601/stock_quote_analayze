#配置文件
#含各个模块的配置信息

import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# 数据库目录 - 使用相对路径
DB_DIR = ROOT_DIR / 'database'
DB_DIR.mkdir(parents=True, exist_ok=True)

# Tushare配置
TUSHARE_CONFIG = {
    'token': '9701deb356e76d8d9918d797aff060ce90bd1a24339866c02444014f',
    'max_retries': 3,
    'timeout': 30
}

# 数据采集器配置
DATA_COLLECTORS = {
    'tushare': {
        'max_retries': 3,  # 最大重试次数
        'retry_delay': 5,  # 重试延迟（秒）
        'timeout': 30,     # 请求超时时间（秒）
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),  # 日志目录
        'db_file': str(DB_DIR / 'stock_analysis.db'),  # 数据库文件路径
        'max_connection_errors': 10,  # 最大连接错误次数
        'token': TUSHARE_CONFIG['token']  # Tushare token
    },
    'akshare': {
        'max_retries': 3,  # 最大重试次数
        'retry_delay': 5,  # 重试延迟（秒）
        'timeout': 30,     # 请求超时时间（秒）
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),  # 日志目录
        'db_file': str(DB_DIR / 'stock_analysis.db'),  # 数据库文件路径
        'max_connection_errors': 10,  # 最大连接错误次数
    }
}

# 创建必要的目录
for dir_path in [
    ROOT_DIR / 'backend_core' / 'logs',
    ROOT_DIR / 'backend_core' / 'data',
    ROOT_DIR / 'backend_core' / 'models'
]:
    dir_path.mkdir(parents=True, exist_ok=True)