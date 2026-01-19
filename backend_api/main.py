"""
FastAPI主应用
"""
print(f"Loading main.py from: {__file__}")


import sys
import os
# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

# 导入中间件
try:
    from middleware import RequestLoggingMiddleware
    print("✅ RequestLoggingMiddleware 导入成功")
except ImportError as e:
    print(f"❌ RequestLoggingMiddleware 导入失败: {e}")
    # 使用内置中间件作为备选
    class RequestLoggingMiddleware:
        async def dispatch(self, request, call_next):
            return await call_next(request)

# 导入FastAPI和其他模块
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import logging
import os
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 尝试导入关键模块
try:
    from .stock.pvfrs_frontend_routes import router as pvfrs_frontend_router
    print("✅ pvfrs_frontend_router 导入成功")
except ImportError as e:
    print(f"❌ pvfrs_frontend_router 导入失败: {e}")
    pvfrs_frontend_router = None

# 尝试导入认证路由
try:
    from .auth_routes import router as auth_router
    print("✅ auth_router 导入成功")
except ImportError as e:
    print(f"❌ auth_router 导入失败: {e}")
    auth_router = None

# 尝试导入watchlist路由
try:
    from .watchlist_manage import router as watchlist_router
    print("✅ watchlist_router 导入成功")
except ImportError as e:
    print(f"❌ watchlist_router 导入失败: {e}")
    watchlist_router = None

# 尝试导入market路由
try:
    from .market_routes import router as market_router
    print("✅ market_router 导入成功")
except ImportError as e:
    print(f"❌ market_router 导入失败: {e}")
    market_router = None

# 尝试导入stock路由
try:
    from .stock.stock_manage import router as stock_router
    print("✅ stock_router 导入成功")
except ImportError as e:
    print(f"❌ stock_router 导入失败: {e}")
    stock_router = None

# 尝试导入screening路由
try:
    from .stock.stock_screening_routes import router as screening_router
    print("✅ screening_router 导入成功")
except ImportError as e:
    print(f"❌ screening_router 导入失败: {e}")
    screening_router = None

# 尝试导入history路由
try:
    from .stock.history_api import router as history_router
    print("✅ history_router 导入成功")
except ImportError as e:
    print(f"❌ history_router 导入失败: {e}")
    history_router = None

# 尝试导入新闻路由
try:
    from .news_channel_routes import router as news_router
    print("✅ news_router 导入成功")
except ImportError as e:
    print(f"❌ news_router 导入失败: {e}")
    news_router = None

# 尝试导入数据采集路由
try:
    from .stock.data_collection_api import router as data_collection_router
    print("✅ data_collection_router 导入成功")
except ImportError as e:
    print(f"❌ data_collection_router 导入失败: {e}")
    data_collection_router = None

# 创建FastAPI应用
app = FastAPI(
    title="股票分析系统API",
    description="股票分析系统的后端API服务",
    version="1.0.2"
)

