#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成测试数据脚本

该脚本用于生成推送系统的测试数据，包括测试用户、推送配置、自选股等。

使用方法:
    python generate_test_data.py [选项]

选项:
    --users N            生成N个测试用户 (默认: 5)
    --stocks N           每个用户生成N只自选股 (默认: 10)
    --clean              清除现有测试数据
    --seed N             随机种子 (默认: 42)
"""

import sys
import os
import argparse
import logging
import random
from pathlib import Path
from datetime import datetime, date, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend_core.database.db import get_db_session
from backend_api.models import User, UserPushConfig, PushRecord, Watchlist
from sqlalchemy import delete


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def clean_test_data(db_session):
    """清除测试数据"""
    logger = logging.getLogger(__name__)
    
    logger.info("清除测试数据...")
    
    # 删除测试用户的推送记录
    db_session.execute(
        delete(PushRecord).where(
            PushRecord.user_id.in_(
                db_session.query(User.id).filter(User.username.like('test_user_%'))
            )
        )
    )
    
    # 删除测试用户的推送配置
    db_session.execute(
        delete(UserPushConfig).where(
            UserPushConfig.user_id.in_(
                db_session.query(User.id).filter(User.username.like('test_user_%'))
            )
        )
    )
    
    # 删除测试用户的自选股
    db_session.execute(
        delete(Watchlist).where(
            Watchlist.user_id.in_(
                db_session.query(User.id).filter(User.username.like('test_user_%'))
            )
        )
    )
    
    # 删除测试用户
    db_session.execute(
        delete(User).where(User.username.like('test_user_%'))
    )
    
    db_session.commit()
    logger.info("测试数据已清除")


def generate_users(db_session, count: int):
    """生成测试用户"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"生成 {count} 个测试用户...")
    
    users = []
    for i in range(1, count + 1):
        user = User(
            username=f"test_user_{i}",
            email=f"test_user_{i}@example.com",
            password_hash="test_password_hash",
            wechat_openid=f"test_openid_{i}" if i % 2 == 0 else None,
            wechat_type="personal" if i % 2 == 0 else None,
            role="user",
            status="active",
            created_at=datetime.now()
        )
        db_session.add(user)
        users.append(user)
    
    db_session.commit()
    logger.info(f"✓ 已生成 {count} 个测试用户")
    
    return users


def generate_push_configs(db_session, users):
    """生成推送配置"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"为 {len(users)} 个用户生成推送配置...")
    
    channels_options = [
        ["wechat"],
        ["email"],
        ["wechat", "email"]
    ]
    
    push_times_options = [
        ["09:30"],
        ["15:30"],
        ["09:30", "15:30"],
        ["08:00", "12:00", "16:00"]
    ]
    
    report_types = ["summary", "detailed"]
    
    for user in users:
        config = UserPushConfig(
            user_id=user.id,
            enabled=random.choice([True, True, True, False]),  # 75%启用
            channels=random.choice(channels_options),
            push_times=random.choice(push_times_options),
            report_type=random.choice(report_types),
            stock_codes=None,  # None表示全部自选股
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db_session.add(config)
    
    db_session.commit()
    logger.info(f"✓ 已生成 {len(users)} 个推送配置")


def generate_watchlists(db_session, users, stocks_per_user: int):
    """生成自选股"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"为每个用户生成 {stocks_per_user} 只自选股...")
    
    # A股股票代码示例
    a_stocks = [
        ("000001", "平安银行"),
        ("000002", "万科A"),
        ("000333", "美的集团"),
        ("000651", "格力电器"),
        ("000858", "五粮液"),
        ("600000", "浦发银行"),
        ("600036", "招商银行"),
        ("600519", "贵州茅台"),
        ("600887", "伊利股份"),
        ("601318", "中国平安"),
    ]
    
    # 港股股票代码示例
    hk_stocks = [
        ("00700", "腾讯控股"),
        ("00941", "中国移动"),
        ("01299", "友邦保险"),
        ("02318", "中国平安"),
        ("03690", "美团-W"),
    ]
    
    all_stocks = a_stocks + hk_stocks
    
    for user in users:
        # 随机选择股票
        selected_stocks = random.sample(all_stocks, min(stocks_per_user, len(all_stocks)))
        
        for stock_code, stock_name in selected_stocks:
            watchlist = Watchlist(
                user_id=user.id,
                stock_code=stock_code,
                stock_name=stock_name,
                group_name="默认分组",
                created_at=datetime.now()
            )
            db_session.add(watchlist)
    
    db_session.commit()
    logger.info(f"✓ 已为 {len(users)} 个用户生成自选股")


