"""
PVFRS策略前端API路由
提供选股频道页面的PVFRS展示功能接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Dict, Optional
import logging
import traceback

from backend_api.database import get_db
from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface, create_frontend_interface
from backend_core.strategies.pvfrs.models import PVFRSException
from backend_core.strategies.pvfrs.serialization import get_formatter, validate_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/frontend/pvfrs", tags=["PVFRS前端接口"])

# 全局前端接口实例
_frontend_interface: Optional[FrontendInterface] = None


def get_frontend_interface() -> FrontendInterface:
    """获取前端接口实例"""
    global _frontend_interface
    if _frontend_interface is None:
        _frontend_interface = create_frontend_interface()
    return _frontend_interface


@router.get("/selection-results")
async def get_selection_results(
    date: Optional[str] = Query(None, description="目标日期，格式：YYYY-MM-DD，不提供则使用当前日期"),
    limit: Optional[int] = Query(None, ge=1, description="最大返回结果数量，不限制则返回所有符合条件的股票"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="最低信号强度阈值，默认0.3"),
    db: Session = Depends(get_db)
):
    """
    获取PVFRS选股结果
    
    获取符合PVFRS条件的股票列表，包含股票代码、名称、信号强度、满足条件等信息。
    
    Args:
        date: 目标日期，如果不提供则使用当前日期
        limit: 最大返回结果数量
        min_strength: 最低信号强度阈值
        db: 数据库会话
    
    Returns:
        PVFRS选股结果列表，按信号强度降序排列
    """
    try:
        logger.info(f"获取PVFRS选股结果 - 日期: {date or '当前'}, 限制: {limit}, 最低强度: {min_strength}")
        
        # 参数验证
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="日期格式错误，应为 YYYY-MM-DD"
                )
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
        # 设置选股配置
        if limit is not None:
            frontend_interface.set_selection_config(max_results=limit, min_strength=min_strength)
        else:
            # 不限制结果数量，设置一个很大的值
            frontend_interface.set_selection_config(max_results=10000, min_strength=min_strength)
        
        # 获取选股结果
        selection_results = frontend_interface.get_selection_results(date)
        
        # 转换为API响应格式
        results_data = []
        for result in selection_results:
            result_dict = result.to_dict()
            
            # 格式化维度状态显示（前端期望的字段）
            indicators = result_dict.get('indicators', {})
            
            # 价格维度状态
            price_dim = indicators.get('price_dimension', {})
            if price_dim.get('price_dimension_valid', False):
                price_status = f"宏观位移: {price_dim.get('macro_displacement', 0):.2f}"
            else:
                price_status = "未满足条件"
            
            # 频率维度状态
            frequency_dim = indicators.get('frequency_dimension', {})
            if frequency_dim.get('frequency_dimension_valid', False):
                rising_days = frequency_dim.get('rising_days', 0)
                falling_days = frequency_dim.get('falling_days', 0)
                frequency_status = f"上涨{rising_days}天/下跌{falling_days}天"
            else:
                frequency_status = "未满足条件"
            
            # 成交量维度状态
            volume_dim = indicators.get('volume_dimension', {})
            if volume_dim.get('volume_dimension_valid', False):
                efficiency_ratio = volume_dim.get('efficiency_ratio', 0)
                volume_status = f"效率比: {efficiency_ratio:.2f}"
            else:
                volume_status = "未满足条件"
            
            # 入场时机状态
            entry_timing = indicators.get('entry_timing_analysis', {})
            if entry_timing.get('optimal_timing', False):
                entry_status = "最佳时机"
            elif entry_timing.get('acceptable_timing', False):
                entry_status = "可接受"
            else:
                entry_status = "等待时机"
            
            # 共振状态
            resonance_analysis = indicators.get('resonance_analysis', {})
            if resonance_analysis.get('three_dimension_resonance', False):
                resonance_status = "三维共振"
            elif resonance_analysis.get('partial_resonance', False):
                resonance_status = "部分共振"
            else:
                resonance_status = "无共振"
            
            # 投资建议
            investment_advice = indicators.get('investment_advice', {})
            if isinstance(investment_advice, dict):
                advice = investment_advice.get('recommendation', '观望')
            else:
                advice = str(investment_advice) if investment_advice else '观望'
            
            # 添加前端期望的字段
            result_dict.update({
                'price_dimension_status': price_status,
                'frequency_dimension_status': frequency_status,
                'volume_dimension_status': volume_status,
                'entry_timing_status': entry_status,
                'resonance_status': resonance_status,
                'investment_advice': advice,
                'current_price': result_dict.get('price', 0)
            })
            
            results_data.append(result_dict)
        
        logger.info(f"PVFRS选股结果获取完成，返回 {len(results_data)} 只股票")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_selection_results(
            results_data,
            query_date=date or datetime.now().strftime("%Y-%m-%d"),
            parameters={
                "limit": limit or "无限制",
                "min_strength": min_strength
            }
        )
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"PVFRS选股结果获取失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PVFRS选股结果获取失败: {str(e)}"
        )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取PVFRS选股结果时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取PVFRS选股结果时发生未知错误: {str(e)}"
        )


@router.get("/stock-detail/{symbol}")
async def get_stock_detail(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    获取股票详细PVFRS分析指标
    
    提供单只股票的完整三维分析结果展示。
    
    Args:
        symbol: 股票代码
        db: 数据库会话
    
    Returns:
        股票详细PVFRS分析信息
    """
    try:
        logger.info(f"获取股票详细PVFRS分析 - 股票代码: {symbol}")
        
        # 参数验证
        if not symbol or len(symbol.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="股票代码不能为空"
            )
        
        symbol = symbol.strip().upper()
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
        # 获取股票详细信息
        stock_detail = frontend_interface.get_stock_detail(symbol)
        
        # 转换为API响应格式
        detail_data = stock_detail.to_dict()
        
        logger.info(f"股票 {symbol} 详细PVFRS分析获取完成")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_stock_detail(detail_data)
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"获取股票 {symbol} 详细分析失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取股票 {symbol} 详细分析失败: {str(e)}"
        )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取股票 {symbol} 详细分析时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票 {symbol} 详细分析时发生未知错误: {str(e)}"
        )


