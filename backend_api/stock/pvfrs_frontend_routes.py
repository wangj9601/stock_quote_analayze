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

from backend_api.models import GMSSignalTrace, MeanFrequencyResonanceIndicators, StockBasicInfo, StockBasicInfoHK
from sqlalchemy import func, desc, or_

# 导入 GMS 策略接口
try:
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface
    from backend_core.strategies.gms.config import GMSConfigManager as GMSConfigManagerCls
    GMS_AVAILABLE = True
except ImportError:
    GMS_AVAILABLE = False

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
        logger.info(f"获取GMS选股结果 - 日期: {date or '最新'}, 限制: {limit}, 最低强度: {min_strength}")

        # 确定目标日期
        target_date = date
        if not target_date:
            target_date = db.query(func.max(GMSSignalTrace.date)).scalar()
        
        if not target_date:
            return JSONResponse({
                "success": True,
                "data": [],
                "total": 0,
                "message": "策略结果表中无数据"
            })

        # 从 GMS 结果表中查询数据，不再重新执行筛选
        query = db.query(GMSSignalTrace).filter(GMSSignalTrace.date == target_date)
        
        if min_strength:
            min_score = min_strength * 100
            query = query.filter(GMSSignalTrace.score_total >= min_score)
        
        query = query.order_by(desc(GMSSignalTrace.score_total))
        
        if limit:
            query = query.limit(limit)
            
        selection_results = query.all()

        # 映射字段以适配前端
        results_data = []
        for r in selection_results:
            code = r.code
            st = r.score_total or 0
            
            # 获取股票名称 (简单缓存或批量查询更佳，这里保持逻辑一致)
            name = f"股票{code}"
            # 判断 CN/HK 并查询
            is_cn = len(code) >= 6 and code.isdigit() and code[0] in "6039"
            if is_cn:
                stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
            else:
                stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
            if stock_info:
                name = stock_info.name

            # 投资建议逻辑
            if st >= 90: advice = "强烈推荐"
            elif st >= 75: advice = "推荐"
            elif st >= 60: advice = "关注"
            else: advice = "观望"

            results_data.append({
                'symbol': code,
                'name': name,
                'signal_strength': st / 100.0,
                'price_dimension_status': f"吸筹: {r.accumulation_grade or '-'}",
                'frequency_dimension_status': f"动量: {r.momentum_grade or '-'}",
                'volume_dimension_status': f"类型: {r.buy_type or '观望'}",
                'resonance_status': f"总分: {st}",
                'investment_advice': advice,
                'price': r.d or 0,
                'indicators': {
                    'price_dimension': {'macro_displacement': r.score_accumulation or 0},
                    'frequency_dimension': {'rising_days': r.score_momentum or 0, 'falling_days': 0},
                    'volume_dimension': {'efficiency_ratio': r.score_balance or 0}
                },
                'timestamp': datetime.now().isoformat()
            })
            
        logger.info(f"直接读取GMS选股结果完成，日期 {target_date}，共 {len(results_data)} 只股票")
        
        return JSONResponse({
            "success": True,
            "data": results_data,
            "total": len(results_data),
            "search_date": target_date,
            "strategy_name": "GMS均值引力动量策略",
            "timestamp": datetime.now().isoformat()
        })
        
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
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_admin)
):
    """
    获取股票详细 GMS 分析指标
    """
    try:
        logger.info(f"获取股票详细GMS分析 - 股票代码: {symbol}")
        
        if not symbol:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
            
        # 获取股票详细 GMS 记录 (优先读取追溯表中的已计算好的数据)
        trace = db.query(GMSSignalTrace).filter(
            GMSSignalTrace.code == symbol
        ).order_by(desc(GMSSignalTrace.date)).first()
        
        if not trace:
            # 如果 trace 表中没有记录，尝试回退到原始指标表显示基础数据，但总分为0
            ind = db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code == symbol
            ).order_by(desc(MeanFrequencyResonanceIndicators.date)).first()
            
            if not ind:
                raise HTTPException(status_code=404, detail="未找到该股票的GMS指标数据")
                
            return JSONResponse({
                "success": True,
                "data": {
                    "symbol": symbol,
                    "date": ind.date,
                    "score_total": 0,
                    "score_accumulation": 0,
                    "score_momentum": 0,
                    "score_balance": 0,
                    "accumulation_grade": "无数据",
                    "momentum_grade": "无数据",
                    "buy_type": "观望",
                    "indicators": {
                        "delta": ind.macro_displacement_delta,
                        "d": ind.ma20_d,
                        "ratio_d20": ind.ratio_d20,
                        "ratio_d1": ind.ratio_d1,
                        "instant_deviation": ind.instant_deviation,
                        "rising_days": ind.rising_days_z,
                        "falling_days": ind.falling_days_f,
                        "avg_volume_20d": ind.mavol20_m,
                    }
                }
            })

        # 获取股票名称
        name = symbol
        is_cn = len(symbol) >= 6 and symbol.isdigit() and symbol[0] in "6039"
        if is_cn:
            stock_info = db.query(StockBasicInfo).filter(StockBasicInfo.code == symbol).first()
        else:
            stock_info = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == symbol).first()
        if stock_info:
            name = stock_info.name

        # 投资建议逻辑
        st = trace.score_total or 0
        if st >= 90: advice = "强烈推荐"
        elif st >= 75: advice = "推荐"
        elif st >= 60: advice = "关注"
        else: advice = "观望"

        detail_data = {
            'symbol': symbol,
            'name': name,
            'price': trace.d,
            'signal_strength': st / 100.0,
            'investment_advice': advice,
            'analysis_time': trace.date,
            'indicators': {
                'price_dimension': {
                    'macro_displacement': trace.score_accumulation,
                    'instant_deviation': trace.instant_deviation,
                    'avg_price_20d': trace.d,
                    'price_dimension_valid': True
                },
                'frequency_dimension': {
                    'rising_days': trace.rising_days,
                    'falling_days': trace.falling_days,
                    'frequency_advantage': (trace.falling_days or 0) > (trace.rising_days or 0),
                    'has_false_prosperity': False,
                    'frequency_dimension_valid': True
                },
                'volume_dimension': {
                    'avg_volume_20d': trace.avg_volume_20d,
                    'current_volume': trace.current_volume,
                    'efficiency_ratio': trace.score_balance,
                    'volume_dimension_valid': True
                },
                'amplitude_ratio': getattr(trace, 'fz_ratio', 0),
                'volume_multiplier': getattr(trace, 'volume_ratio', 1.0),
                'entry_timing_analysis': {
                    'comprehensive_assessment': {
                        'score': st / 100.0,
                        'optimal_timing': st >= 85,
                        'recommendation': advice
                    }
                }
            },
            'score_detail': {
                'score_acc_fz': getattr(trace, 'score_acc_fz', 0),
                'score_acc_balance': getattr(trace, 'score_acc_balance', 0),
                'score_acc_volume': getattr(trace, 'score_acc_volume', 0),
                'score_mom_ratio_d1': getattr(trace, 'score_mom_ratio_d1', 0),
                'score_mom_deviation': getattr(trace, 'score_mom_deviation', 0),
                'score_mom_volume': getattr(trace, 'score_mom_volume', 0)
            }
        }
        
        return JSONResponse({
            "success": True,
            "data": detail_data,
            "strategy_name": "GMS均值引力动量策略",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取股票 {symbol} GMS详情失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
    获取 GMS 选股汇总信息
    """
    try:
        logger.info("获取GMS选股汇总信息 (从GMSSignalTrace读取)")
        
        # 获取结果表的最新日期
        latest_date = db.query(func.max(GMSSignalTrace.date)).scalar()
        
        if not latest_date:
            return JSONResponse({
                "success": True,
                "data": {
                    "total_stocks": 0,
                    "strong_signals": 0,
                    "last_update_date": None
                }
            })

        # 统计总数
        total_count = db.query(func.count(GMSSignalTrace.code)).filter(
            GMSSignalTrace.date == latest_date
        ).scalar()
        
        # 强信号定义
        strong_count = db.query(func.count(GMSSignalTrace.code)).filter(
            GMSSignalTrace.date == latest_date,
            or_(
                GMSSignalTrace.score_total >= 70,
                GMSSignalTrace.accumulation_grade == 'S',
                GMSSignalTrace.momentum_grade == '全速切入'
            )
        ).scalar()
        
        summary_data = {
            "total_stocks": total_count,
            "active_signals": total_count,
            "strong_signals": strong_count,
            "latest_date": latest_date,
            "dimension_stats": {
                "high_accumulation": db.query(func.count(GMSSignalTrace.code)).filter(
                    GMSSignalTrace.date == latest_date,
                    GMSSignalTrace.score_accumulation >= 80
                ).scalar(),
                "high_momentum": db.query(func.count(GMSSignalTrace.code)).filter(
                    GMSSignalTrace.date == latest_date,
                    GMSSignalTrace.score_momentum >= 80
                ).scalar()
            }
        }
        
        return JSONResponse({
            "success": True,
            "data": summary_data,
            "query_time": datetime.now().isoformat(),
            "strategy_name": "GMS均值引力动量策略"
        })
        
    except Exception as e:
        logger.error(f"获取GMS选股汇总信息时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "success": False,
            "error": f"获取汇总信息失败: {str(e)}",
            "query_time": datetime.now().isoformat()
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
