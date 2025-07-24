#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    from stock.stock_analysis_routes import router
    print("✓ stock_analysis_routes 导入成功")
except Exception as e:
    print(f"✗ stock_analysis_routes 导入失败: {e}")

try:
    from stock.stock_analysis import StockAnalysisService
    print("✓ stock_analysis 导入成功")
except Exception as e:
    print(f"✗ stock_analysis 导入失败: {e}")

try:
    from main import app
    print("✓ main app 导入成功")
except Exception as e:
    print(f"✗ main app 导入失败: {e}")

print("导入测试完成") 