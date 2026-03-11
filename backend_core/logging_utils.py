# -*- coding: utf-8 -*-
"""
日志工具：是否写文件的开关由 .env 的 LOG_TO_FILE 控制。
"""
import os


def should_log_to_file() -> bool:
    """
    是否将日志写入文件。由环境变量 LOG_TO_FILE 控制。
    为 true/yes/1（不区分大小写）时返回 True，否则仅控制台。
    """
    return os.getenv('LOG_TO_FILE', 'false').strip().lower() in ('1', 'true', 'yes')