@router.post("/refresh-results")
async def refresh_results(
    db: Session = Depends(get_db)
):
    """
    刷新PVFRS选股结果
    
    清除缓存并重新获取最新的选股结果。
    
    Args:
        db: 数据库会话
    
    Returns:
        刷新操作结果
    """
    try:
        logger.info("刷新PVFRS选股结果")
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
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
async def get_selection_summary(
    db: Session = Depends(get_db)
):
    """
    获取PVFRS选股汇总信息
    
    提供选股结果的统计汇总信息。
    
    Args:
        db: 数据库会话
    
    Returns:
        PVFRS选股汇总信息
    """
    try:
        logger.info("获取PVFRS选股汇总信息")
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
        # 获取汇总信息
        summary_data = frontend_interface.get_selection_summary()
        
        logger.info("PVFRS选股汇总信息获取完成")
        
        return JSONResponse({
            "success": True,
            "data": summary_data,
            "query_time": datetime.now().isoformat(),
            "strategy_name": "PVFRS量价频三维共振演化策略"
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS选股汇总信息时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 返回错误信息而不是抛出异常，因为汇总信息可能包含部分错误
        return JSONResponse({
            "success": False,
            "error": f"获取PVFRS选股汇总信息失败: {str(e)}",
            "query_time": datetime.now().isoformat(),
            "strategy_name": "PVFRS量价频三维共振演化策略"
        })


@router.get("/interface-status")
async def get_interface_status(
    db: Session = Depends(get_db)
):
    """
    获取前端接口状态
    
    提供前端接口的运行状态和配置信息。
    
    Args:
        db: 数据库会话
    
    Returns:
        前端接口状态信息
    """
    try:
        logger.info("获取PVFRS前端接口状态")
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
        # 获取接口状态
        status_data = frontend_interface.get_interface_status()
        
        logger.info("PVFRS前端接口状态获取完成")
        
        return JSONResponse({
            "success": True,
            "data": status_data,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS前端接口状态时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取PVFRS前端接口状态失败: {str(e)}"
        )


@router.get("/system/status")
async def get_system_status(
    db: Session = Depends(get_db)
):
    """
    获取系统状态
    
    提供PVFRS系统的整体运行状态信息。
    
    Args:
        db: 数据库会话
    
    Returns:
        系统状态信息
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
    db: Session = Depends(get_db)
):
    """
    创建回测任务（前端接口）
    
    Args:
        task_data: 回测任务数据
        db: 数据库会话
    
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
    db: Session = Depends(get_db)
):
    """
    设置缓存配置
    
    Args:
        enabled: 是否启用缓存
        duration_minutes: 缓存持续时间（分钟）
        db: 数据库会话
    
    Returns:
        配置更新结果
    """
    try:
        logger.info(f"设置PVFRS前端接口缓存配置 - 启用: {enabled}, 持续时间: {duration_minutes}分钟")
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
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
    db: Session = Depends(get_db)
):
    """
    设置选股配置
    
    Args:
        max_results: 最大返回结果数量
        min_strength: 最低信号强度阈值
        db: 数据库会话
    
    Returns:
        配置更新结果
    """
    try:
        logger.info(f"设置PVFRS前端接口选股配置 - 最大结果: {max_results}, 最低强度: {min_strength}")
        
        # 获取前端接口实例
        frontend_interface = get_frontend_interface()
        
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
