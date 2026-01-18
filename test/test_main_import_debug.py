"""
调试main.py导入过程
逐步导入每个模块，找出问题所在
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_step_by_step_import():
    """逐步导入main.py中的模块"""
    print("🔧 开始逐步导入main.py中的模块...")
    
    try:
        print("\n1. 导入基础模块...")
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        print("✅ FastAPI基础模块导入成功")
        
        print("\n2. 导入stock_screening_routes...")
        from backend_api.stock.stock_screening_routes import router as stock_screening_router
        print("✅ stock_screening_routes导入成功")
        print(f"✅ 路由对象: {stock_screening_router}")
        
        # 检查路由
        routes = []
        for route in stock_screening_router.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        print(f"✅ 路由中包含的路径: {routes}")
        
        print("\n3. 创建应用并注册路由...")
        app = FastAPI()
        app.include_router(stock_screening_router)
        print("✅ 路由注册成功")
        
        # 检查应用中的路由
        app_routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                app_routes.append(route.path)
        
        screening_routes = [r for r in app_routes if 'screening' in r]
        pvfrs_routes = [r for r in app_routes if 'pvfrs' in r.lower()]
        
        print(f"✅ 应用中的screening路由: {screening_routes}")
        print(f"✅ 应用中的PVFRS路由: {pvfrs_routes}")
        
        return len(pvfrs_routes) > 0
        
    except Exception as e:
        print(f"❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_import_all_routers():
    """测试导入所有路由器"""
    print("\n🔧 测试导入所有路由器...")
    
    routers = []
    
    try:
        print("导入 stock_screening_router...")
        from backend_api.stock.stock_screening_routes import router as stock_screening_router
        routers.append(('stock_screening', stock_screening_router))
        print("✅ stock_screening_router 导入成功")
    except Exception as e:
        print(f"❌ stock_screening_router 导入失败: {e}")
    
    try:
        print("导入 auth_router...")
        from backend_api.auth_routes import router as auth_router
        routers.append(('auth', auth_router))
        print("✅ auth_router 导入成功")
    except Exception as e:
        print(f"❌ auth_router 导入失败: {e}")
    
    try:
        print("导入 admin_router...")
        from backend_api.admin import router as admin_router
        routers.append(('admin', admin_router))
        print("✅ admin_router 导入成功")
    except Exception as e:
        print(f"❌ admin_router 导入失败: {e}")
    
    # 创建应用并注册所有成功导入的路由
    try:
        from fastapi import FastAPI
        app = FastAPI()
        
        for name, router in routers:
            try:
                app.include_router(router)
                print(f"✅ {name} 路由注册成功")
            except Exception as e:
                print(f"❌ {name} 路由注册失败: {e}")
        
        # 检查最终的路由
        all_routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                all_routes.append(route.path)
        
        screening_routes = [r for r in all_routes if 'screening' in r]
        pvfrs_routes = [r for r in all_routes if 'pvfrs' in r.lower()]
        
        print(f"\n✅ 最终应用中的screening路由: {screening_routes}")
        print(f"✅ 最终应用中的PVFRS路由: {pvfrs_routes}")
        
        return len(pvfrs_routes) > 0
        
    except Exception as e:
        print(f"❌ 创建应用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_compare_with_running_server():
    """与运行中的服务器进行对比"""
    print("\n🔧 与运行中的服务器进行对比...")
    
    try:
        import requests
        
        # 获取服务器的路由
        response = requests.get("http://localhost:5000/openapi.json", timeout=5)
        if response.status_code == 200:
            openapi_data = response.json()
            server_paths = list(openapi_data.get('paths', {}).keys())
            server_screening = [p for p in server_paths if 'screening' in p]
            server_pvfrs = [p for p in server_paths if 'pvfrs' in p.lower()]
            
            print(f"✅ 服务器screening路由: {server_screening}")
            print(f"✅ 服务器PVFRS路由: {server_pvfrs}")
            
            # 检查是否缺少PVFRS选股路由
            expected_pvfrs_screening = ['/api/screening/pvfrs-strategy', '/api/screening/test-pvfrs']
            missing_routes = [r for r in expected_pvfrs_screening if r not in server_paths]
            
            if missing_routes:
                print(f"❌ 服务器缺少的PVFRS选股路由: {missing_routes}")
                return False
            else:
                print("✅ 服务器包含所有预期的PVFRS选股路由")
                return True
        else:
            print(f"❌ 无法获取服务器路由信息: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 服务器对比失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 开始调试main.py导入过程...")
    print("=" * 60)
    
    result1 = test_step_by_step_import()
    result2 = test_import_all_routers()
    result3 = test_compare_with_running_server()
    
    print("\n" + "=" * 60)
    print("🔧 调试总结:")
    print(f"   逐步导入测试: {'✅ 通过' if result1 else '❌ 失败'}")
    print(f"   所有路由导入测试: {'✅ 通过' if result2 else '❌ 失败'}")
    print(f"   服务器对比测试: {'✅ 通过' if result3 else '❌ 失败'}")
    
    if result1 and result2 and not result3:
        print("\n💡 结论: 路由定义和导入都正常，但服务器上缺少PVFRS选股路由")
        print("💡 建议: 检查服务器启动过程中是否有导入异常被忽略")