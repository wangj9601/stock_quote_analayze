# -*- coding: utf-8 -*-
"""
日志工具：是否写文件的开关由 .env 的 LOG_TO_FILE 控制；
默认写项目根 logs/；生产可设 LOGS_DIR=/opt/stock_quote/shared/logs（跨 release 保留）。
"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（backend_core 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


def should_log_to_file() -> bool:
    """
    是否将日志写入文件。由环境变量 LOG_TO_FILE 控制。
    为 true/yes/1（不区分大小写）时返回 True，否则仅控制台。
    """
    return os.getenv("LOG_TO_FILE", "false").strip().lower() in ("1", "true", "yes")


def get_logs_dir() -> Path:
    """返回日志目录（LOGS_DIR 环境变量优先），不存在则创建。"""
    override = (os.getenv("LOGS_DIR") or "").strip()
    target = Path(override).expanduser() if override else LOGS_DIR
    try:
        target.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # release 目录偶发属主不对时，退回 shared/logs（若在标准部署树下）
        shared = PROJECT_ROOT.parent / "shared" / "logs"
        if shared != target:
            shared.mkdir(parents=True, exist_ok=True)
            return shared
        raise
    return target


def resolve_log_file(filename: str) -> Path:
    """
    将日志文件名解析为项目根 logs/ 下的绝对路径，并确保目录存在。
    若传入已是绝对路径/含子目录，则仅保证父目录存在后原样使用 basename 写入 logs/。
    """
    name = Path(filename).name
    path = get_logs_dir() / name
    return path
