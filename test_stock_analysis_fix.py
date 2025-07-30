#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试StockAnalysisService修复
验证_get_current_price方法是否正常工作
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend_api'))

def test_stock_analysis_service():
    """测试StockAnalysisService"""
    print("=== 测试StockAnalysisService修复 ===\n")
    
    try:
        from stock.stock_analysis import StockAnalysisService
        from database import get_db
        
        # 创建服务实例
        service = StockAnalysisService()
        
        # 测试获取当前价格
        test_stocks = ["000001", "000002", "600000"]
        
        for stock_code in test_stocks:
            print(f"测试股票: {stock_code}")
            
            try:
                # 测试获取当前价格
                current_price = service._get_current_price(stock_code)
                print(f"  当前价格: {current_price}")
                
                if current_price is not None:
                    print(f"  ✅ 成功获取价格: {current_price}")
                else:
                    print(f"  ⚠️  未找到价格数据")
                    
            except Exception as e:
                print(f"  ❌ 获取价格失败: {e}")
                
            print()
            
        # 测试完整分析
        print("测试完整股票分析...")
        for stock_code in test_stocks[:1]:  # 只测试第一个
            try:
                result = service.get_stock_analysis(stock_code)
                
                if "error" in result:
                    print(f"❌ 分析失败: {result['error']}")
                else:
                    print(f"✅ 分析成功")
                    data = result['data']
                    
                    # 验证关键价位
                    key_levels = data.get('key_levels', {})
                    current_price = data.get('current_price', 0)
                    
                    print(f"  当前价格: {current_price}")
                    print(f"  支撑位: {key_levels.get('support_levels', [])}")
                    print(f"  阻力位: {key_levels.get('resistance_levels', [])}")
                    
                    # 验证支撑位严格小于当前价格
                    support_levels = key_levels.get('support_levels', [])
                    support_valid = all(level < current_price for level in support_levels)
                    print(f"  支撑位验证: {'✅ 通过' if support_valid else '❌ 失败'}")
                    
                    # 验证阻力位严格大于当前价格
                    resistance_levels = key_levels.get('resistance_levels', [])
                    resistance_valid = all(level > current_price for level in resistance_levels)
                    print(f"  阻力位验证: {'✅ 通过' if resistance_valid else '❌ 失败'}")
                    
            except Exception as e:
                print(f"❌ 完整分析失败: {e}")
                
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保在正确的目录下运行此脚本")
    except Exception as e:
        print(f"测试异常: {e}")

def test_models():
    """测试模型定义"""
    print("\n=== 测试模型定义 ===\n")
    
    try:
        from models import StockRealtimeQuote, IndustryBoardRealtimeQuotes
        
        # 检查StockRealtimeQuote字段
        print("StockRealtimeQuote 字段:")
        for column in StockRealtimeQuote.__table__.columns:
            print(f"  {column.name}: {column.type}")
            
        # 检查IndustryBoardRealtimeQuotes字段
        print("\nIndustryBoardRealtimeQuotes 字段:")
        for column in IndustryBoardRealtimeQuotes.__table__.columns:
            print(f"  {column.name}: {column.type}")
            
        print("\n✅ 模型定义检查完成")
        
    except ImportError as e:
        print(f"导入模型失败: {e}")
    except Exception as e:
        print(f"模型测试异常: {e}")

if __name__ == "__main__":
    print("开始测试StockAnalysisService修复...\n")
    
    # 测试模型定义
    test_models()
    
    # 测试服务功能
    test_stock_analysis_service()
    
    print("\n测试完成！") 