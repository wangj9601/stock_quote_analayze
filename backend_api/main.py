"""
FastAPI 主应用
"""
print(f"Loading main.py from: {__file__}")


import sys
import os
# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

# 在导入任何路由之前：猴子补丁 JSONResponse.render，将 nan/inf 转为 null，避免 ValueError: Out of range float values are not JSON compliant
# 直接补丁原始类的方法，这样无论 FastAPI/Starlette 用哪份 JSONResponse 引用都会生效
import json
import math

def _sanitize_for_json(obj):
    """递归将 nan/inf 与 numpy 标量转为 JSON 可序列化值。"""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if hasattr(obj, 'item'):  # numpy 标量
        try:
            return _sanitize_for_json(obj.item())
        except (ValueError, AttributeError, TypeError):
            return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj

import starlette.responses
_original_json_render = starlette.responses.JSONResponse.render

def _patched_json_render(self, content):
    content = _sanitize_for_json(content)
    return _original_json_render(self, content)

starlette.responses.JSONResponse.render = _patched_json_render
# FastAPI 的 JSONResponse 即 starlette 的，补丁一次即可
try:
    import fastapi.responses
    fastapi.responses.JSONResponse.render = _patched_json_render
except Exception:
    pass

# 导入中间件（优先包内路径，避免仅能在 backend_api 目录下启动时才能 import middleware）
try:
    from backend_api.middleware import RequestLoggingMiddleware
    print("RequestLoggingMiddleware 导入成功 (backend_api.middleware)")
except ImportError:
    try:
        from middleware import RequestLoggingMiddleware
        print("RequestLoggingMiddleware 导入成功 (legacy middleware)")
    except ImportError as e:
        print(f"RequestLoggingMiddleware 导入失败: {e}")
        from starlette.middleware.base import BaseHTTPMiddleware

        class RequestLoggingMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await call_next(request)

# 导入 FastAPI 和其它模块
from typing import Optional

from fastapi import FastAPI, Request, Response, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import asyncio
import re
import uvicorn
import logging
import os
import sys
from sqlalchemy.orm import Session

from backend_api.database import get_db

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
    print("pvfrs_frontend_router 导入成功")
except ImportError as e:
    print(f"pvfrs_frontend_router 导入失败: {e}")
    pvfrs_frontend_router = None

try:
    from .stock.gms_frontend_routes import router as gms_frontend_router
    print("gms_frontend_router 导入成功")
except ImportError as e:
    print(f"gms_frontend_router 导入失败: {e}")
    gms_frontend_router = None

# 尝试导入认证路由
try:
    from .auth_routes import router as auth_router
    print("auth_router 导入成功")
except ImportError as e:
    print(f"auth_router 导入失败: {e}")
    auth_router = None

# 尝试导入watchlist路由
try:
    from .watchlist_manage import router as watchlist_router
    print("watchlist_router 导入成功")
except ImportError as e:
    print(f"watchlist_router 导入失败: {e}")
    watchlist_router = None

# 尝试导入market路由
try:
    from .market_routes import router as market_router
    print("market_router 导入成功")
except ImportError as e:
    print(f"market_router 导入失败: {e}")
    market_router = None

# 尝试导入stock路由
try:
    from .stock.stock_manage import router as stock_router
    print("stock_router 导入成功")
except ImportError as e:
    print(f"stock_router 导入失败: {e}")
    stock_router = None

try:
    from .triple_volume_observe_routes import router as triple_volume_observe_router, admin_router as triple_volume_observe_admin_router
    print("triple_volume_observe_router 导入成功")
except ImportError as e:
    print(f"triple_volume_observe_router 导入失败: {e}")
    triple_volume_observe_router = None
    triple_volume_observe_admin_router = None

try:
    from .vsb_observe_stocks_routes import router as vsb_observe_stocks_router
    print("vsb_observe_stocks_router 导入成功")
except ImportError as e:
    print(f"vsb_observe_stocks_router 导入失败: {e}")
    vsb_observe_stocks_router = None

try:
    from .gms_trade_observe_routes import router as gms_trade_observe_router
    print("gms_trade_observe_router 导入成功")
except ImportError as e:
    print(f"gms_trade_observe_router 导入失败: {e}")
    gms_trade_observe_router = None

try:
    from .gms_formal_trade_routes import router as gms_formal_trade_router
    print("gms_formal_trade_router 导入成功")
