#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库初始化和迁移脚本

该脚本用于运行数据库迁移，创建或更新推送系统所需的数据库表。

使用方法:
    python init_db.py [选项]

选项:
    --migration-dir PATH  迁移脚本目录 (默认: migrations)
    --dry-run            仅显示将要执行的操作，不实际执行
    --force              强制执行迁移，即使已经执行过
    --rollback           回滚最后一次迁移
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.logging_utils import resolve_log_file
from backend_core.database.db import get_db_session, engine
from backend_api.models import Base, User, UserPushConfig, PushRecord
from sqlalchemy import inspect, text


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(resolve_log_file('init_db.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )


def check_table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_tables(dry_run: bool = False):
    """创建所有表"""
    logger = logging.getLogger(__name__)
    
    if dry_run:
        logger.info("【模拟模式】将要创建以下表:")
        for table_name, table in Base.metadata.tables.items():
            if not check_table_exists(table_name):
                logger.info(f"  - {table_name}")
        return
    
    logger.info("开始创建数据库表...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    logger.info("数据库表创建完成")
    
    # 显示创建的表
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"当前数据库中的表: {', '.join(tables)}")


def run_migration(migration_file: str, dry_run: bool = False):
    """运行单个迁移脚本"""
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(migration_file):
        logger.error(f"迁移文件不存在: {migration_file}")
        return False
    
    logger.info(f"运行迁移: {migration_file}")
    
    if dry_run:
        logger.info("【模拟模式】将要执行迁移脚本")
        return True
    
    try:
        # 执行迁移脚本
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_code = f.read()
        
        # 创建执行环境
        exec_globals = {
            'engine': engine,
            'get_db_session': get_db_session,
            'Base': Base,
            'User': User,
            'UserPushConfig': UserPushConfig,
            'PushRecord': PushRecord,
        }
        
        exec(migration_code, exec_globals)
        
        logger.info(f"迁移完成: {migration_file}")
        return True
        
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        return False


def run_all_migrations(migration_dir: str, dry_run: bool = False, force: bool = False):
    """运行所有迁移脚本"""
    logger = logging.getLogger(__name__)
    
    migration_path = Path(migration_dir)
    if not migration_path.exists():
        logger.error(f"迁移目录不存在: {migration_dir}")
        return False
    
    # 获取所有迁移文件
    migration_files = sorted(migration_path.glob("*.py"))
    
    if not migration_files:
        logger.warning(f"在 {migration_dir} 中没有找到迁移文件")
        return True
    
    logger.info(f"找到 {len(migration_files)} 个迁移文件")
    
    success_count = 0
    for migration_file in migration_files:
        if migration_file.name.startswith('__'):
            continue
        
        if run_migration(str(migration_file), dry_run):
            success_count += 1
    
    logger.info(f"完成 {success_count}/{len(migration_files)} 个迁移")
    return success_count == len(migration_files)


def verify_tables():
    """验证表结构"""
    logger = logging.getLogger(__name__)
    
    logger.info("验证数据库表结构...")
    
    required_tables = {
        'users': ['id', 'username', 'email', 'wechat_openid', 'wechat_type'],
        'user_push_configs': ['id', 'user_id', 'enabled', 'channels', 'push_times', 'report_type'],
        'push_records': ['id', 'user_id', 'push_date', 'push_time', 'status', 'channel_status']
    }
    
    inspector = inspect(engine)
    
    all_valid = True
    for table_name, required_columns in required_tables.items():
        if not check_table_exists(table_name):
            logger.error(f"表不存在: {table_name}")
            all_valid = False
            continue
        
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        missing_columns = set(required_columns) - set(columns)
        
        if missing_columns:
            logger.error(f"表 {table_name} 缺少列: {', '.join(missing_columns)}")
            all_valid = False
        else:
            logger.info(f"✓ 表 {table_name} 结构正确")
    
    return all_valid


def show_status():
    """显示数据库状态"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("数据库状态")
    logger.info("=" * 60)
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    logger.info(f"数据库中的表数量: {len(tables)}")
    
    for table_name in sorted(tables):
        columns = inspector.get_columns(table_name)
        logger.info(f"\n表: {table_name}")
        logger.info(f"  列数: {len(columns)}")
        logger.info(f"  列: {', '.join([col['name'] for col in columns])}")
    
    logger.info("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据库初始化和迁移')
    parser.add_argument('--migration-dir', type=str, default='migrations',
                       help='迁移脚本目录')
    parser.add_argument('--dry-run', action='store_true',
                       help='仅显示将要执行的操作，不实际执行')
    parser.add_argument('--force', action='store_true',
                       help='强制执行迁移，即使已经执行过')
    parser.add_argument('--rollback', action='store_true',
                       help='回滚最后一次迁移')
    parser.add_argument('--status', action='store_true',
                       help='显示数据库状态')
    parser.add_argument('--verify', action='store_true',
                       help='验证表结构')
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("数据库初始化和迁移工具")
    logger.info("=" * 60)
    
    try:
        if args.status:
            # 显示状态
            show_status()
        elif args.verify:
            # 验证表结构
            if verify_tables():
                logger.info("✓ 所有表结构验证通过")
            else:
                logger.error("✗ 表结构验证失败")
                sys.exit(1)
        elif args.rollback:
            # 回滚迁移
            logger.warning("回滚功能尚未实现")
            sys.exit(1)
        else:
            # 创建表
            create_tables(dry_run=args.dry_run)
            
            # 运行迁移
            if run_all_migrations(args.migration_dir, dry_run=args.dry_run, force=args.force):
                logger.info("✓ 数据库迁移完成")
                
                # 验证表结构
                if not args.dry_run:
                    if verify_tables():
                        logger.info("✓ 表结构验证通过")
                    else:
                        logger.warning("⚠ 表结构验证失败，请检查")
            else:
                logger.error("✗ 数据库迁移失败")
                sys.exit(1)
        
        logger.info("=" * 60)
        logger.info("操作完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
