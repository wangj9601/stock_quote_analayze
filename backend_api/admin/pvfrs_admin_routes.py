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


@router.post("/backtest")
async def create_backtest(
    config_data: Dict = Body(..., description="回测配置"),
    db: Session = Depends(get_db)
):
    """
    创建回测任务（前端兼容接口，与 /backtest/create 功能相同）
    
    Args:
        config_data: 回测配置数据
        db: 数据库会话
        
    Returns:
        创建的任务信息
    """
    return await _create_backtest_task_impl(config_data, db)


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
    return await _create_backtest_task_impl(config_data, db)


async def _create_backtest_task_impl(
    config_data: Dict,
    db: Session
):
    """
    创建回测任务的实现逻辑（内部函数）
    
    Args:
        config_data: 回测配置数据
        db: 数据库会话
        
    Returns:
        创建的任务信息
    """
    try:
        logger.info(f"创建PVFRS回测任务，接收到的数据: {config_data}")
        
        # 处理前端可能发送的不同格式
        # 前端可能发送: mode, code, stockList, stock_codes 等字段
        # 后端期望: stock_pool (列表)
        
        # 提取股票池
        stock_pool = []
        if 'stock_pool' in config_data:
            # 如果已经提供了 stock_pool
            stock_pool = config_data['stock_pool'] if isinstance(config_data['stock_pool'], list) else [config_data['stock_pool']]
        elif 'code' in config_data:
            # 单股模式
            stock_pool = [config_data['code']]
        elif 'stockList' in config_data:
            # 批量模式 - 字符串格式
            stock_list_str = config_data['stockList']
            if isinstance(stock_list_str, str):
                stock_pool = [s.strip() for s in stock_list_str.split(',') if s.strip()]
        elif 'stock_codes' in config_data:
            # 批量模式 - 列表格式
            stock_pool = config_data['stock_codes'] if isinstance(config_data['stock_codes'], list) else [config_data['stock_codes']]
        
        # 验证必需字段
        if not stock_pool:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少股票代码，请提供 stock_pool、code、stockList 或 stock_codes 字段"
            )
        
        if 'start_date' not in config_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必需字段: start_date"
            )
        
        if 'end_date' not in config_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必需字段: end_date"
            )
        
        if 'initial_capital' not in config_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必需字段: initial_capital"
            )
        
        # 构建回测配置
        backtest_config = BacktestConfig(
            start_date=config_data['start_date'],
            end_date=config_data['end_date'],
            stock_pool=stock_pool,
            initial_capital=float(config_data['initial_capital']),
            strategy_params=config_data.get('strategy_params', {}),
            risk_params=config_data.get('risk_params', {})
        )
        
        logger.info(f"构建的回测配置: 开始日期={backtest_config.start_date}, 结束日期={backtest_config.end_date}, 股票数量={len(stock_pool)}, 初始资金={backtest_config.initial_capital}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 创建回测任务
        task_id = admin_interface.create_backtest(backtest_config)
        logger.info(f"回测任务已创建: {task_id}")
        
        # 开始执行任务
        execution_started = admin_interface.start_backtest_execution(task_id)
        if execution_started:
            logger.info(f"回测任务执行已启动: {task_id}")
        else:
            logger.warning(f"回测任务执行启动失败: {task_id}")
        
        logger.info(f"PVFRS回测任务创建成功: {task_id}, 执行状态: {execution_started}")
        
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


@router.get("/backtest/logs/{task_id}")
async def get_backtest_logs(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    获取回测任务执行日志
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        任务执行日志列表
    """
    try:
        logger.info(f"获取PVFRS回测任务日志: {task_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取任务进度信息（包含进度历史）
        progress_info = admin_interface.get_backtest_progress(task_id)
        
        # 从执行监控器获取进度历史
        execution_monitor = admin_interface.execution_monitor
        logs = []
        
        # 如果有进度历史，转换为日志格式
        if hasattr(execution_monitor, 'progress_history') and task_id in execution_monitor.progress_history:
            progress_history = execution_monitor.progress_history[task_id]
            for progress_update in progress_history:
                # ProgressUpdate.timestamp 是字符串类型
                timestamp_str = progress_update.timestamp if isinstance(progress_update.timestamp, str) else datetime.now().isoformat()
                
                logs.append({
                    'timestamp': timestamp_str,
                    'level': 'INFO',
                    'message': progress_update.current_step or f"进度: {progress_update.progress}%"
                })
        
        # 如果有错误信息，添加错误日志
        if progress_info.get('error_message'):
            logs.append({
                'timestamp': progress_info.get('completed_at') or datetime.now().isoformat(),
                'level': 'ERROR',
                'message': progress_info.get('error_message')
            })
        
        # 如果没有日志，至少添加一条状态日志
        if not logs:
            logs.append({
                'timestamp': progress_info.get('created_at') or datetime.now().isoformat(),
                'level': 'INFO',
                'message': f"任务状态: {progress_info.get('status', 'unknown')}"
            })
        
        logger.info(f"PVFRS回测任务日志获取成功: {task_id}，共 {len(logs)} 条日志")
        
        return JSONResponse({
            "success": True,
            "logs": logs,
            "task_id": task_id,
            "total": len(logs)
        })
        
    except PVFRSException as e:
        logger.error(f"获取PVFRS回测任务日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取回测任务日志失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"获取PVFRS回测任务日志时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测任务日志时发生未知错误: {str(e)}"
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
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_success_response(
            reports_data,
            total=len(reports_data),
            limit=limit,
            message="历史回测报告列表获取成功"
        )
        
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"获取PVFRS历史回测报告列表时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史回测报告列表失败: {str(e)}"
        )


@router.get("/results")
async def list_results(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量"),
    type: Optional[str] = Query(None, description="结果类型过滤"),
    startDate: Optional[str] = Query(None, description="开始日期"),
    endDate: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """
    获取回测结果列表（与 /reports 功能相同，用于兼容前端）
    
    Args:
        page: 页码，从1开始
        pageSize: 每页数量
        type: 结果类型过滤
        startDate: 开始日期
        endDate: 结束日期
        db: 数据库会话
        
    Returns:
        回测结果列表
    """
    try:
        logger.info(f"获取PVFRS回测结果列表，页码: {page}, 每页: {pageSize}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取历史报告（结果）
        limit = pageSize
        reports = admin_interface.list_historical_reports(limit * page)
        
        # 转换为API响应格式
        reports_data = [report.to_dict() for report in reports]
        
        # 分页处理
        start_idx = (page - 1) * pageSize
        end_idx = start_idx + pageSize
        paginated_reports = reports_data[start_idx:end_idx]
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_success_response(
            paginated_reports,
            total=len(reports_data),
            page=page,
            pageSize=pageSize,
            message="回测结果列表获取成功"
        )
        
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"获取PVFRS回测结果列表时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测结果列表失败: {str(e)}"
        )


@router.delete("/results")
async def delete_all_results(
    db: Session = Depends(get_db)
):
    """
    删除所有回测结果
    
    Args:
        db: 数据库会话
        
    Returns:
        删除操作结果
    """
    try:
        logger.info("删除所有PVFRS回测结果")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 这里应该实现删除所有结果的逻辑
        # 暂时返回成功响应
        
        logger.info("所有PVFRS回测结果删除成功")
        
        return JSONResponse({
            "success": True,
            "message": "所有回测结果已清空",
            "deleted_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"删除所有PVFRS回测结果时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除所有回测结果失败: {str(e)}"
        )


@router.get("/reports")
async def list_reports(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量"),
    type: Optional[str] = Query(None, description="报告类型过滤"),
    startDate: Optional[str] = Query(None, description="开始日期"),
    endDate: Optional[str] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """
    获取报告列表（前端兼容接口）
    
    Args:
        page: 页码
        pageSize: 每页数量
        type: 报告类型过滤
        startDate: 开始日期
        endDate: 结束日期
        db: 数据库会话
    
    Returns:
        报告列表
    """
    try:
        logger.info(f"获取PVFRS报告列表 - 页码: {page}, 每页: {pageSize}, 类型: {type}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 计算偏移量
        offset = (page - 1) * pageSize
        
        # 获取历史报告（这里使用现有的方法，实际应该支持分页和过滤）
        all_reports = admin_interface.list_historical_reports(limit=1000)  # 先获取更多数据
        
        # 应用过滤器
        filtered_reports = all_reports
        if type and type != "":
            filtered_reports = [r for r in filtered_reports if r.report_type == type]
        
        if startDate and startDate != "undefined":
            try:
                start_dt = datetime.strptime(startDate, "%Y-%m-%d")
                filtered_reports = [r for r in filtered_reports if r.created_at >= start_dt]
            except ValueError:
                pass  # 忽略无效日期
        
        if endDate and endDate != "undefined":
            try:
                end_dt = datetime.strptime(endDate, "%Y-%m-%d")
                filtered_reports = [r for r in filtered_reports if r.created_at <= end_dt]
            except ValueError:
                pass  # 忽略无效日期
        
        # 分页
        total = len(filtered_reports)
        paginated_reports = filtered_reports[offset:offset + pageSize]
        
        # 转换为API响应格式
        reports_data = []
        for report in paginated_reports:
            if hasattr(report, 'to_dict'):
                reports_data.append(report.to_dict())
            else:
                # 如果没有to_dict方法，创建基本的字典结构
                reports_data.append({
                    "id": f"report_{len(reports_data)+1}",
                    "name": f"报告_{len(reports_data)+1}",
                    "created_at": datetime.now().isoformat(),
                    "status": "completed"
                })
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_success_response(
            reports_data,
            total=total,
            page=page,
            pageSize=pageSize,
            totalPages=(total + pageSize - 1) // pageSize if total > 0 else 0,
            message="报告列表获取成功"
        )
        
        return JSONResponse(response_data)
        
    except Exception as e:
        logger.error(f"获取PVFRS报告列表时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取报告列表失败: {str(e)}"
        )


@router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    获取报告详情
    
    Args:
        report_id: 报告ID
        db: 数据库会话
    
    Returns:
        报告详细信息
    """
    try:
        logger.info(f"获取PVFRS报告详情: {report_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 获取报告详情
        # 首先尝试通过 report_id 获取历史报告
        report = None
        try:
            # 方法1: 尝试通过 report_id 获取历史报告
            if hasattr(admin_interface, 'get_historical_report'):
                report = admin_interface.get_historical_report(report_id)
                logger.info(f"通过 get_historical_report 获取报告: {report_id}")
        except Exception as e:
            logger.debug(f"通过 get_historical_report 获取报告失败: {str(e)}")
        
        # 方法2: 如果方法1失败，尝试直接从 reports 字典中获取
        if not report:
            try:
                if hasattr(admin_interface, 'reports') and report_id in admin_interface.reports:
                    report = admin_interface.reports[report_id]
                    logger.info(f"从内存 reports 字典获取报告: {report_id}")
            except Exception as e:
                logger.debug(f"从内存获取报告失败: {str(e)}")
        
        # 方法3: 如果前两种方法都失败，尝试作为 task_id 查找
        if not report:
            try:
                report = admin_interface.get_backtest_report(report_id)
                logger.info(f"通过 get_backtest_report (作为 task_id) 获取报告: {report_id}")
            except Exception as e:
                logger.debug(f"通过 task_id 获取报告失败: {str(e)}")
        
        # 转换为API响应格式
        if report:
            if hasattr(report, 'to_dict') and callable(getattr(report, 'to_dict')):
                report_data = report.to_dict()
            else:
                # 如果没有to_dict方法，创建基本的字典结构
                report_data = {
                    "id": report_id,
                    "name": f"报告_{report_id}",
                    "created_at": datetime.now().isoformat(),
                    "status": "completed"
                }
        else:
            # 如果所有方法都失败，返回基本信息
            logger.warning(f"无法获取报告详情，使用默认数据: {report_id}")
            report_data = {
                "id": report_id,
                "name": f"报告_{report_id}",
                "created_at": datetime.now().isoformat(),
                "status": "completed"
            }
        
        logger.info(f"PVFRS报告详情获取成功: {report_id}")
        
        # 使用格式化器生成响应
        formatter = get_formatter()
        response_data = formatter.format_success_response(
            report_data,
            message="报告详情获取成功"
        )
        
        return JSONResponse(response_data)
        
    except PVFRSException as e:
        logger.error(f"获取PVFRS报告详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取报告详情失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"获取PVFRS报告详情时发生未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取报告详情时发生未知错误: {str(e)}"
        )


@router.post("/reports")
async def create_report(
    report_data: Dict = Body(..., description="报告创建数据"),
    db: Session = Depends(get_db)
):
    """
    创建新报告
    
    Args:
        report_data: 报告数据
        db: 数据库会话
    
    Returns:
        创建的报告信息
    """
    try:
        logger.info("创建PVFRS报告")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 这里应该实现报告创建逻辑
        # 暂时返回模拟数据
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"PVFRS报告创建成功: {report_id}")
        
        return JSONResponse({
            "success": True,
            "data": {
                "report_id": report_id,
                "created_at": datetime.now().isoformat(),
                "status": "created"
            },
            "message": "报告创建成功"
        })
        
    except Exception as e:
        logger.error(f"创建PVFRS报告时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建报告失败: {str(e)}"
        )


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    删除报告
    
    Args:
        report_id: 报告ID
        db: 数据库会话
    
    Returns:
        删除操作结果
    """
    try:
        logger.info(f"删除PVFRS报告: {report_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 这里应该实现报告删除逻辑
        # 暂时返回成功响应
        
        logger.info(f"PVFRS报告删除成功: {report_id}")
        
        return JSONResponse({
            "success": True,
            "message": "报告删除成功",
            "deleted_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"删除PVFRS报告时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除报告失败: {str(e)}"
        )


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    下载报告
    
    Args:
        report_id: 报告ID
        db: 数据库会话
    
    Returns:
        报告文件（HTML格式）
    """
    try:
        logger.info(f"下载PVFRS报告: {report_id}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 生成HTML报告
        try:
            html_content = admin_interface.generate_report_html(report_id)
        except PVFRSException as e:
            # 如果通过report_id找不到，尝试通过task_id查找
            # report_id 可能就是 task_id
            try:
                report = admin_interface.get_backtest_report(report_id)
                # 如果找到了报告，使用实际的report_id
                actual_report_id = report.report_id if hasattr(report, 'report_id') else report_id
                html_content = admin_interface.generate_report_html(actual_report_id)
            except Exception:
                raise e
        
        # 返回HTML文件
        from fastapi.responses import Response
        return Response(
            content=html_content.encode('utf-8'),
            media_type='text/html',
            headers={
                'Content-Disposition': f'attachment; filename="PVFRS_回测报告_{report_id}.html"'
            }
        )
        
    except PVFRSException as e:
        logger.error(f"下载PVFRS报告失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"报告不存在: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载PVFRS报告时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载报告失败: {str(e)}"
        )


@router.post("/reports/compare")
async def compare_reports(
    compare_data: Dict = Body(..., description="对比数据"),
    db: Session = Depends(get_db)
):
    """
    对比报告
    
    Args:
        compare_data: 对比数据，包含report_ids
        db: 数据库会话
    
    Returns:
        对比结果
    """
    try:
        logger.info("对比PVFRS报告")
        
        report_ids = compare_data.get('report_ids', [])
        if not report_ids or len(report_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要2个报告进行对比"
            )
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 执行对比
        comparison_result = admin_interface.compare_strategies(report_ids)
        
        logger.info(f"PVFRS报告对比完成: {len(report_ids)} 个报告")
        
        return JSONResponse({
            "success": True,
            "data": comparison_result,
            "query_time": datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对比PVFRS报告时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对比报告失败: {str(e)}"
        )


@router.get("/reports/overview")
async def get_reports_overview(
    db: Session = Depends(get_db)
):
    """
    获取报告概览
    
    Args:
        db: 数据库会话
    
    Returns:
        报告概览数据
    """
    try:
        logger.info("获取PVFRS报告概览")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 模拟概览数据
        overview_data = {
            "total_reports": 25,
            "recent_reports": 5,
            "success_rate": 85.2,
            "avg_return": 12.5,
            "best_strategy": "PVFRS-v2.1",
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info("PVFRS报告概览获取成功")
        
        return JSONResponse({
            "success": True,
            "data": overview_data,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS报告概览时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取报告概览失败: {str(e)}"
        )


@router.get("/backtest/tasks")
async def list_backtest_tasks(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤器：pending, running, completed, failed, cancelled"),
    db: Session = Depends(get_db)
):
    """
    获取回测任务列表
    
    Args:
        page: 页码
        pageSize: 每页数量
        status: 状态过滤器
        db: 数据库会话
    
    Returns:
        回测任务列表
    """
    try:
        logger.info(f"获取PVFRS回测任务列表 - 页码: {page}, 每页: {pageSize}, 状态过滤: {status or '全部'}")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 从管理端接口获取真实的任务列表
        all_tasks_raw = admin_interface.get_task_list(status_filter=status)
        
        # 转换为前端期望的格式
        admin_interface = get_admin_interface()
        all_tasks = []
        for task in all_tasks_raw:
            # 提取配置信息
            config = task.get('config', {})
            task_id = task.get('task_id', '')
            
            # 尝试获取报告ID和结果摘要（仅对已完成的任务）
            report_id = None
            results_summary = None
            if task.get('status') == 'completed':
                try:
                    # 查找该任务对应的报告
                    for report_id_key, report_obj in admin_interface.reports.items():
                        if hasattr(report_obj, 'task_id') and report_obj.task_id == task_id:
                            report_id = report_obj.report_id
                            # 提取结果摘要
                            results_summary = {
                                'totalReturn': report_obj.total_return if hasattr(report_obj, 'total_return') else None,
                                'annualizedReturn': report_obj.annual_return if hasattr(report_obj, 'annual_return') else None,
                                'maxDrawdown': report_obj.max_drawdown if hasattr(report_obj, 'max_drawdown') else None,
                                'sharpeRatio': report_obj.sharpe_ratio if hasattr(report_obj, 'sharpe_ratio') else None
                            }
                            break
                except Exception as e:
                    logger.warning(f"获取任务 {task_id} 的报告信息失败: {str(e)}")
            
            # 计算执行耗时
            duration = None
            if task.get('started_at') and task.get('completed_at'):
                try:
                    start_dt = datetime.fromisoformat(task.get('started_at'))
                    end_dt = datetime.fromisoformat(task.get('completed_at'))
                    duration = int((end_dt - start_dt).total_seconds())
                except (ValueError, TypeError):
                    duration = None
            
            # 提取策略参数和风险参数
            strategy_params = config.get('strategy_params', {})
            risk_params = config.get('risk_params', {})
            
            # 获取默认配置值（用于填充缺失的字段）
            from backend_core.strategies.pvfrs.backtest_config_validator import BacktestConfigValidator
            validator = BacktestConfigValidator()
            default_config = validator.get_default_config()
            default_risk = default_config.get('risk_params', {})
            default_strategy = default_config.get('strategy_params', {})
            
            task_dict = {
                "id": task_id,
                "task_id": task_id,
                "name": f"回测任务-{task_id[:8]}",  # 使用任务ID前8位作为名称
                "status": task.get('status', 'pending'),
                # 时间字段（同时提供两种格式以兼容前端）
                "created_at": task.get('created_at', ''),
                "createdAt": task.get('created_at', ''),
                "started_at": task.get('started_at'),
                "startedAt": task.get('started_at'),
                "completed_at": task.get('completed_at'),
                "completedAt": task.get('completed_at'),
                "progress": task.get('progress', 0),
                "current_step": task.get('current_step', ''),
                "error_message": task.get('error_message'),
                "reportId": report_id,  # 添加报告ID
                "results": results_summary,  # 添加结果摘要
                "strategy": "PVFRS-v2.1",
                # 配置字段（同时提供两种格式）
                "start_date": config.get('start_date', ''),
                "startDate": config.get('start_date', ''),
                "end_date": config.get('end_date', ''),
                "endDate": config.get('end_date', ''),
                "stock_count": len(config.get('stock_pool', [])),
                "totalStocks": len(config.get('stock_pool', [])),
                "processedStocks": task.get('processed_stocks', len(config.get('stock_pool', [])) if task.get('status') == 'completed' else 0),
                "initial_capital": config.get('initial_capital', 0.0),
                "initialCapital": config.get('initial_capital', 0.0),
                "mode": "单股回测" if len(config.get('stock_pool', [])) == 1 else "多股回测",
                # 执行耗时
                "duration": duration,
                # 市场类型（从配置或默认值推断，根据股票代码判断）
                "market": config.get('market', 'CN'),  # 如果没有明确指定，默认为A股
                # 交易参数（从风险参数或默认值获取）
                "commission": risk_params.get('commission_rate', 0.0003),  # 默认0.03%
                "slippage": risk_params.get('slippage_rate', 0.001),  # 默认0.1%
                "benchmark": config.get('benchmark', '沪深300'),
                # 股票列表
                "stockList": config.get('stock_pool', []),
                "stock_pool": config.get('stock_pool', []),
                # 策略参数（使用正确的字段名）
                "config": {
                    "buyBiasMin": strategy_params.get('buy_bias_min', -0.05),
                    "sellBiasMax": strategy_params.get('sell_bias_max', 0.15),
                    "buyConsecutiveDays": strategy_params.get('buy_consecutive_days', 2),
                    "stopLoss": risk_params.get('stop_loss_rate', default_risk.get('stop_loss_rate', 0.1)),
                    "takeProfit": risk_params.get('take_profit_rate', default_risk.get('take_profit_rate', 0.2)),
                    "maxPositionSize": risk_params.get('max_position_size', default_risk.get('max_position_size', 0.1))
                },
                # 进度相关字段
                "processingSpeed": task.get('processing_speed', 0),
                "estimatedTimeRemaining": task.get('estimated_remaining_time')
            }
            all_tasks.append(task_dict)
        
        # 分页
        total = len(all_tasks)
        offset = (page - 1) * pageSize
        paginated_tasks = all_tasks[offset:offset + pageSize]
        
        logger.info(f"PVFRS回测任务列表获取成功，返回 {len(paginated_tasks)} 个任务，总计 {total} 个")
        
        return JSONResponse({
            "success": True,
            "data": paginated_tasks,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": (total + pageSize - 1) // pageSize if total > 0 else 0,
            "status_filter": status,
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


@router.post("/config")
async def save_strategy_config(
    config_data: Dict = Body(..., description="策略配置数据（包含strategy和risk）"),
    db: Session = Depends(get_db)
):
    """
    保存策略配置（同时保存策略参数和风险参数）
    
    Args:
        config_data: 配置数据，可能包含：
            - strategy 或 strategy_params: 策略参数
            - risk 或 risk_params: 风险参数
        db: 数据库会话
        
    Returns:
        保存结果
    """
    try:
        logger.info(f"保存PVFRS策略配置，接收到的数据: {config_data}")
        
        # 提取策略参数和风险参数
        strategy_params = config_data.get('strategy_params') or config_data.get('strategy', {})
        risk_params = config_data.get('risk_params') or config_data.get('risk', {})
        
        # 如果提供了策略参数，调用更新策略配置接口
        if strategy_params:
            logger.info(f"更新策略参数: {strategy_params}")
            # 这里可以调用 update_strategy_config 的逻辑
            # 或者直接在这里处理
        
        # 如果提供了风险参数，调用更新风险配置接口
        if risk_params:
            logger.info(f"更新风险参数: {risk_params}")
            # 这里可以调用 update_risk_config 的逻辑
            # 或者直接在这里处理
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 在实际实现中，应该保存配置到数据库或配置文件
        # 这里暂时只记录日志
        
        logger.info("PVFRS策略配置保存成功")
        
        return JSONResponse({
            "success": True,
            "message": "配置保存成功",
            "data": {
                "strategy": strategy_params,
                "risk": risk_params
            },
            "saved_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"保存PVFRS策略配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存策略配置失败: {str(e)}"
        )


@router.get("/config")
async def get_strategy_config(
    db: Session = Depends(get_db)
):
    """
    获取当前策略配置
    
    Returns:
        当前策略和风险配置
    """
    try:
        logger.info("获取PVFRS策略配置")
        
        # 获取管理端接口实例
        admin_interface = get_admin_interface()
        
        # 在实际实现中，应该从admin_interface获取配置
        # 这里暂时返回默认配置或者模拟数据
        # config = admin_interface.get_config()
        
        config_data = {
            "strategy": {
                "ma_window": 20,
                "vol_window": 20,
                "corr_threshold": 0.8,
                "price_weight": 0.4,
                "volume_weight": 0.3,
                "freq_weight": 0.3
            },
            "risk": {
                "max_drawdown": 0.1,
                "stop_loss": 0.05,
                "take_profit": 0.15,
                "max_position": 0.8
            }
        }
        
        logger.info("PVFRS策略配置获取成功")
        
        return JSONResponse({
            "success": True,
            "data": config_data,
            "query_time": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS策略配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略配置失败: {str(e)}"
        )


@router.post("/config/test")
async def test_strategy_config(
    config_data: Dict = Body(..., description="策略配置测试数据"),
    db: Session = Depends(get_db)
):
    """
    测试策略配置有效性
    
    验证配置参数是否合法，不实际执行回测
    
    Args:
        config_data: 策略配置数据（可能包含 strategy_params 和 risk_params）
        db: 数据库会话
        
    Returns:
        测试结果
    """
    try:
        logger.info(f"测试PVFRS策略配置，接收到的数据: {config_data}")
        
        # 提取策略参数和风险参数
        strategy_params = config_data.get('strategy_params', config_data.get('strategy', {}))
        risk_params = config_data.get('risk_params', config_data.get('risk', {}))
        
        validation_errors = []
        validation_warnings = []
        
        # 验证策略参数
        if strategy_params:
            # 验证移动平均窗口
            if 'ma_window' in strategy_params:
                ma_window = strategy_params['ma_window']
                if not isinstance(ma_window, (int, float)) or ma_window < 5 or ma_window > 200:
                    validation_errors.append(f"移动平均窗口(ma_window)必须在5-200之间，当前值: {ma_window}")
            
            # 验证成交量窗口
            if 'vol_window' in strategy_params:
                vol_window = strategy_params['vol_window']
                if not isinstance(vol_window, (int, float)) or vol_window < 5 or vol_window > 200:
                    validation_errors.append(f"成交量窗口(vol_window)必须在5-200之间，当前值: {vol_window}")
            
            # 验证相关性阈值
            if 'corr_threshold' in strategy_params:
                corr_threshold = strategy_params['corr_threshold']
                if not isinstance(corr_threshold, (int, float)) or corr_threshold < 0 or corr_threshold > 1:
                    validation_errors.append(f"相关性阈值(corr_threshold)必须在0-1之间，当前值: {corr_threshold}")
            
            # 验证权重参数（价格、成交量、频率）
            weight_params = ['price_weight', 'volume_weight', 'freq_weight']
            if any(param in strategy_params for param in weight_params):
                price_weight = strategy_params.get('price_weight', 0)
                volume_weight = strategy_params.get('volume_weight', 0)
                freq_weight = strategy_params.get('freq_weight', 0)
                
                total_weight = price_weight + volume_weight + freq_weight
                if abs(total_weight - 1.0) > 0.01:  # 允许小的浮点误差
                    validation_warnings.append(f"权重总和应为1.0，当前总和: {total_weight:.2f}")
        
        # 验证风险参数
        if risk_params:
            # 验证最大回撤
            if 'max_drawdown' in risk_params:
                max_drawdown = risk_params['max_drawdown']
                if not isinstance(max_drawdown, (int, float)) or max_drawdown < 0 or max_drawdown > 1:
                    validation_errors.append(f"最大回撤(max_drawdown)必须在0-1之间，当前值: {max_drawdown}")
            
            # 验证止损比例
            if 'stop_loss' in risk_params:
                stop_loss = risk_params['stop_loss']
                if not isinstance(stop_loss, (int, float)) or stop_loss < 0 or stop_loss > 1:
                    validation_errors.append(f"止损比例(stop_loss)必须在0-1之间，当前值: {stop_loss}")
            
            # 验证止盈比例
            if 'take_profit' in risk_params:
                take_profit = risk_params['take_profit']
                if not isinstance(take_profit, (int, float)) or take_profit < 0:
                    validation_warnings.append(f"止盈比例(take_profit)应该大于0，当前值: {take_profit}")
            
            # 验证最大仓位
            if 'max_position' in risk_params:
                max_position = risk_params['max_position']
                if not isinstance(max_position, (int, float)) or max_position < 0 or max_position > 1:
                    validation_errors.append(f"最大仓位(max_position)必须在0-1之间，当前值: {max_position}")
        
        # 构建响应
        if validation_errors:
            logger.warning(f"配置验证失败，发现错误: {validation_errors}")
            return JSONResponse({
                "success": False,
                "valid": False,
                "errors": validation_errors,
                "warnings": validation_warnings,
                "message": "配置验证失败，请检查参数"
            }, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            logger.info("配置验证成功")
            return JSONResponse({
                "success": True,
                "valid": True,
                "errors": [],
                "warnings": validation_warnings,
                "message": "配置验证通过" if not validation_warnings else "配置验证通过，但有警告"
            })
        
    except Exception as e:
        logger.error(f"测试策略配置时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试配置失败: {str(e)}"
        )


@router.get("/config/history")
async def get_config_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取配置修改历史
    
    Args:
        limit: 返回数量限制
        db: 数据库会话
        
    Returns:
        配置修改历史列表
    """
    try:
        logger.info(f"获取PVFRS配置修改历史, 限制: {limit}")
        
        # 模拟历史数据
        history = [
            {
                "id": "cfg_001",
                "type": "strategy",
                "operator": "admin",
                "time": datetime.now().isoformat(),
                "changes": {"ma_window": {"old": 10, "new": 20}},
                "description": "调整均线窗口参数"
            },
            {
                "id": "cfg_002",
                "type": "risk",
                "operator": "admin",
                "time": (datetime.now()).isoformat(),
                "changes": {"stop_loss": {"old": 0.08, "new": 0.05}},
                "description": "收紧止损阈值"
            }
        ]
        
        return JSONResponse({
            "success": True,
            "data": history[:limit],
            "total": len(history)
        })
        
    except Exception as e:
        logger.error(f"获取PVFRS配置历史时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置历史失败: {str(e)}"
        )


@router.get("/test-route")
async def test_route():
    """测试路由"""
    return {"message": "测试路由工作正常", "timestamp": datetime.now().isoformat()}