def generate_push_records(db_session, users):
    """生成推送记录"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"为 {len(users)} 个用户生成历史推送记录...")
    
    statuses = ["success", "failed", "partial_success"]
    push_times = ["09:30", "15:30"]
    
    # 生成最近7天的推送记录
    for user in users:
        for days_ago in range(7):
            push_date = date.today() - timedelta(days=days_ago)
            
            for push_time in push_times:
                # 随机决定是否有这个时间点的推送记录
                if random.random() < 0.8:  # 80%概率有记录
                    status = random.choice(statuses)
                    
                    # 根据状态生成渠道状态
                    if status == "success":
                        channel_status = {"wechat": "success", "email": "success"}
                    elif status == "failed":
                        channel_status = {"wechat": "failed", "email": "failed"}
                    else:  # partial_success
                        channel_status = {"wechat": "success", "email": "failed"}
                    
                    record = PushRecord(
                        user_id=user.id,
                        push_date=push_date,
                        push_time=push_time,
                        report_type=random.choice(["summary", "detailed"]),
                        channel_status=channel_status,
                        status=status,
                        report_file_path=f"./reports/user_{user.id}_{push_date}_{push_time}.csv",
                        error_messages={"wechat": None, "email": "SMTP connection failed"} if status != "success" else None,
                        retry_count=random.randint(0, 2) if status == "failed" else 0,
                        max_retries=3,
                        created_at=datetime.combine(push_date, datetime.strptime(push_time, "%H:%M").time()),
                        started_at=datetime.combine(push_date, datetime.strptime(push_time, "%H:%M").time()),
                        completed_at=datetime.combine(push_date, datetime.strptime(push_time, "%H:%M").time()) + timedelta(seconds=random.randint(5, 30))
                    )
                    db_session.add(record)
    
    db_session.commit()
    logger.info(f"✓ 已生成历史推送记录")


def show_summary(db_session):
    """显示数据摘要"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("测试数据摘要")
    logger.info("=" * 60)
    
    user_count = db_session.query(User).filter(User.username.like('test_user_%')).count()
    config_count = db_session.query(UserPushConfig).join(User).filter(User.username.like('test_user_%')).count()
    watchlist_count = db_session.query(Watchlist).join(User).filter(User.username.like('test_user_%')).count()
    record_count = db_session.query(PushRecord).join(User).filter(User.username.like('test_user_%')).count()
    
    logger.info(f"测试用户数: {user_count}")
    logger.info(f"推送配置数: {config_count}")
    logger.info(f"自选股数: {watchlist_count}")
    logger.info(f"推送记录数: {record_count}")
    
    # 显示启用推送的用户
    enabled_count = db_session.query(UserPushConfig).join(User).filter(
        User.username.like('test_user_%'),
        UserPushConfig.enabled == True
    ).count()
    logger.info(f"启用推送的用户: {enabled_count}/{user_count}")
    
    logger.info("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成测试数据')
    parser.add_argument('--users', type=int, default=5,
                       help='生成的测试用户数量')
    parser.add_argument('--stocks', type=int, default=10,
                       help='每个用户的自选股数量')
    parser.add_argument('--clean', action='store_true',
                       help='清除现有测试数据')
    parser.add_argument('--seed', type=int, default=42,
                       help='随机种子')
    parser.add_argument('--no-records', action='store_true',
                       help='不生成推送记录')
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 设置随机种子
    random.seed(args.seed)
    
    logger.info("=" * 60)
    logger.info("测试数据生成工具")
    logger.info("=" * 60)
    
    try:
        # 获取数据库会话
        db_session = get_db_session()
        
        # 清除现有测试数据
        if args.clean:
            clean_test_data(db_session)
        
        # 生成测试用户
        users = generate_users(db_session, args.users)
        
        # 生成推送配置
        generate_push_configs(db_session, users)
        
        # 生成自选股
        generate_watchlists(db_session, users, args.stocks)
        
        # 生成推送记录
        if not args.no_records:
            generate_push_records(db_session, users)
        
        # 显示摘要
        show_summary(db_session)
        
        logger.info("=" * 60)
        logger.info("✓ 测试数据生成完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"生成失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
