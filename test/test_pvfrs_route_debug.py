"""
PVFRS路由调试测试
用于诊断为什么PVFRS路由没有正确注册
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import requests
import logging
from fastapi.testclient import TestClient

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_import_stock_screening_routes():
    """测试导入stock_screening_routes模块"""
    try:
        from backend_api.stock.stock_screening_routes import router
        print("✅ stock_screening_routes模块导入成功")
        print(f"✅ 路由对象类型: {type(router)}")
        
        # 检查路由中的路径
        routes = []
        for route in router.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
                print(f"✅ 发现路由: {route.path}")
        
        print(f"✅ 总共发现 {len(routes)} 个路由")
        
        # 检查是否包含PVFRS路由
        pvfrs_routes = [r for r in routes if 'pvfrs' in r.lower()]
        print(f"✅ PVFRS相关路由: {pvfrs_routes}")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_import_main_app():
    """测试导入main应用"""
    try:
        from backend_api.main import app
        print("✅ main应用导入成功")
        
        # 检查应用中的路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"✅ 应用中总共有 {len(routes)} 个路由")
        
        # 查找screening相关路由
        screening_routes = [r for r in routes if 'screening' in r.lower()]
        print(f"✅ screening相关路由: {screening_routes}")
        
        # 查找pvfrs相关路由
        pvfrs_routes = [r for r in routes if 'pvfrs' in r.lower()]
        print(f"✅ PVFRS相关路由: {pvfrs_routes}")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入main应用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pvfrs_frontend_interface():
    """测试PVFRS前端接口导入"""
    try:
        from backend_core.strategies.pvfrs.frontend_interface import create_frontend_interface
        print("✅ PVFRS前端接口导入成功")
        
        # 尝试创建接口实例
        interface = create_frontend_interface()
        print(f"✅ 前端接口实例创建成功: {type(interface)}")
        
        return True
        
    except Exception as e:
        print(f"❌ PVFRS前端接口导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_route_registration_order():
    """测试路由注册顺序"""
    try:
        # 重新导入以检查导入顺序
        print("🔧 检查导入顺序...")
        
        # 1. 先导入路由模块
        from backend_api.stock import stock_screening_routes
        print("✅ 1. stock_screening_routes模块导入成功")
        
        # 2. 检查路由定义
        router = stock_screening_routes.router
        print(f"✅ 2. 路由器对象: {router}")
        
        # 3. 检查路由中的函数
        route_functions = []
        for route in router.routes:
            if hasattr(route, 'endpoint'):
                func_name = route.endpoint.__name__ if route.endpoint else 'unknown'
                route_functions.append(f"{route.path} -> {func_name}")
        
        print("✅ 3. 路由函数映射:")
        for rf in route_functions:
            print(f"   {rf}")
        
        return True
        
    except Exception as e:
        print(f"❌ 路由注册顺序检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_route_call():
    """直接测试路由函数调用"""
    try:
        from backend_api.stock.stock_screening_routes import get_pvfrs_strategy
        print("✅ PVFRS路由函数导入成功")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(get_pvfrs_strategy)
        print(f"✅ 函数签名: {sig}")
        
        return True
        
    except Exception as e:
        print(f"❌ 直接路由函数调用测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_with_test_client():
    """使用TestClient测试路由"""
    try:
        from backend_api.main import app
        client = TestClient(app)
        
        print("✅ TestClient创建成功")
        
        # 测试PVFRS路由
        response = client.get("/api/screening/pvfrs-strategy")
        print(f"✅ PVFRS路由响应状态: {response.status_code}")
        print(f"✅ PVFRS路由响应内容: {response.text[:200]}...")
        
        # 测试测试路由
        response = client.get("/api/screening/test-pvfrs")
        print(f"✅ 测试路由响应状态: {response.status_code}")
        print(f"✅ 测试路由响应内容: {response.text[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ TestClient测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 开始PVFRS路由调试...")
    print("=" * 50)
    
    print("\n1. 测试stock_screening_routes模块导入:")
    test_import_stock_screening_routes()
    
    print("\n2. 测试main应用导入:")
    test_import_main_app()
    
    print("\n3. 测试PVFRS前端接口:")
    test_pvfrs_frontend_interface()
    
    print("\n4. 测试路由注册顺序:")
    test_route_registration_order()
    
    print("\n5. 测试直接路由函数调用:")
    test_direct_route_call()
    
    print("\n6. 测试TestClient:")
    test_with_test_client()
    
    print("\n" + "=" * 50)
    print("🔧 PVFRS路由调试完成")