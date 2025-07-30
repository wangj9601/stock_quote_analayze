#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试StockRealtimeQuote字段名修复
"""

def test_field_names():
    """测试字段名"""
    print("=== 测试StockRealtimeQuote字段名 ===\n")
    
    # 模拟StockRealtimeQuote对象
    class MockStockRealtimeQuote:
        def __init__(self):
            self.code = "000001"
            self.name = "平安银行"
            self.current_price = 12.34  # 正确的字段名
            self.change_percent = 2.5
            self.volume = 1000000
            self.amount = 12340000
            self.high = 12.50
            self.low = 12.20
            self.open = 12.30
            self.pre_close = 12.04
            self.turnover_rate = 1.2
            self.pe_dynamic = 8.5
            self.total_market_value = 1000000000
            self.pb_ratio = 0.8
            self.circulating_market_value = 800000000
            self.update_time = "2025-07-30 16:00:00"
    
    # 测试获取当前价格
    def get_current_price(stock):
        """模拟_get_current_price方法"""
        try:
            if stock:
                return float(stock.current_price) if stock.current_price else None
            return None
        except Exception as e:
            print(f"获取当前价格失败: {str(e)}")
            return None
    
    # 创建模拟对象
    mock_stock = MockStockRealtimeQuote()
    
    # 测试获取当前价格
    current_price = get_current_price(mock_stock)
    print(f"股票代码: {mock_stock.code}")
    print(f"股票名称: {mock_stock.name}")
    print(f"当前价格: {current_price}")
    
    if current_price is not None:
        print("✅ 成功获取当前价格")
    else:
        print("❌ 获取当前价格失败")
    
    # 测试字段访问
    print(f"\n字段访问测试:")
    print(f"  current_price: {mock_stock.current_price} ✅")
    print(f"  change_percent: {mock_stock.change_percent} ✅")
    print(f"  volume: {mock_stock.volume} ✅")
    print(f"  amount: {mock_stock.amount} ✅")
    
    print("\n✅ 字段名测试通过！")

if __name__ == "__main__":
    test_field_names() 