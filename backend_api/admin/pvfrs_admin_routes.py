"""
PVFRS策略管理端API路由
提供管理端回测功能和策略管理接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Dict, Optional
import logging
import traceback
import json

from backend_api.database import get_db
from backend_core.strategies.pvfrs.admin_interface import (
    AdminInterface, BacktestConfig, BacktestTask, BacktestReport, 
    create_admin_interface
)
from backend_core.strategies.pvfrs.models import PVFRSException
from backend_core.strategies.pvfrs.serialization import get_formatter, validate_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pvfrs", tags=["PVFRS管理端接口"])

# 全局管理端接口实例
_admin_interface: Optional[AdminInterface] = None


def get_admin_interface() -> AdminInterface:
    """获取管理端接口实例"""
    global _admin_interface
    if _admin_interface is None:
        _admin_interface = create_admin_interface()
    return _admin_interface


@router.post("/backtest/create")
async def create_backtest_task(
    config_data: Dict = Body(..., description="回测配置"),
    db: Session = Depends(get_db)
):
    """
    创建回测任务
    
    Args:
        config_data: 回测配置数据
        db: 数据库会话
    
    Returns:
        创建的任务信息
    """
    try:
        logger.info("创建PVFRS回测任务")
        
        # 验证必需字段
        required_fields = ['start_date', 'end_date', 'stock_pool', 'initial_capital']
        for field in required_fields:
            if field not in config_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"缺少必需字段: {field}"
                )
        
        # 构建回测配置
        backtest_config = BacktestConfig(
            start_date=config_data['start_date'],
            end_date=config_data['end_date'],
            stock_pool=config_data['stock_pool'],
            initial_capital=float(config_data['initial_capital']),
            strategy_params=config_data.get('strategy_params', {}),
            risk_params=config_data.get('risk_params', {})
        )
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 创建回测任务
        task_id = admin_interface.create_backtest(backtest_config)
        
        # 开始执行任务
        execution_started = admin_interface.start_backtest_execution(task_id)
        
        logger.info(f"PVFRS回测任务创建成功: {task_id}")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_success_response(
            {
                "task_id": task_id,
                "execution_started": execution_started,
                "created_at": datetime.now().isoformat()
            },
            message="回测任务创建成功"
        )
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"创建PVFRS回测任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建回测任务失败: {str(e)}"
        )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"创建PVFRS回测任务时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建回测任务时发生未知错误: {str(e)}"
        )


@router.get("/backtest/progress/{task_id}")
async def get_backtest_progress(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    获取回测任务进度
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        回测任务进度信息
    """
    try:
        logger.info(f"获取PVFRS回测任务进度: {task_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取任务进度
        progress_info = admin_interface.get_backtest_progress(task_id)
        
        logger.info(f"PVFRS回测任务进度获取成功: {task_id}")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_task_progress(progress_info)
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"获取PVFRS回测任务进度失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取回测任务进度失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"获取PVFRS回测任务进度时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测任务进度时发生未知错误: {str(e)}"
        )


