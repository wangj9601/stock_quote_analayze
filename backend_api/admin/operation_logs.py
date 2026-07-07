"""
系统操作日志独立API模块
专门处理operation_logs表的查询和统计
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text, desc
from sqlalchemy.orm import Session
from backend_api.database import get_db
from backend_api.auth import get_current_admin
from backend_api.services.operation_logs_schema import ensure_operation_logs_system_schema

router = APIRouter(prefix="/api/admin/operation-logs", tags=["operation-logs"])

# operation_logs表配置
OPERATION_LOGS_CONFIG = {
    "table_name": "operation_logs",
    "display_name": "系统操作日志",
    "columns": ["id", "log_type", "log_message", "affected_count", "log_status", "error_info", "log_time"]
}

@router.get("/info")
async def get_operation_logs_info():
    """获取系统操作日志表信息"""
    return {
        "table_name": OPERATION_LOGS_CONFIG["table_name"],
        "display_name": OPERATION_LOGS_CONFIG["display_name"],
        "columns": OPERATION_LOGS_CONFIG["columns"],
        "description": "系统操作日志，记录各种系统操作的状态和结果"
    }

@router.get("/query")
async def query_operation_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    log_status: Optional[str] = Query(None, description="日志状态筛选"),
    log_type: Optional[str] = Query(None, description="日志类型筛选"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """查询系统操作日志数据"""
    
    table_name = OPERATION_LOGS_CONFIG["table_name"]
    
    try:
        ensure_operation_logs_system_schema(db)
        # 构建查询条件
        where_conditions = []
        params = {}
        
        # 日期范围筛选
        if start_date:
            where_conditions.append("log_time >= :start_date")
            params["start_date"] = f"{start_date} 00:00:00"
        
        if end_date:
            where_conditions.append("log_time <= :end_date")
            params["end_date"] = f"{end_date} 23:59:59"
        
        # 日志状态筛选
        if log_status:
            where_conditions.append("log_status = :log_status")
            params["log_status"] = log_status
        
        # 日志类型筛选
        if log_type:
            where_conditions.append("log_type ILIKE :log_type")
            params["log_type"] = f"%{log_type}%"
        
        # 构建WHERE子句
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # 计算总数
        count_sql = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
        count_result = db.execute(text(count_sql), params).scalar()
        total_count = count_result or 0
        
        # 计算分页
        offset = (page - 1) * page_size
        
        # 查询数据
        columns_str = ", ".join(OPERATION_LOGS_CONFIG["columns"])
        query_sql = f"""
            SELECT {columns_str}
            FROM {table_name}
            {where_clause}
            ORDER BY log_time DESC
            LIMIT :limit OFFSET :offset
        """
        
        params.update({"limit": page_size, "offset": offset})
        result = db.execute(text(query_sql), params)
        rows = result.fetchall()
        
        # 格式化数据
        logs = []
        for row in rows:
            log_dict = {}
            for i, column in enumerate(OPERATION_LOGS_CONFIG["columns"]):
                value = row[i]
                if isinstance(value, datetime):
                    value = value.isoformat()
                log_dict[column] = value
            logs.append(log_dict)
        
        return {
            "table_name": OPERATION_LOGS_CONFIG["display_name"],
            "data": logs,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询系统操作日志失败: {str(e)}")

@router.get("/stats")
async def get_operation_logs_stats(
    days: Optional[int] = Query(None, ge=1, le=365, description="统计天数，不传则统计全部数据"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """获取系统操作日志统计信息"""
    
    table_name = OPERATION_LOGS_CONFIG["table_name"]
    
    try:
        ensure_operation_logs_system_schema(db)
        # 构建WHERE条件
        where_clause = ""
        params = {}
        
        if days is not None:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            where_clause = "WHERE log_time >= :start_date"
            params["start_date"] = start_date
        
        # 状态统计
        status_stats_sql = f"""
            SELECT log_status, COUNT(*) as count
            FROM {table_name}
            {where_clause}
            GROUP BY log_status
            ORDER BY count DESC
        """
        
        status_result = db.execute(text(status_stats_sql), params).fetchall()
        status_stats = [{"status": row[0], "count": row[1]} for row in status_result]
        
        # 每日统计
        daily_stats_sql = f"""
            SELECT 
                DATE(log_time) as date,
                COUNT(*) as total_count,
                COUNT(CASE WHEN log_status = '成功' THEN 1 END) as success_count,
                COUNT(CASE WHEN log_status = '失败' THEN 1 END) as error_count
            FROM {table_name}
            {where_clause}
            GROUP BY DATE(log_time)
            ORDER BY date DESC
        """
        
        daily_result = db.execute(text(daily_stats_sql), params).fetchall()
        
        daily_stats = []
        for row in daily_result:
            daily_stats.append({
                "date": row[0].isoformat() if isinstance(row[0], datetime) else str(row[0]),
                "total_count": row[1],
                "success_count": row[2],
                "error_count": row[3]
            })
        
        # 日志类型统计
        log_type_stats_sql = f"""
            SELECT log_type, COUNT(*) as count
            FROM {table_name}
            {where_clause}
            GROUP BY log_type
            ORDER BY count DESC
            LIMIT 10
        """
        
        log_type_result = db.execute(text(log_type_stats_sql), params).fetchall()
        log_type_stats = [{"log_type": row[0], "count": row[1]} for row in log_type_result]
        
        return {
            "table_name": OPERATION_LOGS_CONFIG["display_name"],
            "period_days": days,
            "is_all_data": days is None,
            "status_stats": status_stats,
            "daily_stats": daily_stats,
            "log_type_stats": log_type_stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统操作日志统计信息失败: {str(e)}")

@router.get("/recent")
async def get_recent_operation_logs(
    limit: int = Query(10, ge=1, le=50, description="记录数量"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """获取最近的系统操作日志记录"""
    
    table_name = OPERATION_LOGS_CONFIG["table_name"]
    
    try:
        ensure_operation_logs_system_schema(db)
        columns_str = ", ".join(OPERATION_LOGS_CONFIG["columns"])
        query_sql = f"""
            SELECT {columns_str}
            FROM {table_name}
            ORDER BY log_time DESC
            LIMIT :limit
        """
        
        result = db.execute(text(query_sql), {"limit": limit})
        rows = result.fetchall()
        
        # 格式化数据
        logs = []
        for row in rows:
            log_dict = {}
            for i, column in enumerate(OPERATION_LOGS_CONFIG["columns"]):
                value = row[i]
                if isinstance(value, datetime):
                    value = value.isoformat()
                log_dict[column] = value
            logs.append(log_dict)
        
        return {
            "table_name": OPERATION_LOGS_CONFIG["display_name"],
            "data": logs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近系统操作日志失败: {str(e)}") 