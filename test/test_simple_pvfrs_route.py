"""
简单的PVFRS路由测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse

def test_simple_pvfrs_route():
    """测试简单的PVFRS路由"""
    
    # 创建一个简单的路由器
    router = APIRouter(prefix="/api/screening", tags=["screening"])
    
    @router.get("/pvfrs-strategy")
    async def simple_pvfrs_strategy():
        """简单的PVFRS策略路由"""
        return JSONResponse({
            "success": True,
            "message": "PVFRS路由工作正常",
            "data": []
        })
    
    # 创建FastAPI应用并注册路由
    app = FastAPI()
    app.include_router(router)
    
    # 检查路由是否被注册
    routes = [route.path for route in app.routes]
    print(f"注册的路由: {routes}")
    
    if "/api/screening/pvfrs-strategy" in routes:
        print("✅ 简单PVFRS路由注册成功")
        return True
    else:
        print("❌ 简单PVFRS路由注册失败")
        return False

if __name__ == "__main__":
    print("开始测试简单PVFRS路由...")
    success = test_simple_pvfrs_route()
    if success:
        print("✅ 简单PVFRS路由测试通过")
    else:
        print("❌ 简单PVFRS路由测试失败")