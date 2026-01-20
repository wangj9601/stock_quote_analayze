"""
增强版主应用入口
集成PVFRS策略管理重构后的API路由
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from contextlib import asynccontextmanager

from backend_api.database import engine
from backend_api.models.pvfrs_enhanced import Base as PVFRSEnhancedBase
from backend_api.admin.pvfrs_admin_routes_enhanced import router as pvfrs_admin_router
from backend_api.stock.stock_screening_routes import router as stock_screening_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在启动PVFRS策略管理增强版API...")
    
    try:
        # 创建PVFRS增强表
        PVFRSEnhancedBase.metadata.create_all(bind=engine)
        logger.info("✅ PVFRS增强数据库表创建完成")
        
        # 运行数据库迁移
        from backend_api.migrations.pvfrs_refactor_migration import main as migrate_main
        try:
            migrate_main()
            logger.info("✅ PVFRS数据库迁移完成")
        except Exception as e:
            logger.warning(f"⚠️ 数据库迁移失败，但不影响正常启动: {str(e)}")
        
        logger.info("🚀 PVFRS策略管理增强版API启动完成")
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {str(e)}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("正在关闭PVFRS策略管理增强版API...")

# 创建FastAPI应用
app = FastAPI(
    title="PVFRS策略管理增强版API",
    description="PVFRS量价频三维共振演化策略管理系统 - 重构版本",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求处理时间中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加请求处理时间头"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 注册路由
app.include_router(pvfrs_admin_router)
app.include_router(stock_screening_router)

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "PVFRS策略管理增强版API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "admin": "/api/admin/pvfrs",
        "screening": "/api/screening"
    }

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0"
    }

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "内部服务器错误",
            "detail": str(exc)
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )
