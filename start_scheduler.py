#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动推送调度器脚本 (PushScheduler)

在配置的时间点自动执行邮件/微信报告推送（从 user_push_configs 读取用户配置）。

启动方式（在项目根目录执行）:
    python start_scheduler.py

可选参数:
    --push-times TIMES    推送时间点，逗号分隔 (默认: 09:30,15:30)
    --log-level LEVEL     日志级别 (默认: INFO)
    --daemon              守护进程模式
    --pid-file PATH       PID 文件路径 (默认: scheduler.pid)
"""

import sys
import os
import argparse
import logging
import signal
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.logging_utils import resolve_log_file


def _reconfigure_stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for _stream in (sys.stdout, sys.stderr):
        _fn = getattr(_stream, "reconfigure", None)
        if callable(_fn):
            try:
                _fn(encoding="utf-8", errors="replace")
            except Exception:
                pass


_reconfigure_stdio_utf8()

from timestamp_stdio import install_timestamp_prefix_stdio

install_timestamp_prefix_stdio()

from backend_api.config import PUSH_CONFIG, SMTP_CONFIG
from backend_api.services.email_service import EmailService, SMTPConfig
from backend_core.scheduler.push_scheduler import PushScheduler
from backend_api.services.push_service import PushService
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_core.database.db import SessionLocal


def _env_bool(name: str, default: bool = False) -> bool:
    """解析环境变量布尔值。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    """解析环境变量整数值，非法值时回退默认值。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = int(str(raw).strip())
        return val if val > 0 else default
    except Exception:
        return default


def _get_smtp_config(db):
    """从数据库或环境变量获取发件配置（与 push_routes 逻辑一致）"""
    try:
        from backend_api.models import EmailSenderConfig
        row = db.query(EmailSenderConfig).filter(EmailSenderConfig.id == 1).first()
        if row and row.host and row.username:
            return SMTPConfig(
                host=str(row.host),
                port=int(row.port),
                username=str(row.username),
                password=str(row.password) if row.password else "",
                use_tls=bool(row.use_tls),
                from_email=str(row.from_email) if row.from_email else str(row.username),
                from_name=str(row.from_name) if row.from_name else "股票分析系统",
            )
    except Exception as e:
        logging.warning(f"从数据库读取发件配置失败，将使用环境变量: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception as rb_e:
            logging.warning(f"rollback 失败: {rb_e}")
    return SMTPConfig(
        host=SMTP_CONFIG["host"],
        port=SMTP_CONFIG["port"],
        username=SMTP_CONFIG["username"],
        password=SMTP_CONFIG["password"],
        use_tls=SMTP_CONFIG["use_tls"],
        from_email=SMTP_CONFIG["from_email"],
        from_name=SMTP_CONFIG["from_name"],
    )


def setup_logging(log_level: str):
    """配置日志"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    # stdout 已由 timestamp_stdio 加行首时间戳；此处不再重复 %(asctime)s
    logging.basicConfig(
        level=numeric_level,
        format='%(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(resolve_log_file('scheduler.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )


def create_push_service():
    """创建推送服务实例（使用与 API 一致的 DB 会话与发件配置）"""
    db = SessionLocal()
    smtp_config = _get_smtp_config(db)
    email_service = EmailService(smtp_config)
    wechat_service = WeChatService()
    config_service = ConfigService(db)
    report_service = ReportService(db, report_dir=PUSH_CONFIG.get("report_dir", "./reports"))
    record_repository = RecordRepository(db)
    push_service = PushService(
        wechat_service=wechat_service,
        email_service=email_service,
        report_service=report_service,
        config_service=config_service,
        record_repository=record_repository,
    )
    return push_service


def write_pid_file(pid_file: str):
    """写入PID文件"""
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))


def remove_pid_file(pid_file: str):
    """删除PID文件"""
    if os.path.exists(pid_file):
        os.remove(pid_file)


def signal_handler(signum, frame, scheduler, pid_file):
    """信号处理器"""
    logging.info(f"接收到信号 {signum}，正在停止调度器...")
    scheduler.stop()
    remove_pid_file(pid_file)
    logging.info("调度器已停止")
    sys.exit(0)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='启动推送调度器')
    parser.add_argument('--config-file', type=str, help='配置文件路径')
    parser.add_argument('--push-times', type=str, help='推送时间点，逗号分隔 (例如: 09:30,15:30)')
    parser.add_argument('--log-level', type=str, default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别')
    parser.add_argument('--daemon', action='store_true', help='以守护进程模式运行')
    parser.add_argument('--pid-file', type=str, default='scheduler.pid', help='PID文件路径')
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # 获取推送时间点
    if args.push_times:
        push_times = [t.strip() for t in args.push_times.split(',')]
    else:
        push_times = PUSH_CONFIG.get("default_push_times", ["09:30", "15:30"])
    
    logger.info(f"推送时间点: {push_times}")
    
    # 以守护进程模式运行
    if args.daemon:
        try:
            pid = os.fork()
            if pid > 0:
                # 父进程退出
                sys.exit(0)
        except OSError as e:
            logger.error(f"Fork失败: {e}")
            sys.exit(1)
        
        # 子进程继续
        os.setsid()
        os.umask(0)
    
    # 写入PID文件
    write_pid_file(args.pid_file)
    logger.info(f"PID文件已写入: {args.pid_file}")
    
    try:
        # 创建推送服务
        logger.info("正在初始化推送服务...")
        push_service = create_push_service()
        
        # 创建调度器（default_push_times 会在 start() 时自动添加）
        logger.info("正在创建调度器...")
        # 周末推送开关（默认关闭）：ENABLE_WEEKEND_PUSH=true 可启用周六/周日推送
        enable_weekend_push = _env_bool("ENABLE_WEEKEND_PUSH", False)
        logger.info("周末推送开关 ENABLE_WEEKEND_PUSH=%s", enable_weekend_push)
        refresh_interval_minutes = _env_int("PUSH_CONFIG_REFRESH_INTERVAL_MINUTES", 5)
        logger.info(
            "推送配置刷新间隔 PUSH_CONFIG_REFRESH_INTERVAL_MINUTES=%s 分钟",
            refresh_interval_minutes,
        )
        scheduler = PushScheduler(
            push_service=push_service,
            default_push_times=push_times,
            enable_weekend_push=enable_weekend_push,
            refresh_interval_minutes=refresh_interval_minutes,
        )
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, scheduler, args.pid_file))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, scheduler, args.pid_file))
        
        # 启动调度器（内部会按 default_push_times 添加定时任务）
        logger.info("正在启动调度器...")
        scheduler.start()
        logger.info("调度器已启动，按 Ctrl+C 停止")
        
        # 保持运行
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止...")
        scheduler.stop()
        remove_pid_file(args.pid_file)
        logger.info("调度器已停止")
    except Exception as e:
        logger.error(f"调度器运行出错: {e}", exc_info=True)
        remove_pid_file(args.pid_file)
        sys.exit(1)


if __name__ == "__main__":
    main()