except ImportError as e:
    print(f"gms_formal_trade_router 导入失败: {e}")
    gms_formal_trade_router = None

try:
    from .gms_user_preferences_routes import router as gms_user_preferences_router
    print("gms_user_preferences_router 导入成功")
except ImportError as e:
    print(f"gms_user_preferences_router 导入失败: {e}")
    gms_user_preferences_router = None

try:
    from .triple_volume_trade_observe_routes import router as triple_volume_trade_observe_router
    print("triple_volume_trade_observe_router 导入成功")
except ImportError as e:
    print(f"triple_volume_trade_observe_router 导入失败: {e}")
    triple_volume_trade_observe_router = None

# 尝试导入screening路由
try:
    from .stock.stock_screening_routes import router as screening_router
    print("screening_router 导入成功")
except ImportError as e:
    print(f"screening_router 导入失败: {e}")
    screening_router = None

# 尝试导入 GMS 信号追溯路由
try:
    from .stock.gms_trace_routes import router as gms_trace_router
    print("gms_trace_router 导入成功")
except ImportError as e:
    print(f"gms_trace_router 导入失败: {e}")
    gms_trace_router = None

try:
    from .stock.vsb_signal_routes import router as vsb_signal_router
    print("vsb_signal_router 导入成功")
except ImportError as e:
    print(f"vsb_signal_router 导入失败: {e}")
    vsb_signal_router = None

# 尝试导入history路由
try:
    from .stock.history_api import router as history_router
    print("history_router 导入成功")
except ImportError as e:
    print(f"history_router 导入失败: {e}")
    history_router = None

# 尝试导入新闻路由
try:
    from .news_channel_routes import router as news_router
    print("news_router 导入成功")
except ImportError as e:
    print(f"news_router 导入失败: {e}")
    news_router = None

# 尝试导入数据采集路由
try:
    from .stock.data_collection_api import router as data_collection_router
    print("data_collection_router 导入成功")
except ImportError as e:
    print(f"data_collection_router 导入失败: {e}")
    data_collection_router = None

# 尝试导入股票分析路由
try:
    from .stock.stock_analysis_routes import router as stock_analysis_router
    print("stock_analysis_router 导入成功")
except ImportError as e:
    print(f"stock_analysis_router 导入失败: {e}")
    stock_analysis_router = None

# 尝试导入港股路由
try:
    from .stock.hk_stock_manage import router_old as hk_stock_router
    print("hk_stock_router 导入成功")
except ImportError as e:
    print(f"hk_stock_router 导入失败: {e}")
    hk_stock_router = None

# 尝试导入quotes路由
try:
    from .quotes_routes import router as quotes_router
    print("quotes_router 导入成功")
except ImportError as e:
    print(f"quotes_router 导入失败: {e}")
    quotes_router = None

# 尝试导入多周期历史行情路由
try:
    from .multi_period_quotes_routes import router as multi_period_quotes_router
    print("multi_period_quotes_router 导入成功")
except ImportError as e:
    print(f"multi_period_quotes_router 导入失败: {e}")
    multi_period_quotes_router = None

# 尝试导入推送路由
try:
    from .push_routes import router as push_router, admin_router as push_admin_router
    print("push_router 导入成功")
except ImportError as e:
    print(f"push_router 导入失败: {e}")
    push_router = None
    push_admin_router = None

# 创建 FastAPI 应用
app = FastAPI(
    title="股票分析系统 API",
    description="股票分析系统的后端 API 服务",
    version="1.0.2"
)
print(f"[backend_api.main] 已加载，文件路径: {__file__}", flush=True)

_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


async def _orm_stock_code_pg_check():
    """PostgreSQL 下 StockBasicInfo.code 与整数比较时是否编译出 CAST（用于排查 text=integer）。"""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from backend_api.models import StockBasicInfo

    stmt = select(StockBasicInfo).where(StockBasicInfo.code == 2709).limit(1)
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    upper = sql.upper()
    return {
        "main_py": __file__,
        "stock_code_type": type(StockBasicInfo.code.type).__name__,
        "postgresql_sql_contains_cast": "CAST(" in upper and "VARCHAR" in upper,
        "sample_sql": sql,
        "use_this_url": "优先使用本接口；勿依赖 /?orm_check=1（易被缓存或旧路由干扰）",
    }


