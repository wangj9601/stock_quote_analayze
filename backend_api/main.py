"""
FastAPI主应用
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn
import logging
from auth_routes import RequestLoggingMiddleware
#from .database import init_db
from market_routes import router as market_router

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

# 修改为绝对导入
from admin import router as admin_router
from admin.auth import router as admin_auth_router
from admin.dashboard import router as dashboard_router
from admin.quotes import router as admin_quotes_router
from admin.users import router as users_router
from admin.logs import router as logs_router
from admin.operation_logs import router as operation_logs_router
from watchlist_manage import router as watchlist_router
from user_manage import router as user_manage_router
from app_complete import router as system_router
from auth_routes import router as auth_router
from stock.stock_manage import router as stock_router
from stock.hk_stock_manage import router as hk_stock_router, router_old as hk_stock_router_old
from stock.history_api import router as history_router
from stock.stock_fund_flow import router as stock_fund_flow_router
from stock.stock_news import router as stock_news_router
from stock.data_collection_api import router as data_collection_router
from stock.stock_analysis_routes import router as stock_analysis_router
from stock.stock_screening_routes import router as stock_screening_router
from quotes_routes import router as quotes_router
from multi_period_quotes_routes import router as multi_period_quotes_router
from trading_notes_routes import router as trading_notes_router
from trading_routes import router as simtrade_router
from news_channel_routes import router as news_channel_router
from admin.indicators import router as indicator_router

# 创建FastAPI应用
app = FastAPI(
    title="股票分析系统API",
    description="股票分析系统的后端API服务",
    version="1.0.0"
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

# 注册路由
app.include_router(auth_router)  # 添加认证路由
app.include_router(admin_router)
app.include_router(admin_auth_router)  # 添加admin认证路由
app.include_router(dashboard_router)
app.include_router(admin_quotes_router)
app.include_router(users_router)
app.include_router(logs_router)
app.include_router(operation_logs_router)
app.include_router(watchlist_router)
app.include_router(user_manage_router)
app.include_router(system_router)  # 添加系统路由
app.include_router(market_router)  # 添加行情路由
app.include_router(data_collection_router)  # 添加数据采集路由
app.include_router(stock_router)
app.include_router(hk_stock_router_old)  # 添加港股行情路由（旧接口，保持原路径）
app.include_router(hk_stock_router)  # 添加港股行情路由（新接口）
app.include_router(history_router)
app.include_router(stock_fund_flow_router)
app.include_router(stock_news_router)
app.include_router(stock_analysis_router)  # 添加股票分析路由
app.include_router(stock_screening_router)  # 添加选股策略路由
app.include_router(quotes_router)
app.include_router(multi_period_quotes_router)
app.include_router(trading_notes_router)
app.include_router(simtrade_router)
app.include_router(news_channel_router)  # 添加资讯频道路由
app.include_router(indicator_router)  # 添加指标查询路由

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