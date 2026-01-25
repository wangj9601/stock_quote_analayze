#!/usr/bin/env python3
"""检查股票报价路由"""
import requests

def check_quote_routes():
    """检查股票报价路由是否正确注册"""
    
    print("🔍 检查股票报价路由")
    print("="*50)
    
    try:
        # 获取所有路由
        response = requests.get('http://localhost:5000/debug/routes', timeout=5)
        
        if response.status_code == 200:
            routes = response.json()
            
            # 查找包含quote的路由
            quote_routes = []
            for route in routes:
                if 'quote' in str(route).lower():
                    quote_routes.append(route)
            
            print(f"找到 {len(quote_routes)} 个包含'quote'的路由:")
            for i, route in enumerate(quote_routes, 1):
                print(f"{i}. {route}")
            
            # 检查POST /api/stock/quote路由
            target_route = None
            for route in routes:
                if (isinstance(route, dict) and 
                    route.get('path') == '/api/stock/quote' and 
                    'POST' in str(route.get('methods', []))):
                    target_route = route
                    break
            
            if target_route:
                print(f"\n✅ 找到目标路由: {target_route}")
            else:
                print(f"\n❌ 未找到 POST /api/stock/quote 路由")
                
        else:
            print(f"❌ 获取路由失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 检查路由时出错: {e}")

if __name__ == "__main__":
    check_quote_routes()