# 配置 CORS — 必须在其它中间件之前添加
origins = [
    "http://localhost:3000",     # Vue 开发服务器
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://192.168.3.60:8000",  # 建议加上你的本机 IP 端口
    "http://192.168.3.60:5000",  # 如有需要
    "http://192.168.31.117:8000",  # 建议加上你的本机 IP 端口
    "http://192.168.31.117:5000",  # 如有需要
    "http://www.icemaplecity.com",  # 生产环境域名
    "https://www.icemaplecity.com",  # 生产环境 HTTPS 域名
    "http://icemaplecity.com",  # 生产环境域名（无 www）
    "https://icemaplecity.com",  # 生产环境 HTTPS 域名（无 www）
]

# 用于 CORS 的 origin 校验（含正则匹配 localhost 任意端口）
_cors_origin_regex = re.compile(r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$")

def _is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin in origins:
        return True
    return bool(_cors_origin_regex.match(origin))


def _include_router(app, router, label: str) -> None:
    """挂载子路由；router 为 None 时仅打印未注册（减少 main 中重复 if/else）。"""
    if router is not None:
        app.include_router(router)
        print(f"{label}路由注册成功")
    else:
        print(f"{label}路由未注册")


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

# 添加请求日志中间件 — 在 CORS 之后
app.add_middleware(RequestLoggingMiddleware)

# 在任何 include_router 之前注册：避免与其它路由冲突；路径唯一，便于排查
@app.get("/api/_debug/orm-stock-code-pg-check")
async def orm_stock_code_pg_check_early():
    return JSONResponse(content=await _orm_stock_code_pg_check(), headers=_NO_CACHE)


# ---------------------------------------------------------------------------
# VSB 信号历史 — 主应用直挂（与 screening / stock 子路由逻辑同源）
# 部分部署环境子路由未挂上时 /api/screening/vsb-signals 与 /api/stock/vsb-signals 会双 404，
# 此处固定注册在 main.app 上，路径与 stock_manage 等无前缀冲突。
# ---------------------------------------------------------------------------


@app.get("/api/vsb/signals")
async def vsb_signals_by_code_on_app(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="signal_date 起（含）"),
    end_date: Optional[str] = Query(None, description="signal_date 止（含）"),
    limit: int = Query(200, ge=1, le=2000, description="最大条数"),
    db: Session = Depends(get_db),
):
    from backend_api.services.vsb_signals_service import query_vsb_signals_by_code

    try:
        payload, err = query_vsb_signals_by_code(
            db, code=code, start_date=start_date, end_date=end_date, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "VSB 信号模型不可用", "data": [], "total": 0},
        )
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    if err == "bad_code":
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    return JSONResponse(payload)


@app.get("/api/vsb/signals/by-date")
async def vsb_signals_by_signal_date_on_app(
    signal_date: str = Query(..., description="信号日（突破日）YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000, description="最大条数"),
    db: Session = Depends(get_db),
):
    from backend_api.services.vsb_signals_service import query_vsb_signals_by_signal_date

    try:
        payload, err = query_vsb_signals_by_signal_date(db, signal_date=signal_date, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if err == "model_unavailable":
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "VSB 信号模型不可用", "data": [], "total": 0},
        )
    if err == "table_missing":
        return JSONResponse(status_code=503, content=payload)
    return JSONResponse(payload)


VSB_RECALCULATE_TIMEOUT_SEC = 120
VSB_REPLAY_TIMEOUT_SEC = 600


