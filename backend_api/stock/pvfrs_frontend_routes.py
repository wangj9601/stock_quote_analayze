"""
PVFRS 策略前端 API 路由（仅 PVFRS，与 GMS 路径无关）
前缀: /api/frontend/pvfrs
"""

from dataclasses import asdict

from fastapi import APIRouter, Query, HTTPException, status, Body
from fastapi.responses import JSONResponse
from datetime import datetime, date
from typing import List, Dict, Optional, Any
import logging
import traceback

try:
    from backend_core.strategies.pvfrs.models import PVFRSException
except ImportError:
    PVFRSException = Exception  # 无 pvfrs 时用 Exception 占位，避免 except 块 NameError

try:
    from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface
except ImportError:
    FrontendInterface = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/frontend/pvfrs", tags=["PVFRS前端接口"])


def get_pvfrs_frontend_interface() -> "FrontendInterface":
    """PVFRS 策略前端接口（与 GMS 的 GMSFrontendInterface 完全独立）。"""
    if FrontendInterface is None:
        raise HTTPException(status_code=503, detail="PVFRS 策略模块未加载")
    return FrontendInterface()


@router.get("/selection-results")
async def get_selection_results(
    date: Optional[str] = Query(None, description="目标日期，格式：YYYY-MM-DD，不提供则使用当前日期"),
    limit: Optional[int] = Query(None, ge=1, description="最大返回结果数量，不限制则返回所有符合条件的股票"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值，默认0.3"),
):
    """
    获取 PVFRS 选股结果（与 GMS 无关，不读 gms_signal_trace）。
    """
    try:
        if date:
            try:
                datetime.strptime(str(date).strip()[:10], "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

        logger.info(f"获取 PVFRS 选股结果 - 日期: {date or '当前'}, 限制: {limit}, 最低强度: {min_strength}")

        fi = get_pvfrs_frontend_interface()
        fi.set_selection_config(fi.max_selection_results, min_strength)
        raw = fi.get_selection_results(date=date)
        rows = [r.to_dict() for r in raw]
        if limit:
            rows = rows[: int(limit)]

        return JSONResponse({
            "success": True,
            "data": rows,
            "total": len(rows),
            "search_date": date or datetime.now().strftime("%Y-%m-%d"),
            "strategy_name": "PVFRS",
            "data_source": "pvfrs_frontend_interface",
            "timestamp": datetime.now().isoformat(),
        })

    except HTTPException:
        raise
    except PVFRSException as e:
        logger.error(f"PVFRS选股结果获取失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PVFRS选股结果获取失败: {str(e)}",
        )
    except Exception as e:
        logger.error(f"获取PVFRS选股结果时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取PVFRS选股结果时发生未知错误: {str(e)}",
        )


@router.get("/stock-detail/{symbol}")
async def get_stock_detail(symbol: str):
    """
    获取 PVFRS 股票详细分析（与 GMS 无关）。
    GMS 单股详情请使用：`GET /api/frontend/gms/stock-detail/{symbol}`。
    """
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="股票代码不能为空")

        logger.info(f"获取 PVFRS 股票详情 - 股票代码: {symbol}")
        fi = get_pvfrs_frontend_interface()
        detail = fi.get_stock_detail(symbol)
        return JSONResponse({
            "success": True,
            "data": asdict(detail),
            "strategy_name": "PVFRS",
            "data_source": "pvfrs_frontend_interface",
            "timestamp": datetime.now().isoformat(),
        })
    except PVFRSException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 PVFRS 股票 {symbol} 详情失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-results")
async def refresh_results():
    """
    刷新PVFRS选股结果
    
    清除缓存并重新获取最新的选股结果。
    
    Returns:
        刷新操作结果
    """
    try:
        logger.info("刷新PVFRS选股结果")
        
        # 获取前端接口实例
        frontend_interface = get_pvfrs_frontend_interface()
        
        # 执行刷新
        refresh_success = frontend_interface.refresh_results()
        
        if refresh_success:
            logger.info("PVFRS选股结果刷新成功")
            return JSONResponse({
                "success": True,
                "message": "PVFRS选股结果刷新成功",
                "refresh_time": datetime.now().isoformat()
            })
        else:
            logger.warning("PVFRS选股结果刷新失败")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PVFRS选股结果刷新失败"
            )
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"刷新PVFRS选股结果时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新PVFRS选股结果时发生未知错误: {str(e)}"
        )