@router.get("/backtest/report/{task_id}")
async def get_backtest_report(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    获取回测报告
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        回测报告详细信息
    """
    try:
        logger.info(f"获取PVFRS回测报告: {task_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取回测报告
        report = admin_interface.get_backtest_report(task_id)
        
        # 转换为API响应格式
        report_data = report.to_dict()
        
        logger.info(f"PVFRS回测报告获取成功: {task_id}")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_backtest_report(report_data)
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"获取PVFRS回测报告失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取回测报告失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"获取PVFRS回测报告时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测报告时发生未知错误: {str(e)}"
        )


@router.post("/backtest/compare")
async def compare_backtest_reports(
    report_ids: List[str] = Body(..., description="要对比的报告ID列表"),
    db: Session = Depends(get_db)
):
    """
    对比多个回测报告
    
    Args:
        report_ids: 报告ID列表
        db: 数据库会话
    
    Returns:
        策略对比结果
    """
    try:
        logger.info(f"对比PVFRS回测报告: {report_ids}")
        
        # 参数验证
        if not report_ids or len(report_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要2个报告进行对比"
            )
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 执行对比
        comparison_result = admin_interface.compare_strategies(report_ids)
        
        logger.info(f"PVFRS回测报告对比完成: {len(report_ids)} 个报告")
        
        return JSONResponse({
            "success": True,
            "data": comparison_result,
            "query_time": datetime.now().isoformat()
        })
        
    except PVFRSException as e:
        logger.error(f"对比PVFRS回测报告失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"对比回测报告失败: {str(e)}"
        )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"对比PVFRS回测报告时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对比回测报告时发生未知错误: {str(e)}"
        )


@router.get("/backtest/reports")
async def list_backtest_reports(
    limit: int = Query(50, ge=1, le=100, description="返回数量限制，默认50"),
    db: Session = Depends(get_db)
):
    """
    获取历史回测报告列表
    
    Args:
        limit: 返回数量限制
        db: 数据库会话
    
    Returns:
        历史回测报告列表
    """
    try:
        logger.info(f"获取PVFRS历史回测报告列表，限制: {limit}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取历史报告
        reports = admin_interface.list_historical_reports(limit)
        
        # 转换为API响应格式
        reports_data = [report.to_dict() for report in reports]
        
        logger.info(f"PVFRS历史回测报告列表获取成功，返回 {len(reports_data)} 个报告")
        
        return JSONResponse({
            "success": True,
            "data": reports_data,
            "total": len(reports_data),
            "limit": limit,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS历史回测报告列表时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史回测报告列表失败: {str(e)}"
        )


@router.get("/backtest/tasks")
async def list_backtest_tasks(
    status_filter: Optional[str] = Query(None, description="状态过滤器：pending, running, completed, failed, cancelled"),
    db: Session = Depends(get_db)
):
    """
    获取回测任务列表
    
    Args:
        status_filter: 状态过滤器
        db: 数据库会话
    
    Returns:
        回测任务列表
    """
    try:
        logger.info(f"获取PVFRS回测任务列表，状态过滤: {status_filter or '全部'}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取任务列表
        tasks = admin_interface.get_task_list(status_filter)
        
        logger.info(f"PVFRS回测任务列表获取成功，返回 {len(tasks)} 个任务")
        
        return JSONResponse({
            "success": True,
            "data": tasks,
            "total": len(tasks),
            "status_filter": status_filter,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS回测任务列表时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测任务列表失败: {str(e)}"
        )


@router.post("/backtest/cancel/{task_id}")
async def cancel_backtest_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    取消回测任务
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        取消操作结果
    """
    try:
        logger.info(f"取消PVFRS回测任务: {task_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 取消任务
        cancel_success = admin_interface.cancel_backtest(task_id)
        
        if cancel_success:
            logger.info(f"PVFRS回测任务取消成功: {task_id}")
            return JSONResponse({
                "success": True,
                "message": "回测任务取消成功",
                "task_id": task_id,
                "cancelled_at": datetime.now().isoformat()
            })
        else:
            logger.warning(f"PVFRS回测任务取消失败: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="回测任务取消失败"
            )
        
    except PVFRSException as e:
        logger.error(f"取消PVFRS回测任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"取消回测任务失败: {str(e)}"
        )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"取消PVFRS回测任务时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消回测任务时发生未知错误: {str(e)}"
        )


@router.get("/interface-status")
async def get_admin_interface_status(
    db: Session = Depends(get_db)
):
    """
    获取管理端接口状态
    
    Args:
        db: 数据库会话
    
    Returns:
        管理端接口状态信息
    """
    try:
        logger.info("获取PVFRS管理端接口状态")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取接口状态
        status_data = admin_interface.get_interface_status()
        
        logger.info("PVFRS管理端接口状态获取成功")
        
        return JSONResponse({
            "success": True,
            "data": status_data,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS管理端接口状态时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取管理端接口状态失败: {str(e)}"
        )


@router.post("/config/strategy")
async def update_strategy_config(
    strategy_params: Dict = Body(..., description="策略参数配置"),
    db: Session = Depends(get_db)
):
    """
    更新策略配置
    
    Args:
        strategy_params: 策略参数
        db: 数据库会话
    
    Returns:
        配置更新结果
    """
    try:
        logger.info("更新PVFRS策略配置")
        
        # 这里可以添加策略配置的验证和保存逻辑
        # 暂时只返回成功响应
        
        logger.info("PVFRS策略配置更新成功")
        
        return JSONResponse({
            "success": True,
            "message": "策略配置更新成功",
            "config": strategy_params,
            "updated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"更新PVFRS策略配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新策略配置失败: {str(e)}"
        )


@router.post("/config/risk")
async def update_risk_config(
    risk_params: Dict = Body(..., description="风险管理参数配置"),
    db: Session = Depends(get_db)
):
    """
    更新风险管理配置
    
    Args:
        risk_params: 风险管理参数
        db: 数据库会话
    
    Returns:
        配置更新结果
    """
    try:
        logger.info("更新PVFRS风险管理配置")
        
        # 这里可以添加风险配置的验证和保存逻辑
        # 暂时只返回成功响应
        
        logger.info("PVFRS风险管理配置更新成功")
        
        return JSONResponse({
            "success": True,
            "message": "风险管理配置更新成功",
            "config": risk_params,
            "updated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"更新PVFRS风险管理配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新风险管理配置失败: {str(e)}"
        )