@app.post("/api/vsb/signals/recalculate")
async def vsb_signals_recalculate_on_app(
    code: str = Query(..., description="6 位股票代码"),
    name: Optional[str] = Query(None, description="证券简称，可空"),
    search_date: Optional[str] = Query(None, description="落库 run_search_date，默认今日 YYYY-MM-DD"),
    replay_range: bool = Query(False, description="为 true 时对 start_date～end_date 内每个交易日切片重算并落库"),
    start_date: Optional[str] = Query(None, description="逐日回放起始日 YYYY-MM-DD（与 end_date 同用）"),
    end_date: Optional[str] = Query(None, description="逐日回放结束日 YYYY-MM-DD"),
    volume_ratio: Optional[float] = Query(None, ge=1.0, le=30.0),
    boom_lookback_min: Optional[int] = Query(None, ge=1, le=250),
    boom_lookback_max: Optional[int] = Query(None, ge=1, le=250),
    db: Session = Depends(get_db),
):
    """单股按最新日线重算 VSB，或可选区间内逐日回放；命中则 upsert 至 volume_shrink_breakout_signals。"""
    try:
        from backend_core.strategies.volume_shrink_breakout import VolumeShrinkBreakoutFrontendInterface
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "3倍量缩量突破策略模块不可用",
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )

    if replay_range:
        rs = (start_date or "").strip()[:10]
        re = (end_date or "").strip()[:10]
        if not rs or not re:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "replay_range=true 时必须同时提供 start_date 与 end_date（YYYY-MM-DD）",
                    "saved": 0,
                    "hit": False,
                    "data": [],
                },
            )

    loop = asyncio.get_event_loop()
    timeout_sec = VSB_REPLAY_TIMEOUT_SEC if replay_range else VSB_RECALCULATE_TIMEOUT_SEC

    def _run():
        if replay_range:
            return VolumeShrinkBreakoutFrontendInterface.recalculate_range_replay_and_persist(
                db,
                code=code,
                name=name,
                search_date=search_date,
                replay_start=(start_date or "").strip()[:10],
                replay_end=(end_date or "").strip()[:10],
                volume_ratio=volume_ratio,
                boom_lookback_min=boom_lookback_min,
                boom_lookback_max=boom_lookback_max,
            )
        return VolumeShrinkBreakoutFrontendInterface.recalculate_single_and_persist(
            db,
            code=code,
            name=name,
            search_date=search_date,
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

    try:
        out = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": (
                    f"VSB 逐日回放超时（>{timeout_sec}s）"
                    if replay_range
                    else f"单股重算超时（>{timeout_sec}s）"
                ),
                "saved": 0,
                "hit": False,
                "data": [],
            },
        )
    if not out.get("success"):
        return JSONResponse(status_code=400, content=out)
    return JSONResponse(content=out)


# 挂载静态文件目录
#app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")

# ---------------------------------------------------------------------------
# 路由注册说明（GMS 与 PVFRS 路径已强制分离，无 URL 前缀冲突）：
#   - 管理端：/api/admin/gms/* 、/api/admin/pvfrs/*
#   - 前端公开：/api/frontend/gms/* 、/api/frontend/pvfrs/*
#   - GMS 信号追溯：/api/stock/* 下子路径（与 stock_manage 同前缀，由具体 path 区分）
# 与此前「text=integer」类问题无关；该类问题来自 ORM/列类型与 PostgreSQL。
# ---------------------------------------------------------------------------

# 注册关键路由
# 注册认证路由（必须在其它路由之前注册）
if auth_router is not None:
    app.include_router(auth_router)
    print("认证路由注册成功")
    # 打印认证路由的详细信息
    if hasattr(auth_router, 'routes'):
        print(f"   认证路由前缀: {auth_router.prefix}")
        print(f"   认证路由数量: {len(auth_router.routes)}")
        for route in auth_router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"   - {list(route.methods)} {route.path}")
else:
    print("认证路由未注册")
    import traceback
    traceback.print_exc()

_include_router(app, watchlist_router, "watchlist")
_include_router(app, market_router, "market")
_include_router(app, stock_router, "stock")
_include_router(app, triple_volume_observe_router, "triple_volume_observe")
_include_router(app, triple_volume_observe_admin_router, "triple_volume_observe_admin")
_include_router(app, vsb_observe_stocks_router, "vsb_observe_stocks")
_include_router(app, gms_trade_observe_router, "gms_trade_observe")
_include_router(app, gms_formal_trade_router, "gms_formal_trade")
_include_router(app, gms_user_preferences_router, "gms_user_preferences")
_include_router(app, triple_volume_trade_observe_router, "triple_volume_trade_observe")
_include_router(app, screening_router, "screening")
_include_router(app, gms_trace_router, "gms_trace")
_include_router(app, vsb_signal_router, "vsb_signal")
_include_router(app, history_router, "history")
_include_router(app, news_router, "新闻")
_include_router(app, data_collection_router, "数据采集")
_include_router(app, stock_analysis_router, "股票分析")
_include_router(app, hk_stock_router, "港股")
_include_router(app, quotes_router, "quotes")
_include_router(app, multi_period_quotes_router, "multi_period_quotes")
_include_router(app, push_router, "推送")
_include_router(app, push_admin_router, "推送管理员")

# 尝试导入交易笔记与模拟交易路由
try:
    from .trading_notes_routes import router as trading_notes_router
    print("trading_notes_router 导入成功")
