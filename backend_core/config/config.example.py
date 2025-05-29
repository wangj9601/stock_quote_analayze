"""
配置文件示例
复制此文件为config.py并修改相应的配置项
"""

import os
from pathlib import Path

# 基础路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
LOG_DIR = BASE_DIR / 'logs'
MODEL_DIR = BASE_DIR / 'models' / 'saved_models'

# 数据库配置
DATABASE = {
    'sqlite': {
        'path': str(DATA_DIR / 'stock_analysis.db'),
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
    },
    'mongodb': {
        'uri': 'mongodb://localhost:27017',
        'db': 'stock_analysis',
    }
}

# 数据采集配置
DATA_COLLECTORS = {
    'akshare': {
        'timeout': 30,
        'retry_times': 3,
        'retry_delay': 5,
    },
    'tushare': {
        'token': 'your_tushare_token',
        'timeout': 30,
        'retry_times': 3,
    },
    'sina': {
        'timeout': 10,
        'retry_times': 3,
        'retry_delay': 2,
    }
}

# 分析配置
ANALYZERS = {
    'technical': {
        'indicators': [
            'MA', 'MACD', 'KDJ', 'RSI', 'BOLL',
            'ATR', 'CCI', 'DMI', 'OBV', 'VOL'
        ],
        'default_periods': {
            'short': 5,
            'medium': 20,
            'long': 60
        }
    },
    'fundamental': {
        'update_interval': 24,  # 小时
        'indicators': [
            'PE', 'PB', 'ROE', 'ROA', 'EPS',
            'Revenue', 'Profit', 'Debt'
        ]
    },
    'sentiment': {
        'update_interval': 1,  # 小时
        'sources': [
            'news',
            'social_media',
            'market_sentiment'
        ]
    }
}

# 模型配置
MODELS = {
    'ml': {
        'features': [
            'technical_indicators',
            'fundamental_indicators',
            'sentiment_indicators'
        ],
        'target': 'price_change',
        'train_test_split': 0.8,
        'validation_split': 0.1,
        'random_state': 42
    },
    'dl': {
        'batch_size': 32,
        'epochs': 100,
        'early_stopping_patience': 10,
        'learning_rate': 0.001,
        'gpu_memory_fraction': 0.8
    }
}

# 任务调度配置
CELERY = {
    'broker_url': 'redis://localhost:6379/1',
    'result_backend': 'redis://localhost:6379/2',
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'Asia/Shanghai',
    'enable_utc': True,
    'task_routes': {
        'data_collectors.*': {'queue': 'data_collectors'},
        'analyzers.*': {'queue': 'analyzers'},
        'models.*': {'queue': 'models'}
    }
}

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'app.log'),
            'formatter': 'standard',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'level': 'INFO',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

# 创建必要的目录
for directory in [DATA_DIR, LOG_DIR, MODEL_DIR]:
    directory.mkdir(parents=True, exist_ok=True) 