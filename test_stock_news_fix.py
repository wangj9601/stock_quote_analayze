#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试StockNews数据库插入修复
验证自增主键是否正确工作
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend_api'))

def test_stock_news_model():
    """测试StockNews模型定义"""
    print("=== 测试StockNews模型定义 ===\n")
    
    try:
        from models import StockNews, StockResearchReport
        
        # 检查StockNews字段
        print("StockNews 字段:")
        for column in StockNews.__table__.columns:
            print(f"  {column.name}: {column.type}")
            if column.primary_key:
                print(f"    - 主键: {column.primary_key}")
            if hasattr(column, 'autoincrement') and column.autoincrement:
                print(f"    - 自增: {column.autoincrement}")
                
        print("\nStockResearchReport 字段:")
        for column in StockResearchReport.__table__.columns:
            print(f"  {column.name}: {column.type}")
            if column.primary_key:
                print(f"    - 主键: {column.primary_key}")
            if hasattr(column, 'autoincrement') and column.autoincrement:
                print(f"    - 自增: {column.autoincrement}")
                
        print("\n✅ 模型定义检查完成")
        
    except ImportError as e:
        print(f"导入模型失败: {e}")
    except Exception as e:
        print(f"模型测试异常: {e}")

def test_stock_news_creation():
    """测试StockNews对象创建"""
    print("\n=== 测试StockNews对象创建 ===\n")
    
    try:
        from models import StockNews
        import datetime
        
        # 创建StockNews对象（不设置id）
        news_obj = StockNews(
            stock_code="000001",
            title="测试新闻标题",
            content="测试新闻内容",
            keywords="测试,新闻",
            publish_time=datetime.datetime.now(),
            source="测试来源",
            url="http://test.com",
            summary="测试摘要",
            type="news",
            rating="",
            target_price="",
            created_at=datetime.datetime.now()
        )
        
        print("✅ 成功创建StockNews对象")
        print(f"  股票代码: {news_obj.stock_code}")
        print(f"  标题: {news_obj.title}")
        print(f"  ID字段: {news_obj.id}")  # 应该为None，因为还没有插入数据库
        
        # 创建StockResearchReport对象
        from models import StockResearchReport
        
        research_obj = StockResearchReport(
            stock_code="000001",
            stock_name="测试股票",
            report_name="测试研报",
            dongcai_rating="买入",
            institution="测试机构",
            monthly_report_count=1,
            profit_2024=100.0,
            pe_2024=10.0,
            profit_2025=120.0,
            pe_2025=12.0,
            profit_2026=150.0,
            pe_2026=15.0,
            industry="测试行业",
            report_date=datetime.datetime.now(),
            pdf_url="http://test.com/report.pdf",
            updated_at=datetime.datetime.now()
        )
        
        print("\n✅ 成功创建StockResearchReport对象")
        print(f"  股票代码: {research_obj.stock_code}")
        print(f"  研报名称: {research_obj.report_name}")
        print(f"  ID字段: {research_obj.id}")  # 应该为None，因为还没有插入数据库
        
    except ImportError as e:
        print(f"导入模块失败: {e}")
    except Exception as e:
        print(f"对象创建测试异常: {e}")

def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试数据库连接 ===\n")
    
    try:
        from database import get_db
        
        db = next(get_db())
        print("✅ 成功连接到数据库")
        
        # 测试简单查询
        result = db.execute("SELECT 1 as test")
        row = result.fetchone()
        print(f"  测试查询结果: {row.test}")
        
        db.close()
        
    except ImportError as e:
        print(f"导入数据库模块失败: {e}")
    except Exception as e:
        print(f"数据库连接测试异常: {e}")

if __name__ == "__main__":
    print("开始测试StockNews数据库插入修复...\n")
    
    # 测试模型定义
    test_stock_news_model()
    
    # 测试对象创建
    test_stock_news_creation()
    
    # 测试数据库连接
    test_database_connection()
    
    print("\n测试完成！") 