except ImportError as e:
    print(f"trading_notes_router 导入失败: {e}")
    trading_notes_router = None
try:
    from .trading_routes import router as simtrade_router
    print("simtrade_router 导入成功")
except ImportError as e:
    print(f"simtrade_router 导入失败: {e}")
    simtrade_router = None

_include_router(app, trading_notes_router, "trading_notes")
_include_router(app, simtrade_router, "simtrade")

# 尝试导入admin路由
try:
    from .admin.auth import router as admin_auth_router
    print("admin_auth_router 导入成功")
except ImportError as e:
    print(f"admin_auth_router 导入失败: {e}")
    admin_auth_router = None

try:
    from .admin.dashboard import router as admin_dashboard_router
    print("admin_dashboard_router 导入成功")
except ImportError as e:
    print(f"admin_dashboard_router 导入失败: {e}")
    admin_dashboard_router = None

try:
    from .admin.indicators import router as admin_indicators_router
    print("admin_indicators_router 导入成功")
    # 打印路由信息用于调试
    if admin_indicators_router:
        print(f"   - 路由前缀: {admin_indicators_router.prefix}")
        print(f"   - 路由数量: {len(admin_indicators_router.routes)}")
        # 打印所有路由路径
        for route in admin_indicators_router.routes:
            if hasattr(route, 'path'):
                print(f"   - 路由路径: {route.path}")
except ImportError as e:
    print(f"admin_indicators_router 导入失败: {e}")
    admin_indicators_router = None

# 导入系统监控路由
try:
    from .admin.system_monitoring import router as system_monitoring_router
    print("system_monitoring_router 导入成功")
except ImportError as e:
    print(f"system_monitoring_router 导入失败: {e}")
    system_monitoring_router = None

# 尝试导入用户管理路由
try:
    from .admin.users import router as admin_users_router
    print("admin_users_router 导入成功")
except Exception as e:
    import traceback
    print(f"admin_users_router 导入失败: {e}")
    traceback.print_exc()
    admin_users_router = None

try:
    from .admin.roles import router as admin_roles_router
    print("admin_roles_router 导入成功")
except Exception as e:
    import traceback
    print(f"admin_roles_router 导入失败: {e}")
    traceback.print_exc()
    admin_roles_router = None

try:
    from .admin.permissions import router as admin_permissions_router
    print("admin_permissions_router 导入成功")
except Exception as e:
    import traceback
    print(f"admin_permissions_router 导入失败: {e}")
    traceback.print_exc()
    admin_permissions_router = None

try:
    from .admin.user_permissions import router as admin_user_permissions_router
    print("admin_user_permissions_router 导入成功")
except Exception as e:
    import traceback
    print(f"admin_user_permissions_router 导入失败: {e}")
    traceback.print_exc()
    admin_user_permissions_router = None

# 尝试导入日志查询路由
try:
    from .admin.logs import router as admin_logs_router
    print("admin_logs_router 导入成功")
except ImportError as e:
    print(f"admin_logs_router 导入失败: {e}")
    admin_logs_router = None

# 尝试导入操作日志路由
try:
    from .admin.operation_logs import router as admin_operation_logs_router
    print("admin_operation_logs_router 导入成功")
except ImportError as e:
    print(f"admin_operation_logs_router 导入失败: {e}")
    admin_operation_logs_router = None

# 尝试导入行情管理路由
try:
    from .admin.quotes import router as admin_quotes_router
    print("admin_quotes_router 导入成功")
except ImportError as e:
    print(f"admin_quotes_router 导入失败: {e}")
    admin_quotes_router = None

# 尝试导入股票基本信息管理路由
try:
    from .admin.stock_basic_admin import router as admin_stock_basic_router
    print("admin_stock_basic_router 导入成功")
except ImportError as e:
    print(f"admin_stock_basic_router 导入失败: {e}")
    admin_stock_basic_router = None

try:
    from .admin.board_constituents import router as admin_board_constituents_router
    print("admin_board_constituents_router 导入成功")
except ImportError as e:
    print(f"admin_board_constituents_router 导入失败: {e}")
    admin_board_constituents_router = None

# 尝试导入采集日历管理路由
try:
    from .admin.trading_calendar import router as trading_calendar_router
    print("trading_calendar_router 导入成功")
except ImportError as e:
    print(f"trading_calendar_router 导入失败: {e}")
    trading_calendar_router = None

