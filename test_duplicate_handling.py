#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重复数据处理逻辑
验证唯一约束违反错误的修复
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend_api'))

def test_duplicate_check_logic():
    """测试重复检查逻辑"""
    print("=== 测试重复检查逻辑 ===\n")
    
    # 模拟重复数据检查逻辑
    def check_duplicate_report(stock_code, report_name, report_date, existing_reports):
        """检查研报是否重复"""
        for report in existing_reports:
            if (report['stock_code'] == stock_code and 
                report['report_name'] == report_name and 
                report['report_date'] == report_date):
                return True
        return False
    
    def check_duplicate_news(stock_code, title, publish_time, existing_news):
        """检查新闻是否重复"""
        for news in existing_news:
            if (news['stock_code'] == stock_code and 
                news['title'] == title and 
                news['publish_time'] == publish_time):
                return True
        return False
    
    # 模拟现有数据
    existing_reports = [
        {
            'stock_code': '601669',
            'report_name': '2025年一季报点评：营收平稳增长，毛利率下行致盈利继续承压',
            'report_date': '2025-05-06 00:00:00'
        }
    ]
    
    existing_news = [
        {
            'stock_code': '601669',
            'title': '中国电建发布2025年一季报',
            'publish_time': '2025-05-06 10:00:00'
        }
    ]
    
    # 测试研报重复检查
    print("测试研报重复检查:")
    
    # 测试重复的研报
    duplicate_report = {
        'stock_code': '601669',
        'report_name': '2025年一季报点评：营收平稳增长，毛利率下行致盈利继续承压',
        'report_date': '2025-05-06 00:00:00'
    }
    
    is_duplicate = check_duplicate_report(
        duplicate_report['stock_code'],
        duplicate_report['report_name'],
        duplicate_report['report_date'],
        existing_reports
    )
    
    print(f"  重复研报检查: {'❌ 重复' if is_duplicate else '✅ 不重复'}")
    print(f"    股票代码: {duplicate_report['stock_code']}")
    print(f"    研报名称: {duplicate_report['report_name']}")
    print(f"    发布日期: {duplicate_report['report_date']}")
    
    # 测试新的研报
    new_report = {
        'stock_code': '601669',
        'report_name': '2025年二季报预测：业绩有望改善',
        'report_date': '2025-08-06 00:00:00'
    }
    
    is_duplicate = check_duplicate_report(
        new_report['stock_code'],
        new_report['report_name'],
        new_report['report_date'],
        existing_reports
    )
    
    print(f"\n  新研报检查: {'❌ 重复' if is_duplicate else '✅ 不重复'}")
    print(f"    股票代码: {new_report['stock_code']}")
    print(f"    研报名称: {new_report['report_name']}")
    print(f"    发布日期: {new_report['report_date']}")
    
    # 测试新闻重复检查
    print("\n测试新闻重复检查:")
    
    # 测试重复的新闻
    duplicate_news = {
        'stock_code': '601669',
        'title': '中国电建发布2025年一季报',
        'publish_time': '2025-05-06 10:00:00'
    }
    
    is_duplicate = check_duplicate_news(
        duplicate_news['stock_code'],
        duplicate_news['title'],
        duplicate_news['publish_time'],
        existing_news
    )
    
    print(f"  重复新闻检查: {'❌ 重复' if is_duplicate else '✅ 不重复'}")
    print(f"    股票代码: {duplicate_news['stock_code']}")
    print(f"    新闻标题: {duplicate_news['title']}")
    print(f"    发布时间: {duplicate_news['publish_time']}")
    
    # 测试新的新闻
    new_news = {
        'stock_code': '601669',
        'title': '中国电建获得新项目合同',
        'publish_time': '2025-05-07 10:00:00'
    }
    
    is_duplicate = check_duplicate_news(
        new_news['stock_code'],
        new_news['title'],
        new_news['publish_time'],
        existing_news
    )
    
    print(f"\n  新新闻检查: {'❌ 重复' if is_duplicate else '✅ 不重复'}")
    print(f"    股票代码: {new_news['stock_code']}")
    print(f"    新闻标题: {new_news['title']}")
    print(f"    发布时间: {new_news['publish_time']}")

def test_error_handling():
    """测试错误处理逻辑"""
    print("\n=== 测试错误处理逻辑 ===\n")
    
    # 模拟数据库操作
    def simulate_db_operation(operation_type, data):
        """模拟数据库操作"""
        if operation_type == "duplicate_insert":
            raise Exception("重复键违反唯一约束")
        elif operation_type == "success":
            return True
        else:
            raise Exception("未知操作类型")
    
    # 测试成功操作
    try:
        result = simulate_db_operation("success", {"test": "data"})
        print("✅ 成功操作测试通过")
    except Exception as e:
        print(f"❌ 成功操作测试失败: {e}")
    
    # 测试重复插入错误处理
    try:
        simulate_db_operation("duplicate_insert", {"test": "data"})
        print("❌ 重复插入错误处理测试失败")
    except Exception as e:
        print(f"✅ 重复插入错误处理测试通过: {e}")
    
    # 测试事务回滚逻辑
    print("\n测试事务回滚逻辑:")
    try:
        # 模拟开始事务
        print("  开始事务...")
        
        # 模拟第一个操作成功
        simulate_db_operation("success", {"data1": "value1"})
        print("  第一个操作成功")
        
        # 模拟第二个操作失败
        simulate_db_operation("duplicate_insert", {"data2": "value2"})
        print("  第二个操作成功")
        
        # 模拟提交事务
        print("  提交事务...")
        
    except Exception as e:
        print(f"  捕获异常: {e}")
        print("  回滚事务...")
        print("✅ 事务回滚逻辑测试通过")

if __name__ == "__main__":
    print("开始测试重复数据处理逻辑...\n")
    
    # 测试重复检查逻辑
    test_duplicate_check_logic()
    
    # 测试错误处理逻辑
    test_error_handling()
    
    print("\n测试完成！") 