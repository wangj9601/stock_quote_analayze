"""
FastAPI主应用
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import logging
from .auth_routes import RequestLoggingMiddleware
#from .database import init_db
from .market_routes import router as market_router

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

# 修改为相对导入
from .admin import router as admin_router
from .admin.dashboard import router as dashboard_router
from .admin.quotes import router as quotes_router
from .admin.users import router as users_router
from .watchlist_manage import router as watchlist_router
from .user_manage import router as user_manage_router
from .app_complete import router as system_router
from .auth_routes import router as auth_router
from .stock.stock_manage import router as stock_router
from .stock.history_api import router as history_router
from .stock.stock_fund_flow import router as stock_fund_flow_router
from .stock.stock_news import router as stock_news_router
from .stock.stock_analysis_routes import router as stock_analysis_router

# 创建FastAPI应用
app = FastAPI(
    title="股票分析系统API",
    description="股票分析系统的后端API服务",
    version="1.0.0"
)

# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 配置CORS
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://192.168.3.60:8000",  # 建议加上你的本地IP端口
    "http://192.168.3.60:5000",  # 如果有需要
    "*",  # 允许所有来源
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# 挂载静态文件目录
app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")

# 注册路由
app.include_router(auth_router)  # 添加认证路由
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(quotes_router)
app.include_router(users_router)
app.include_router(watchlist_router)
app.include_router(user_manage_router)
app.include_router(system_router)  # 添加系统路由
app.include_router(market_router)  # 添加行情路由
app.include_router(stock_analysis_router)  # 添加智能分析路由
app.include_router(stock_router)
app.include_router(history_router)
app.include_router(stock_fund_flow_router)
app.include_router(stock_news_router)

# 根路由重定向到管理后台
@app.get("/")
async def root():
    return {"message": "Welcome to Stock Analysis System API"}

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
    uvicorn.run("backend_api.main:app", host="0.0.0.0", port=5000, reload=True) 