# 注册admin路由
if admin_auth_router is not None:
    app.include_router(admin_auth_router)
    print("admin auth路由注册成功")

if admin_dashboard_router is not None:
    app.include_router(admin_dashboard_router)
    print("admin dashboard路由注册成功")

if admin_indicators_router is not None:
    app.include_router(admin_indicators_router)
    print("admin indicators路由注册成功")
else:
    print("admin indicators路由未注册")

# 注册系统监控路由
if system_monitoring_router is not None:
    app.include_router(system_monitoring_router)
    print("system monitoring路由注册成功")
else:
    print("system monitoring路由未注册")

# 注册用户管理路由
if admin_users_router is not None:
    app.include_router(admin_users_router)
    print("admin users路由注册成功")
else:
    print("admin users路由未注册")

if admin_user_permissions_router is not None:
    app.include_router(admin_user_permissions_router)
    print("admin user permissions路由注册成功")
else:
    print("admin user permissions路由未注册")

if admin_roles_router is not None:
    app.include_router(admin_roles_router)
    print("admin roles路由注册成功")
else:
    print("admin roles路由未注册")

if admin_permissions_router is not None:
    app.include_router(admin_permissions_router)
    print("admin permissions路由注册成功")
else:
    print("admin permissions路由未注册")

# 注册日志查询路由
if admin_logs_router is not None:
    app.include_router(admin_logs_router)
    print("admin logs路由注册成功")

# 注册操作日志路由
if admin_operation_logs_router is not None:
    app.include_router(admin_operation_logs_router)
    print("admin operation logs路由注册成功")

# 注册行情管理路由
if admin_quotes_router is not None:
    app.include_router(admin_quotes_router)
    print("admin quotes路由注册成功")

# 注册股票基本信息管理路由
if admin_stock_basic_router is not None:
    app.include_router(admin_stock_basic_router)
    print("admin stock basic路由注册成功")

if admin_board_constituents_router is not None:
    app.include_router(admin_board_constituents_router)
    print("admin board constituents路由注册成功")

# 注册采集日历管理路由
if trading_calendar_router is not None:
    app.include_router(trading_calendar_router)
    print("trading calendar路由注册成功")

# 尝试导入PVFRS admin路由
try:
    from backend_api.admin.pvfrs_admin_routes import router as pvfrs_admin_router
    print("pvfrs_admin_router 导入成功")
    # 打印路由信息用于调试
    if pvfrs_admin_router:
        print(f"   - 路由前缀: {pvfrs_admin_router.prefix}")
        print(f"   - 路由数量: {len(pvfrs_admin_router.routes)}")
        # 打印所有路由路径
        for route in pvfrs_admin_router.routes:
            if hasattr(route, 'path'):
                print(f"   - 路由路径: {route.path}")
except ImportError as e:
    print(f"pvfrs_admin_router 导入失败: {e}")
    import traceback
    traceback.print_exc()
    pvfrs_admin_router = None
except Exception as e:
    print(f"pvfrs_admin_router 导入时发生其它错误: {e}")
    import traceback
    traceback.print_exc()
    pvfrs_admin_router = None

# 注册 PVFRS 管理端路由（仅注册一次；此前重复 include 会导致同路径注册两遍）
if pvfrs_admin_router is not None:
    app.include_router(pvfrs_admin_router)
    print("PVFRS admin 路由注册成功 (/api/admin/pvfrs)")
else:
    print("PVFRS admin 路由未注册（导入失败）")

# 尝试导入 GMS admin 路由
try:
    from backend_api.admin.gms_admin_routes import router as gms_admin_router
    print("gms_admin_router 导入成功")
except Exception as e:
    print(f"gms_admin_router 导入失败: {e}")
    gms_admin_router = None

if gms_admin_router is not None:
    app.include_router(gms_admin_router)
    print("GMS admin 路由注册成功 (/api/admin/gms)")
else:
    print("GMS admin 路由未注册")

# 尝试导入 URT admin 路由
try:
    from backend_api.admin.urt_admin_routes import router as urt_admin_router
    print("urt_admin_router 导入成功")
except Exception as e:
    print(f"urt_admin_router 导入失败: {e}")
    urt_admin_router = None

if urt_admin_router is not None:
    app.include_router(urt_admin_router)
    print("URT admin 路由注册成功 (/api/admin/urt)")
else:
    print("URT admin 路由未注册")

