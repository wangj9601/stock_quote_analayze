"""
数据同步API模块
提供数据同步功能的接口
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import logging
import akshare as ak
import pandas as pd

from .models import (
    User, QuoteSyncTask, QuoteSyncTaskCreate, QuoteSyncTaskInDB
)
from .database import get_db
from .auth import get_current_admin_user

router = APIRouter(prefix="/api/sync", tags=["sync"])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 数据同步相关路由
async def sync_market_data(db: Session, task_id: int):
    """同步市场数据的后台任务"""
    try:
        task = db.query(QuoteSyncTask).filter(QuoteSyncTask.id == task_id).first()
        if not task:
            return
        
        # 更新任务状态
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        
        # 获取股票列表
        stock_list = ak.stock_info_a_code_name()
        
        # 同步实时行情
        for _, row in stock_list.iterrows():
            try:
                # 获取实时行情
                quote = ak.stock_zh_a_spot_em()
                quote = quote[quote['代码'] == row['code']]
                
                if not quote.empty:
                    # 更新数据库
                    # TODO: 实现数据库更新逻辑
                    pass
                
                # 记录进度
                task.progress = (row.name + 1) / len(stock_list) * 100
                db.commit()
                
            except Exception as e:
                logger.error(f"同步股票 {row['code']} 数据失败: {str(e)}")
                continue
        
        # 更新任务状态
        task.status = "completed"
        task.completed_at = datetime.now()
        db.commit()
        
    except Exception as e:
        logger.error(f"同步任务 {task_id} 执行失败: {str(e)}")
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()

@router.post("", response_model=QuoteSyncTaskInDB)
async def create_sync_task(
    task: QuoteSyncTaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """创建数据同步任务"""
    # 检查是否有正在运行的任务
    running_task = db.query(QuoteSyncTask).filter(
        QuoteSyncTask.status == "running"
    ).first()
    
    if running_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已有同步任务正在运行"
        )
    
    # 创建新任务
    db_task = QuoteSyncTask(
        task_type=task.task_type,
        status="pending",
        progress=0.0
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # 在后台执行同步任务
    background_tasks.add_task(sync_market_data, db, db_task.id)
    
    return db_task

@router.get("/tasks", response_model=List[QuoteSyncTaskInDB])
async def get_sync_tasks(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取同步任务列表"""
    query = db.query(QuoteSyncTask)
    if status:
        query = query.filter(QuoteSyncTask.status == status)
    
    tasks = query.order_by(desc(QuoteSyncTask.created_at)).all()
    return tasks

@router.get("/tasks/{task_id}", response_model=QuoteSyncTaskInDB)
async def get_sync_task(
    task_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取同步任务详情"""
    task = db.query(QuoteSyncTask).filter(QuoteSyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    return task 