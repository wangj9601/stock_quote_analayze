#!/usr/bin/env python3
"""测试股票分析路由导入"""
import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend_api'))

try:
    from stock.stock_analysis_routes import router
    print("✅ 导入成功")
    print(f"路由前缀: {router.prefix}")
    print(f"路由数量: {len(router.routes)}")
    for route in router.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.path}")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