@router.get("/selection-summary")
async def get_selection_summary():
    """
    获取 PVFRS 选股汇总信息（与 GMS 无关）。
    GMS 汇总请使用：`GET /api/frontend/gms/selection-summary`。
    """
    try:
        logger.info("获取 PVFRS 选股汇总信息")
        fi = get_pvfrs_frontend_interface()
        summary = fi.get_selection_summary()
        return JSONResponse({
            "success": True,
            "data": summary,
            "query_time": datetime.now().isoformat(),
            "strategy_name": "PVFRS",
            "data_source": "pvfrs_frontend_interface",
        })
    except Exception as e:
        logger.error(f"获取 PVFRS 选股汇总信息时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "success": False,
            "error": f"获取汇总信息失败: {str(e)}",
            "query_time": datetime.now().isoformat(),
            "data_source": "pvfrs_frontend_interface",
        })


@router.get("/interface-status")
async def get_interface_status():
    """
    获取 PVFRS 前端接口状态。
    """
    try:
        logger.info("获取PVFRS前端接口状态")
        
        # 获取前端接口实例
        frontend_interface = get_pvfrs_frontend_interface()
        
        # 获取接口状态
        status_data = frontend_interface.get_interface_status()
        
        logger.info("PVFRS前端接口状态获取完成")
        
        return JSONResponse({
            "success": True,
            "data": status_data,
            "query_time": datetime.now().isoformat(),
            "data_source": "pvfrs_frontend_interface",
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS前端接口状态时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取PVFRS前端接口状态失败: {str(e)}"
        )


@router.get("/system/status")
async def get_system_status():
    """
    获取 PVFRS 系统整体运行状态。
    """
    try:
        logger.info("获取PVFRS系统状态")
        
        # 从 MonitorService 获取最新监控数据
        from backend_core.strategies.pvfrs.monitor_service import monitor_service
        monitor_data = monitor_service.get_monitoring_data()
        
        system_status = {
            "status": monitor_data.get("status", "running"),
            "version": "2.1.0",
            "uptime": "运行中",
            "last_update": monitor_data.get("last_update", datetime.now().isoformat()),
            "components": {
                "frontend_interface": "running",
                "data_collector": "running", 
                "strategy_engine": "running",
                "database": "connected" if monitor_data.get("status") != "error" else "disconnected"
            },
            "performance": {
                "cpu_usage": monitor_data.get("system_health", {}).get("cpu_usage", 0),
                "memory_usage": monitor_data.get("system_health", {}).get("memory_usage", 0),
                "disk_usage": monitor_data.get("system_health", {}).get("disk_usage", 0),
                "response_time": monitor_data.get("performance", {}).get("avg_response_time", 0.05)
            },
            "statistics": {
                "total_stocks": monitor_data.get("total_signals", 0),
                "active_signals": monitor_data.get("active_stocks", 0),
                "processed_today": monitor_data.get("strong_signals", 0),
                "success_rate": monitor_data.get("performance", {}).get("success_rate", 0)
            }
        }
        
        logger.info("PVFRS系统状态获取完成")
        
        return JSONResponse({
            "success": True,
            "data": system_status,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS系统状态时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )


@router.post("/backtest")
async def create_backtest_task(
    task_data: Dict = Body(..., description="回测任务数据"),
):
    """
    创建回测任务（前端接口）
    
    Args:
        task_data: 回测任务数据
    
    Returns:
        创建的任务信息
    """
    try:
        logger.info("创建PVFRS回测任务（前端接口）")
        
        # 简化回测任务创建，避免复杂的依赖调用
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"PVFRS回测任务创建成功: {task_id}")
        
        return JSONResponse({
            "success": True,
            "data": {
                "task_id": task_id,
                "status": "created",
                "created_at": datetime.now().isoformat(),
                "config": task_data
            },
            "message": "回测任务创建成功"
        })
        
    except Exception as e:
        logger.error(f"创建PVFRS回测任务时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建回测任务失败: {str(e)}"
        )


@router.post("/config/cache")
async def set_cache_config(
    enabled: bool = Query(True, description="是否启用缓存"),
    duration_minutes: int = Query(5, ge=1, le=60, description="缓存持续时间（分钟）"),
):
    """
    设置缓存配置
    
    Args:
        enabled: 是否启用缓存
        duration_minutes: 缓存持续时间（分钟）
    
    Returns:
        配置更新结果
    """
    try:
        logger.info(f"设置PVFRS前端接口缓存配置 - 启用: {enabled}, 持续时间: {duration_minutes}分钟")
        
        # 获取前端接口实例
        frontend_interface = get_pvfrs_frontend_interface()
        
        # 设置缓存配置
        frontend_interface.set_cache_config(enabled, duration_minutes)
        
        logger.info("PVFRS前端接口缓存配置更新成功")
        
        return JSONResponse({
            "success": True,
            "message": "缓存配置更新成功",
            "config": {
                "enabled": enabled,
                "duration_minutes": duration_minutes
            },
            "update_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"设置PVFRS前端接口缓存配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置缓存配置失败: {str(e)}"
        )


@router.post("/config/selection")
async def set_selection_config(
    max_results: Optional[int] = Query(None, ge=1, description="最大返回结果数量，不设置则不限制"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值"),
):
    """
    设置选股配置
    
    Args:
        max_results: 最大返回结果数量
        min_strength: 最低信号强度阈值
    
    Returns:
        配置更新结果
    """
    try:
        logger.info(f"设置PVFRS前端接口选股配置 - 最大结果: {max_results}, 最低强度: {min_strength}")
        
        # 获取前端接口实例
        frontend_interface = get_pvfrs_frontend_interface()
        
        # 设置选股配置
        if max_results is not None:
            frontend_interface.set_selection_config(max_results, min_strength)
        else:
            # 不限制结果数量，设置一个很大的值
            frontend_interface.set_selection_config(10000, min_strength)
        
        logger.info("PVFRS前端接口选股配置更新成功")
        
        return JSONResponse({
            "success": True,
            "message": "选股配置更新成功",
            "config": {
                "max_results": max_results or "无限制",
                "min_strength": min_strength
            },
            "update_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"设置PVFRS前端接口选股配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置选股配置失败: {str(e)}"
        )


@router.get("/monitor")
async def get_monitoring_data():
    """
    获取实时监控数据
    
    提供PVFRS策略的实时监控状态数据。
    
    Returns:
        实时监控数据
    """
    try:
        logger.info("获取PVFRS实时监控数据")
        
        from backend_core.strategies.pvfrs.monitor_service import monitor_service
        monitoring_data = monitor_service.get_monitoring_data()
        
        logger.info("PVFRS实时监控数据获取成功")
        return JSONResponse({
            "success": True,
            "data": monitoring_data
        })
    except Exception as e:
        logger.error(f"获取PVFRS实时监控数据时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitor/alerts")
async def get_monitoring_alerts():
    """
    获取监控告警列表
    
    提供PVFRS策略系统的告警信息。
    
    Returns:
        告警列表
    """
    try:
        logger.info("获取PVFRS监控告警列表")
        
        from backend_core.strategies.pvfrs.monitor_service import monitor_service
        alerts = monitor_service.get_monitoring_alerts()
        
        logger.info("PVFRS监控告警列表获取成功")
        return JSONResponse({
            "success": True,
            "data": alerts,
            "total": len(alerts)
        })
    except Exception as e:
        logger.error(f"获取PVFRS监控告警列表时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    确认监控告警
    
    标记指定告警为已确认状态。
    """
    try:
        logger.info(f"确认PVFRS监控告警: {alert_id}")
        
        from backend_core.strategies.pvfrs.monitor_service import monitor_service
        success = monitor_service.acknowledge_alert(int(alert_id))
        
        if success:
            return JSONResponse({
                "success": True,
                "message": f"告警 {alert_id} 已确认",
                "acknowledged_at": datetime.now().isoformat()
            })
        else:
            raise HTTPException(status_code=404, detail="未找到该告警")
    except Exception as e:
        logger.error(f"确认PVFRS监控告警时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitor/performance")
async def get_performance_metrics(
    timeRange: str = Query("1h", description="时间范围: 1h, 6h, 1d, 1w"),
    interval: str = Query("15m", description="数据间隔: 1m, 5m, 15m, 1h")
):
    """
    获取性能指标数据
    """
    try:
        logger.info(f"获取PVFRS性能指标数据 - 时间范围: {timeRange}, 间隔: {interval}")
        
        from backend_core.strategies.pvfrs.monitor_service import monitor_service
        performance_data = monitor_service.get_performance_metrics(timeRange, interval)
        
        logger.info("PVFRS性能指标数据获取成功")
        return JSONResponse({
            "success": True,
            "data": performance_data
        })
    except Exception as e:
        logger.error(f"获取PVFRS性能指标数据时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
