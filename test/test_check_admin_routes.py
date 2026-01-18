#!/usr/bin/env python3
"""
检查管理后台路由注册情况
"""

import requests
import json

def check_admin_routes():
    """检查管理后台相关路由"""
    try:
        response = requests.get("http://localhost:5000/debug/routes")
        if response.status_code == 200:
            routes = response.json()
            
            print("管理后台PVFRS相关路由:")
            print("=" * 50)
            
            admin_pvfrs_routes = []
            for route in routes:
                path = route.get("path", "")
                methods = route.get("methods", [])
                
                if "/api/admin/pvfrs" in path:
                    admin_pvfrs_routes.append(route)
                    print(f"✅ {path} - {methods}")
            
            print(f"\n找到 {len(admin_pvfrs_routes)} 个管理后台PVFRS路由")
            
            # 检查特定路由
            target_route = "/api/admin/pvfrs/backtest/tasks"
            found = any(route['path'] == target_route for route in routes)
            status = "✅ 已注册" if found else "❌ 未注册"
            print(f"\n目标路由检查:")
            print(f"{target_route}: {status}")
            
            if not found:
                print("\n所有包含 'tasks' 的路由:")
                for route in routes:
                    if 'tasks' in route.get('path', ''):
                        print(f"  {route['path']} - {route.get('methods', [])}")
                
        else:
            print(f"获取路由信息失败: {response.status_code}")
            
    except Exception as e:
        print(f"检查路由时发生错误: {str(e)}")

if __name__ == "__main__":
    check_admin_routes()