# 配置CORS - 必须在其他中间件之前添加
origins = [
    "http://localhost:3000",     # Vue 开发服务器
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://192.168.3.60:8000",  # 建议加上你的本地IP端口
    "http://192.168.3.60:5000",  # 如果有需要
    "http://192.168.31.117:8000",  # 建议加上你的本地IP端口
    "http://192.168.31.117:5000",  # 如果有需要
    "http://www.icemaplecity.com",  # 生产环境域名
    "https://www.icemaplecity.com",  # 生产环境HTTPS域名
    "http://icemaplecity.com",  # 生产环境域名（无www）
    "https://icemaplecity.com",  # 生产环境HTTPS域名（无www）
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# 添加请求日志中间件 - 在CORS之后
app.add_middleware(RequestLoggingMiddleware)

# 挂载静态文件目录
#app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")

# 注册关键路由
# 注册认证路由（必须在其他路由之前注册）
if auth_router is not None:
    app.include_router(auth_router)
    print("✅ 认证路由注册成功")
else:
    print("❌ 认证路由未注册")

# 注册watchlist路由
if watchlist_router is not None:
    app.include_router(watchlist_router)
    print("✅ watchlist路由注册成功")
else:
    print("❌ watchlist路由未注册")

# 注册market路由
if market_router is not None:
    app.include_router(market_router)
    print("✅ market路由注册成功")
else:
    print("❌ market路由未注册")

# 注册stock路由
if stock_router is not None:
    app.include_router(stock_router)
    print("✅ stock路由注册成功")
else:
    print("❌ stock路由未注册")

# 注册screening路由
if screening_router is not None:
    app.include_router(screening_router)
    print("✅ screening路由注册成功")
else:
    print("❌ screening路由未注册")

# 注册history路由
if history_router is not None:
    app.include_router(history_router)
    print("✅ history路由注册成功")
else:
    print("❌ history路由未注册")

# 注册新闻路由
if news_router is not None:
    app.include_router(news_router)
    print("✅ 新闻路由注册成功")
else:
    print("❌ 新闻路由未注册")

# 注册数据采集路由
if data_collection_router is not None:
    app.include_router(data_collection_router)
    print("✅ 数据采集路由注册成功")
else:
    print("❌ 数据采集路由未注册")

# 尝试导入admin路由
try:
    from .admin.auth import router as admin_auth_router
    print("✅ admin_auth_router 导入成功")
except ImportError as e:
    print(f"❌ admin_auth_router 导入失败: {e}")
    admin_auth_router = None

try:
    from .admin.dashboard import router as admin_dashboard_router
    print("✅ admin_dashboard_router 导入成功")
except ImportError as e:
    print(f"❌ admin_dashboard_router 导入失败: {e}")
    admin_dashboard_router = None

try:
    from .admin.indicators import router as admin_indicators_router
    print("✅ admin_indicators_router 导入成功")
    # 打印路由信息用于调试
    if admin_indicators_router:
        print(f"   - 路由前缀: {admin_indicators_router.prefix}")
        print(f"   - 路由数量: {len(admin_indicators_router.routes)}")
        # 打印所有路由路径
        for route in admin_indicators_router.routes:
            if hasattr(route, 'path'):
                print(f"   - 路由路径: {route.path}")
except ImportError as e:
    print(f"❌ admin_indicators_router 导入失败: {e}")
    import traceback
    traceback.print_exc()
    admin_indicators_router = None
except Exception as e:
    print(f"❌ admin_indicators_router 导入时发生其他错误: {e}")
    import traceback
    traceback.print_exc()
    admin_indicators_router = None

# 注册admin路由
if admin_auth_router is not None:
    app.include_router(admin_auth_router)
    print("✅ admin auth路由注册成功")

if admin_dashboard_router is not None:
    app.include_router(admin_dashboard_router)
    print("✅ admin dashboard路由注册成功")

if admin_indicators_router is not None:
    app.include_router(admin_indicators_router)
    print("✅ admin indicators路由注册成功")
else:
    print("❌ admin indicators路由未注册")

# 尝试导入PVFRS admin路由
try:
    from backend_api.admin.pvfrs_admin_routes import router as pvfrs_admin_router
    print("✅ pvfrs_admin_router 导入成功")
    # 打印路由信息用于调试
    if pvfrs_admin_router:
        print(f"   - 路由前缀: {pvfrs_admin_router.prefix}")
        print(f"   - 路由数量: {len(pvfrs_admin_router.routes)}")
        # 打印所有路由路径
        for route in pvfrs_admin_router.routes:
            if hasattr(route, 'path'):
                print(f"   - 路由路径: {route.path}")
except ImportError as e:
    print(f"❌ pvfrs_admin_router 导入失败: {e}")
    import traceback
    traceback.print_exc()
    pvfrs_admin_router = None
except Exception as e:
    print(f"❌ pvfrs_admin_router 导入时发生其他错误: {e}")
    import traceback
    traceback.print_exc()
    pvfrs_admin_router = None

# 注册PVFRS admin路由
if pvfrs_admin_router is not None:
    app.include_router(pvfrs_admin_router)
    print("✅ PVFRS admin路由注册成功")
else:
    print("❌ PVFRS admin路由未注册（导入失败）")

# 注册PVFRS前端路由
if pvfrs_frontend_router is not None:
    app.include_router(pvfrs_frontend_router)
    print("✅ PVFRS前端接口路由注册成功")
else:
    print("❌ PVFRS前端接口路由未注册")

# 根路由重定向到管理后台
@app.get("/")
async def root():
    return {"message": "Welcome to Stock Analysis System API"}

@app.get("/debug/routes")
async def list_routes():
    """列出所有注册的路由（调试用）"""
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else None
            })
    return routes

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    try:
        logger.info("正在初始化数据库...")
        #init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise

if __name__ == "__main__":
    uvicorn.run(
        "backend_api.main:app", 
        host="0.0.0.0", 
        port=5000, 
        reload=True,
        timeout_keep_alive=300,
        timeout_graceful_shutdown=300
    )