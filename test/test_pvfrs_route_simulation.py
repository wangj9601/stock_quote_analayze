"""
模拟PVFRS路由测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime

def test_pvfrs_route_simulation():
    """测试模拟的PVFRS路由"""
    
    print("开始测试PVFRS路由模拟...")
    
    # 测试PVFRS前端接口导入
    try:
        from backend_core.strategies.pvfrs.frontend_interface import create_frontend_interface
        print("✅ PVFRS前端接口导入成功")
        PVFRS_AVAILABLE = True
    except Exception as e:
        print(f"❌ PVFRS前端接口导入失败: {e}")
        PVFRS_AVAILABLE = False
        return False
    
    # 创建路由器
    router = APIRouter(prefix="/api/screening", tags=["screening"])
    
    @router.get("/pvfrs-strategy")
    async def get_pvfrs_strategy(
        date: str = Query(None, description="目标日期，格式：YYYY-MM-DD，不提供则使用当前日期"),
        limit: int = Query(50, ge=1, le=100, description="最大返回结果数量，默认50"),
        min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值，默认0.3")
    ):
        """模拟的PVFRS策略路由"""
        print(f"🔧 DEBUG: 模拟PVFRS路由被调用 - 日期: {date}, 限制: {limit}, 最低强度: {min_strength}")
        
        # 检查PVFRS是否可用
        if not PVFRS_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PVFRS策略暂时不可用，请稍后重试"
            )
        
        try:
            # 参数验证
            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="日期格式错误，应为 YYYY-MM-DD"
                    )
            
            # 创建前端接口实例
            frontend_interface = create_frontend_interface()
            print("✅ PVFRS前端接口创建成功")
            
            # 设置选股配置
            frontend_interface.set_selection_config(max_results=limit, min_strength=min_strength)
            print("✅ PVFRS选股配置设置成功")
            
            # 获取选股结果
            selection_results = frontend_interface.get_selection_results(date)
            print(f"✅ PVFRS选股结果获取成功，找到 {len(selection_results)} 只股票")
            
            # 转换为API响应格式
            results_data = []
            for result in selection_results:
                result_dict = result.to_dict()
                results_data.append(result_dict)
            
            return JSONResponse({
                "success": True,
                "data": results_data,
                "total": len(results_data),
                "search_date": date or datetime.now().strftime("%Y-%m-%d"),
                "strategy_name": "PVFRS量价频三维共振演化策略",
                "parameters": {
                    "limit": limit,
                    "min_strength": min_strength
                }
            })
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            print(f"❌ PVFRS策略执行失败: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PVFRS策略选股执行失败: {str(e)}"
            )
    
    # 创建FastAPI应用并注册路由
    app = FastAPI()
    app.include_router(router)
    
    # 检查路由是否被注册
    routes = [route.path for route in app.routes]
    print(f"注册的路由: {routes}")
    
    if "/api/screening/pvfrs-strategy" in routes:
        print("✅ 模拟PVFRS路由注册成功")
        return True
    else:
        print("❌ 模拟PVFRS路由注册失败")
        return False

if __name__ == "__main__":
    success = test_pvfrs_route_simulation()
    if success:
        print("✅ PVFRS路由模拟测试通过")
    else:
        print("❌ PVFRS路由模拟测试失败")