#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动推送调度器脚本

该脚本用于启动每日报告推送的定时调度器。
调度器会在配置的时间点自动触发推送任务。

使用方法:
    python start_scheduler.py [选项]

选项:
    --config-file PATH    指定配置文件路径 (默认: backend_api/config.py)
    --push-times TIMES    指定推送时间点，逗号分隔 (默认: 09:30,15:30)
    --log-level LEVEL     日志级别 (DEBUG, INFO, WARNING, ERROR) (默认: INFO)
    --daemon              以守护进程模式运行
    --pid-file PATH       PID文件路径 (默认: scheduler.pid)
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

from backend_api.config import PUSH_CONFIG, WECHAT_CONFIG, SMTP_CONFIG
from backend_core.scheduler.push_scheduler import PushScheduler
from backend_api.services.push_service import PushService
from backend_api.services.email_service import EmailService
from backend_api.services.config_service import ConfigService
from backend_api.services.report_service import ReportService
from backend_api.services.record_repository import RecordRepository
from backend_core.wechat.wechat_service import WeChatService
from backend_core.database.db import get_db_session


def setup_logging(log_level: str):
    """配置日志"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scheduler.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def create_push_service():
    """创建推送服务实例"""
    # 创建数据库会话
    db_session = get_db_session()
    
    # 创建各个服务实例
    wechat_service = WeChatService(
        corp_id=WECHAT_CONFIG.get("corp_id"),
        agent_id=WECHAT_CONFIG.get("agent_id"),
        secret=WECHAT_CONFIG.get("secret")
    )
    
    email_service = EmailService(smtp_config=SMTP_CONFIG)
    
    config_service = ConfigService(db_session=db_session)
    
    report_service = ReportService(
        db_session=db_session,
        report_dir=PUSH_CONFIG.get("report_dir", "./reports")
    )
    
    record_repository = RecordRepository(db_session=db_session)
    
    # 创建推送服务
    push_service = PushService(
        wechat_service=wechat_service,
        email_service=email_service,
        report_service=report_service,
        config_service=config_service,
        record_repository=record_repository
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
        
        # 创建调度器
        logger.info("正在创建调度器...")
        scheduler = PushScheduler(push_service=push_service)
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, scheduler, args.pid_file))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, scheduler, args.pid_file))
        
        # 添加推送任务
        for push_time in push_times:
            logger.info(f"添加推送任务: {push_time}")
            scheduler.add_push_job(push_time)
        
        # 启动调度器
        logger.info("正在启动调度器...")
        scheduler.start()
        logger.info("调度器已启动，按Ctrl+C停止")
        
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
