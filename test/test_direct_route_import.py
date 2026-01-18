#!/usr/bin/env python3
"""
直接测试路由导入和函数调用
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_route_import():
    """测试路由导入"""
    try:
        from backend_api.admin.pvfrs_admin_routes import router
        
        print("路由导入成功")
        print(f"路由数量: {len(router.routes)}")
        
        # 查找tasks路由
        tasks_route = None
        for route in router.routes:
            if route.path == "/api/admin/pvfrs/backtest/tasks":
                tasks_route = route
                break
        
        if tasks_route:
            print("✅ 找到tasks路由")
            print(f"路径: {tasks_route.path}")
            print(f"方法: {list(tasks_route.methods)}")
            print(f"名称: {tasks_route.name}")
        else:
            print("❌ 未找到tasks路由")
            print("所有路由:")
            for i, route in enumerate(router.routes):
                print(f"  {i+1}. {route.path} - {list(route.methods) if hasattr(route, 'methods') else 'N/A'}")
        
        return tasks_route is not None
        
    except Exception as e:
        print(f"路由导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_route_import()