# 尝试导入 ETF admin 路由
try:
    from backend_api.admin.etf_admin_routes import router as etf_admin_router
    print("etf_admin_router 导入成功")
except Exception as e:
    print(f"etf_admin_router 导入失败: {e}")
    etf_admin_router = None

if etf_admin_router is not None:
    app.include_router(etf_admin_router)
    print("ETF admin 路由注册成功 (/api/admin/etf)")
else:
    print("ETF admin 路由未注册")

# 前端公开接口：路径与 PVFRS 完全分离（/api/frontend/gms vs /api/frontend/pvfrs）
if gms_frontend_router is not None:
    app.include_router(gms_frontend_router)
    print("GMS 前端路由注册成功 (/api/frontend/gms)")
else:
    print("GMS 前端路由未注册")

if pvfrs_frontend_router is not None:
    app.include_router(pvfrs_frontend_router)
    print("PVFRS 前端路由注册成功 (/api/frontend/pvfrs)")
else:
    print("PVFRS 前端路由未注册")

# 全局异常处理：确保错误响应也带 CORS 头，避免前端跨域时报 No 'Access-Control-Allow-Origin'
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logger.error("未捕获异常: %s\n%s", exc, tb)
    # 同步打到 stderr，避免仅写入 app.log 时终端看不到（便于排查 ORM/PG 错误）
    print(f"[未捕获异常] {exc}\n{tb}", file=sys.stderr, flush=True)
    body = {"detail": str(exc), "success": False}
    response = JSONResponse(status_code=500, content=body)
    origin = request.headers.get("origin")
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# 根路径重定向到管理后台
@app.get("/")
async def root(orm_check: Optional[str] = Query(None, description="任意非空则返回 ORM 编译自检 JSON")):
    if orm_check is not None:
        return JSONResponse(content=await _orm_stock_code_pg_check(), headers=_NO_CACHE)
    return JSONResponse(
        content={
            "message": "Welcome to Stock Analysis System API [rev:2026-04-orm3]",
            "main_py": __file__,
            "api_revision": "2026-04-orm3",
            "orm_selftest": "请打开 /api/_debug/orm-stock-code-pg-check（不要用缓存的 /）",
        },
        headers=_NO_CACHE,
    )

@app.get("/debug/routes")
async def list_routes():
    """列出已注册的路由（调试用）。"""
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else None
            })
    return routes


for _path in (
    "/stock-code-orm-check",
    "/debug/stock-code-orm-check",
    "/api/health/stock-code-orm-check",
):
    app.add_api_route(_path, _orm_stock_code_pg_check, methods=["GET"])


@app.on_event("startup")
async def startup_event():
    """应用启动时执行。"""
    try:
        logger.info("正在初始化数据库...")
        #init_db()
        logger.info("数据库初始化完成")

        try:
            from backend_api.models import StockBasicInfo

            code_t = StockBasicInfo.__table__.c.code.type
            logger.info(
                "StockBasicInfo.code 列类型: %s（若为 StockCodeTextPK 列，ORM 与 int 比较会按字符串绑定）",
                type(code_t).__name__,
            )
        except Exception as e:
            logger.warning("StockBasicInfo.code 列类型探测失败: %s", e)
        
        try:
            from backend_api.database import SessionLocal
            from backend_api.permissions import ensure_permissions_from_registry

            db = SessionLocal()
            try:
                result = ensure_permissions_from_registry(db)
                if result.get("created"):
                    logger.info(
                        "权限注册表增量同步：新建 %s 项 %s",
                        result["created"],
                        result.get("created_codes"),
                    )
                else:
                    logger.info("权限注册表增量同步完成（无新建项）")
            finally:
                db.close()
        except Exception as e:
            logger.warning("权限注册表增量同步失败: %s", e)

        # 启动 PVFRS 监控后台线程
        try:
            from backend_core.strategies.pvfrs.monitor_service import monitor_service
            monitor_service.start_background_monitoring()
            logger.info("PVFRS 后台监控已启动")
        except Exception as e:
            logger.warning(f"⚠ PVFRS 后台监控启动失败: {e}")
        
        # 启动系统监控后台线程
        try:
            from backend_core.monitoring import system_monitor
            system_monitor.start_background_monitoring()
            logger.info("系统监控后台线程已启动")
        except Exception as e:
            logger.warning(f"⚠ 系统监控后台线程启动失败: {e}")
            
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
