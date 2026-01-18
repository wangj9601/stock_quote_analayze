"""
简化的PVFRS路由测试
只测试路由本身，不依赖完整的应用启动
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_pvfrs_route_isolated():
    """独立测试PVFRS路由"""
    try:
        # 直接导入路由模块
        from backend_api.stock.stock_screening_routes import router, get_pvfrs_strategy
        print("✅ PVFRS路由模块导入成功")
        
        # 检查路由注册
        pvfrs_routes = []
        for route in router.routes:
            if hasattr(route, 'path') and 'pvfrs' in route.path.lower():
                pvfrs_routes.append({
                    'path': route.path,
                    'methods': getattr(route, 'methods', []),
                    'endpoint': route.endpoint.__name__ if hasattr(route, 'endpoint') and route.endpoint else 'unknown'
                })
        
        print(f"✅ 找到 {len(pvfrs_routes)} 个PVFRS路由:")
        for route in pvfrs_routes:
            print(f"   {route['methods']} {route['path']} -> {route['endpoint']}")
        
        # 检查函数是否可调用
        import inspect
        sig = inspect.signature(get_pvfrs_strategy)
        print(f"✅ get_pvfrs_strategy函数签名: {sig}")
        
        return len(pvfrs_routes) > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_create_minimal_app():
    """创建最小化应用来测试路由"""
    try:
        from fastapi import FastAPI
        from backend_api.stock.stock_screening_routes import router
        
        # 创建最小化应用
        app = FastAPI()
        app.include_router(router)
        
        print("✅ 最小化应用创建成功")
        
        # 检查应用中的路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        pvfrs_routes = [r for r in routes if 'pvfrs' in r.lower()]
        print(f"✅ 应用中的PVFRS路由: {pvfrs_routes}")
        
        return len(pvfrs_routes) > 0
        
    except Exception as e:
        print(f"❌ 最小化应用测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_with_mock_dependencies():
    """使用模拟依赖测试路由"""
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend_api.stock.stock_screening_routes import router, get_pvfrs_strategy
        
        # 创建应用
        app = FastAPI()
        app.include_router(router)
        
        # 模拟数据库依赖
        def mock_get_db():
            return None
        
        # 覆盖依赖
        from backend_api.stock.stock_screening_routes import get_db
        app.dependency_overrides[get_db] = mock_get_db
        
        # 创建测试客户端
        client = TestClient(app)
        
        print("✅ 测试客户端创建成功")
        
        # 测试PVFRS路由
        response = client.get("/api/screening/test-pvfrs")
        print(f"✅ 测试路由响应: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ 响应内容: {response.json()}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ 模拟依赖测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 开始简化PVFRS路由测试...")
    print("=" * 50)
    
    print("\n1. 独立路由测试:")
    result1 = test_pvfrs_route_isolated()
    
    print("\n2. 最小化应用测试:")
    result2 = test_create_minimal_app()
    
    print("\n3. 模拟依赖测试:")
    result3 = test_with_mock_dependencies()
    
    print("\n" + "=" * 50)
    if all([result1, result2, result3]):
        print("🎉 所有测试通过！PVFRS路由工作正常！")
    else:
        print("❌ 部分测试失败，需要进一步调试")