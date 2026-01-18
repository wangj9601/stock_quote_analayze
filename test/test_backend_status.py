"""
检查后端服务实际状态
"""

import requests
import sys
import os

def check_backend_status():
    """检查后端服务状态"""
    base_url = "http://localhost:5000"
    
    print("🔍 检查后端服务实际状态")
    print("=" * 50)
    
    # 1. 检查基本连通性
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ 后端服务连通性: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 后端服务无法连接 - 服务可能未启动")
        return False
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        return False
    
    # 2. 检查已知工作的路由
    working_routes = [
        "/api/frontend/pvfrs/monitor",
        "/api/frontend/pvfrs/selection-results"
    ]
    
    print("\n📋 检查已知工作的路由:")
    for route in working_routes:
        try:
            response = requests.get(f"{base_url}{route}", timeout=5)
            status = f"✅ {response.status_code}" if response.status_code != 404 else f"❌ 404"
            print(f"   {route}: {status}")
        except Exception as e:
            print(f"   {route}: ❌ 错误 - {e}")
    
    # 3. 检查问题路由
    problem_routes = [
        ("GET", "/api/frontend/pvfrs/system/status"),
        ("POST", "/api/frontend/pvfrs/backtest")
    ]
    
    print("\n📋 检查问题路由:")
    for method, route in problem_routes:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{route}", timeout=5)
            else:
                response = requests.post(f"{base_url}{route}", json={}, timeout=5)
            
            status = f"✅ {response.status_code}" if response.status_code != 404 else f"❌ 404"
            print(f"   {method} {route}: {status}")
            
            if response.status_code == 404:
                print(f"      响应内容: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   {method} {route}: ❌ 错误 - {e}")
    
    # 4. 检查路由列表（如果有debug端点）
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print(f"\n✅ FastAPI文档可访问: {base_url}/docs")
            print("   建议在浏览器中查看 http://localhost:5000/docs 来确认路由列表")
        else:
            print(f"\n❌ FastAPI文档不可访问: {response.status_code}")
    except:
        print("\n❌ 无法访问FastAPI文档")
    
    return True

def check_route_registration():
    """检查路由注册情况"""
    print("\n🔍 检查路由注册情况")
    print("=" * 30)
    
    try:
        # 检查主应用导入
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from backend_api.main import app
        
        # 获取所有路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                methods = list(route.methods) if hasattr(route, 'methods') else ['Unknown']
                routes.append((route.path, methods))
        
        print(f"✅ 主应用共有 {len(routes)} 个路由")
        
        # 查找PVFRS相关路由
        pvfrs_routes = [r for r in routes if 'pvfrs' in r[0].lower()]
        print(f"✅ PVFRS相关路由: {len(pvfrs_routes)} 个")
        
        # 检查关键路由
        key_routes = [
            "/api/frontend/pvfrs/system/status",
            "/api/frontend/pvfrs/backtest"
        ]
        
        for key_route in key_routes:
            found = any(key_route in route[0] for route in routes)
            print(f"   {'✅' if found else '❌'} {key_route}")
        
        return True
        
    except Exception as e:
        print(f"❌ 检查路由注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 开始后端服务状态检查...")
    
    # 检查服务状态
    service_ok = check_backend_status()
    
    if service_ok:
        # 检查路由注册
        routes_ok = check_route_registration()
        
        if not routes_ok:
            print("\n💡 建议:")
            print("   1. 检查后端启动日志是否有错误")
            print("   2. 确认PVFRS路由模块是否正确导入")
            print("   3. 检查main.py中的路由注册代码")
    
    print("\n" + "=" * 50)
    print("检查完成")