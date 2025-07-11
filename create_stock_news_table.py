#!/usr/bin/env python3
"""
创建股票新闻公告表的数据库迁移脚本（SQLAlchemy+PostgreSQL 版）
"""
from backend_api.database import init_db
from backend_api.models import StockNews

def create_stock_news_table():
    """
创建股票新闻公告表（如未存在则自动建表）
"""
    try:
        # 直接用SQLAlchemy自动建表
        init_db()
        print("✅ 成功创建股票新闻公告表及索引（如未存在）")
        return True
    except Exception as e:
        print(f"❌ 创建股票新闻公告表失败: {e}")
        return False

if __name__ == "__main__":
    print("开始创建股票新闻公告表...")
    if create_stock_news_table():
        print("✅ 数据库表创建完成")
    else:
        print("❌ 数据库表创建失败")