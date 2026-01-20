"""
PVFRS策略管理增强API路由
基于重构后的数据库结构提供RESTful API
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, date
import logging

from backend_api.database import get_db
from backend_api.services.pvfrs_admin_service import PVFRSAdminService
from backend_core.strategies.pvfrs.admin_interface_enhanced import (
    AdminInterfaceEnhanced, BacktestConfig, create_admin_interface_enhanced
)
from backend_core.strategies.pvfrs.models import PVFRSException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pvfrs", tags=["PVFRS策略管理"])

# Pydantic模型
class StrategyConfigCreate(BaseModel):
    name: str = Field(..., description="策略名称")
    description: str = Field(..., description="策略描述")
    config_params: Dict[str, Any] = Field(..., description="策略参数")
    is_active: bool = Field(True, description="是否激活")

class StrategyConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    config_params: Optional[Dict[str, Any]] = Field(None, description="策略参数")
    is_active: Optional[bool] = Field(None, description="是否激活")

class BacktestConfigCreate(BaseModel):
    strategy_name: str = Field(..., description="策略名称")
    stock_pool: List[str] = Field(..., description="股票池")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="初始资金")
    strategy_params: Dict[str, Any] = Field(..., description="策略参数")
    risk_params: Dict[str, Any] = Field(..., description="风险参数")
    mode: str = Field("single", description="模式: single, batch, optimize")
    force_update: bool = Field(False, description="是否强制更新")

class TaskProgressUpdate(BaseModel):
    progress: int = Field(..., ge=0, le=100, description="进度百分比")
    current_step: str = Field(..., description="当前步骤")
    status: str = Field("running", description="状态")

class TaskComplete(BaseModel):
    performance: Dict[str, Any] = Field(..., description="性能指标")
    trades: List[Dict[str, Any]] = Field(..., description="交易记录")
    equity_curve: List[Dict[str, Any]] = Field(..., description="收益曲线")

# 依赖注入
def get_admin_interface() -> AdminInterfaceEnhanced:
    """获取管理接口实例"""
    return create_admin_interface_enhanced()

def get_admin_service(db=Depends(get_db)) -> PVFRSAdminService:
    """获取管理服务实例"""
    return PVFRSAdminService(db)

# ==================== 策略配置管理 ====================

@router.post("/strategy-configs", response_model=Dict)
async def create_strategy_config(
    config: StrategyConfigCreate,
    service: PVFRSAdminService = Depends(get_admin_service)
):
    """创建策略配置"""
    try:
        config_id = service.create_strategy_config(
            name=config.name,
            description=config.description,
            config_params=config.config_params,
            is_active=config.is_active
        )
        return {
            "success": True,
            "config_id": config_id,
            "message": "策略配置创建成功"
        }
    except Exception as e:
        logger.error(f"创建策略配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategy-configs", response_model=Dict)
async def list_strategy_configs(
    active_only: bool = Query(False, description="仅显示激活的配置"),
    service: PVFRSAdminService = Depends(get_admin_service)
):
    """列出策略配置"""
    try:
        configs = service.list_strategy_configs(active_only)
        return {
            "success": True,
            "configs": [
                {
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "config_params": config.config_params,
                    "is_active": config.is_active,
                    "created_at": config.created_at.isoformat(),
                    "updated_at": config.updated_at.isoformat()
                }
                for config in configs
            ]
        }
    except Exception as e:
        logger.error(f"列出策略配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategy-configs/{config_id}", response_model=Dict)
async def get_strategy_config(
    config_id: int,
    service: PVFRSAdminService = Depends(get_admin_service)
):
    """获取策略配置"""
    try:
        config = service.get_strategy_config(config_id)
        if not config:
            raise HTTPException(status_code=404, detail="策略配置不存在")
        
        return {
            "success": True,
            "config": {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "config_params": config.config_params,
                "is_active": config.is_active,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/strategy-configs/{config_id}", response_model=Dict)
async def update_strategy_config(
    config_id: int,
    config_update: StrategyConfigUpdate,
    service: PVFRSAdminService = Depends(get_admin_service)
):
    """更新策略配置"""
    try:
        update_data = config_update.dict(exclude_unset=True)
        success = service.update_strategy_config(config_id, **update_data)
        
        if not success:
            raise HTTPException(status_code=404, detail="策略配置不存在")
        
        return {
            "success": True,
            "message": "策略配置更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/strategy-configs/{config_id}", response_model=Dict)
async def delete_strategy_config(
    config_id: int,
    service: PVFRSAdminService = Depends(get_admin_service)
):
    """删除策略配置"""
    try:
        success = service.delete_strategy_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="策略配置不存在")
        
        return {
            "success": True,
            "message": "策略配置删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除策略配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 回测任务管理 ====================

@router.post("/backtests", response_model=Dict)
async def create_backtest(
    config: BacktestConfigCreate,
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """创建回测任务"""
    try:
        backtest_config = BacktestConfig(
            strategy_name=config.strategy_name,
            stock_pool=config.stock_pool,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            strategy_params=config.strategy_params,
            risk_params=config.risk_params,
            mode=config.mode,
            force_update=config.force_update
        )
        
        task_id = admin.create_backtest(backtest_config)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "回测任务创建成功"
        }
    except Exception as e:
        logger.error(f"创建回测任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/backtests/{task_id}/progress", response_model=Dict)
async def get_task_progress(
    task_id: str,
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """获取任务进度"""
    try:
        progress = admin.get_task_progress(task_id)
        if 'error' in progress:
            raise HTTPException(status_code=404, detail=progress['error'])
        
        return {
            "success": True,
            "progress": progress
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/backtests/{task_id}/progress", response_model=Dict)
async def update_task_progress(
    task_id: str,
    progress_update: TaskProgressUpdate,
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """更新任务进度"""
    try:
        success = admin.update_task_progress(
            task_id=task_id,
            progress=progress_update.progress,
            current_step=progress_update.current_step,
            status=progress_update.status
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "success": True,
            "message": "任务进度更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新任务进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backtests/{task_id}/complete", response_model=Dict)
async def complete_task(
    task_id: str,
    complete_data: TaskComplete,
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """完成任务"""
    try:
        report_id = admin.complete_task(
            task_id=task_id,
            performance=complete_data.performance,
            trades=complete_data.trades,
            equity_curve=complete_data.equity_curve
        )
        
        return {
            "success": True,
            "report_id": report_id,
            "message": "任务完成成功"
        }
    except Exception as e:
        logger.error(f"完成任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/backtests", response_model=Dict)
async def list_backtest_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: int = Query(50, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """列出回测任务"""
    try:
        tasks = admin.list_backtest_tasks(status, limit, offset)
        
        return {
            "success": True,
            "tasks": tasks,
            "total": len(tasks),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"列出回测任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 回测报告管理 ====================

@router.get("/reports/{report_id}", response_model=Dict)
async def get_backtest_report(
    report_id: str,
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """获取回测报告"""
    try:
        report = admin.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="报告不存在")
        
        return {
            "success": True,
            "report": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports/compare", response_model=Dict)
async def compare_reports(
    report_ids: List[str] = Body(..., description="报告ID列表"),
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """比较多个报告"""
    try:
        if len(report_ids) < 2:
            raise HTTPException(status_code=400, detail="至少需要2个报告进行比较")
        
        comparison = admin.compare_reports(report_ids)
        
        return {
            "success": True,
            "comparison": comparison
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"比较报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 数据统计和管理 ====================

@router.get("/statistics", response_model=Dict)
async def get_statistics(
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """获取统计信息"""
    try:
        stats = admin.get_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup", response_model=Dict)
async def cleanup_old_data(
    days: int = Query(365, ge=1, le=3650, description="保留天数"),
    admin: AdminInterfaceEnhanced = Depends(get_admin_interface)
):
    """清理旧数据"""
    try:
        result = admin.cleanup_old_data(days)
        
        return {
            "success": True,
            "cleanup_result": result,
            "message": f"清理完成，删除了 {result.get('total_deleted', 0)} 条记录"
        }
    except Exception as e:
        logger.error(f"清理旧数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 健康检查 ====================

@router.get("/health", response_model=Dict)
async def health_check():
    """健康检查"""
    try:
        return {
            "success": True,
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
