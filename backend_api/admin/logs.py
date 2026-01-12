"""
管理后台日志查询API
提供对所有系统运行产生的日志表的查询监控功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text, desc
from sqlalchemy.orm import Session
from backend_api.database import get_db
from backend_api.auth import get_current_admin

router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"])

def get_field_mapping(table_config: Dict[str, Any]) -> Dict[str, str]:
    """获取字段映射，适配不同的表结构"""
    columns = table_config["columns"]
    
    # 默认映射
    mapping = {
        "id": "id",
        "operation_type": None,
        "operation_desc": None,
        "affected_rows": None,
        "status": None,
        "error_message": None,
        "created_at": None
    }
    
    # 根据实际字段名进行映射
    for col in columns:
        if col == "operation_type" or col == "log_type":
            mapping["operation_type"] = col
        elif col == "operation_desc" or col == "log_message":
            mapping["operation_desc"] = col
        elif col == "affected_rows" or col == "affected_count":
            mapping["affected_rows"] = col
        elif col == "status" or col == "log_status":
            mapping["status"] = col
        elif col == "error_message" or col == "error_info":
            mapping["error_message"] = col
        elif col == "created_at" or col == "log_time":
            mapping["created_at"] = col
    
    return mapping

# 日志表配置
LOG_TABLES = {
    "historical_collect": {
        "table_name": "historical_collect_operation_logs",
        "display_name": "历史数据采集日志",
        "columns": ["id", "operation_type", "operation_desc", "affected_rows", "status", "error_message", "collect_source", "created_at"]
    },
    "realtime_collect": {
        "table_name": "realtime_collect_operation_logs", 
        "display_name": "实时数据采集日志",
        "columns": ["id", "operation_type", "operation_desc", "affected_rows", "status", "error_message", "collect_source", "created_at"]
    },
    "operation": {
        "table_name": "operation_logs",
        "display_name": "系统操作日志", 
        "columns": ["id", "log_type", "log_message", "affected_count", "log_status", "error_info", "log_time"]
    },
    "watchlist_history": {
        "table_name": "watchlist_history_collection_logs",
        "display_name": "自选股历史采集日志",
        "columns": ["id", "stock_code", "affected_rows", "status", "error_message", "created_at"]
    }
}

@router.get("/tables")
async def get_log_tables():
    """获取可用的日志表列表"""
    return {
        "tables": [
            {
                "key": key,
                "display_name": config["display_name"],
                "table_name": config["table_name"]
            }
            for key, config in LOG_TABLES.items()
        ]
    }

@router.get("/stats")
async def get_overall_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """获取全局统计信息"""
    try:
        stats = {}
        
        for table_key, table_config in LOG_TABLES.items():
            table_name = table_config["table_name"]
            field_mapping = get_field_mapping(table_config)
            
            # 获取基本统计
            try:
                count_sql = f"SELECT COUNT(*) FROM {table_name}"
                total_count = db.execute(text(count_sql)).scalar() or 0
                
                # 获取今日记录数
                today_sql = f"""
                    SELECT COUNT(*) FROM {table_name} 
                    WHERE DATE({field_mapping['created_at']}) = CURRENT_DATE
                """
                today_count = db.execute(text(today_sql)).scalar() or 0
                
                # 获取错误记录数
                if field_mapping['status']:
                    error_sql = f"""
                        SELECT COUNT(*) FROM {table_name} 
                        WHERE {field_mapping['status']} = 'error'
                    """
                    error_count = db.execute(text(error_sql)).scalar() or 0
                else:
                    error_count = 0
                
                stats[table_key] = {
                    "table_name": table_config["display_name"],
                    "total_count": total_count,
                    "today_count": today_count,
                    "error_count": error_count
                }
            except Exception as e:
                # 如果某个表查询失败，设置默认值
                stats[table_key] = {
                    "table_name": table_config["display_name"],
                    "total_count": 0,
                    "today_count": 0,
                    "error_count": 0,
                    "error": str(e)
                }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@router.get("/query/{table_key}")
async def query_logs(
    table_key: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="状态筛选"),
    operation_type: Optional[str] = Query(None, description="操作类型筛选"),
    stock_code: Optional[str] = Query(None, description="股票代码筛选"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """查询指定日志表的数据"""
    
    if table_key not in LOG_TABLES:
        raise HTTPException(status_code=404, detail="日志表不存在")
    
    table_config = LOG_TABLES[table_key]
    table_name = table_config["table_name"]
    
    try:
        # 获取字段映射
        field_mapping = get_field_mapping(table_config)
        
        # 检查哪些字段实际存在于表中
        existing_columns_result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """), {"table_name": table_name})
        existing_columns = {row[0] for row in existing_columns_result.fetchall()}
        
        # 过滤出实际存在的列
        available_columns = [col for col in table_config["columns"] if col in existing_columns]
        
        # 构建查询条件
        where_conditions = []
        params = {}
        
        # 日期范围筛选
        if start_date and field_mapping["created_at"]:
            where_conditions.append(f"{field_mapping['created_at']} >= :start_date")
            params["start_date"] = f"{start_date} 00:00:00"
        
        if end_date and field_mapping["created_at"]:
            where_conditions.append(f"{field_mapping['created_at']} <= :end_date")
            params["end_date"] = f"{end_date} 23:59:59"
        
        # 状态筛选
        if status and field_mapping["status"]:
            where_conditions.append(f"{field_mapping['status']} = :status")
            params["status"] = status
        
        # 操作类型筛选
        if operation_type and field_mapping["operation_type"]:
            where_conditions.append(f"{field_mapping['operation_type']} ILIKE :operation_type")
            params["operation_type"] = f"%{operation_type}%"
        
        # 股票代码筛选（仅适用于watchlist_history表）
        if stock_code and table_key == "watchlist_history":
            where_conditions.append("stock_code ILIKE :stock_code")
            params["stock_code"] = f"%{stock_code}%"
        
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
        
        # 查询数据（只查询存在的列）
        columns_str = ", ".join(available_columns) if available_columns else "*"
        order_by_field = field_mapping["created_at"] or "id"
        query_sql = f"""
            SELECT {columns_str}
            FROM {table_name}
            {where_clause}
            ORDER BY {order_by_field} DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = offset
        
        result = db.execute(text(query_sql), params)
        rows = result.fetchall()
        
        # 格式化数据
        logs = []
        for row in rows:
            log_dict = {}
            # 使用实际查询到的列数量
            for i, column in enumerate(available_columns):
                if i < len(row):
                    value = row[i]
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    log_dict[column] = value
                else:
                    log_dict[column] = None
            # 对于配置中存在但表中不存在的字段，设置为 None
            for column in table_config["columns"]:
                if column not in available_columns:
                    log_dict[column] = None
            logs.append(log_dict)
        
        return {
            "table_key": table_key,
            "table_name": table_config["display_name"],
            "data": logs,
            "total": total_count,
            "page": page,
            "pageSize": page_size
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询日志失败: {str(e)}")

@router.get("/stats/{table_key}")
async def get_log_stats(
    table_key: str,
    days: Optional[int] = Query(None, ge=1, le=365, description="统计天数，不传则统计全部数据"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """获取指定日志表的统计信息"""
    
    if table_key not in LOG_TABLES:
        raise HTTPException(status_code=404, detail="日志表不存在")
    
    table_config = LOG_TABLES[table_key]
    table_name = table_config["table_name"]
    
    try:
        # 获取字段映射
        field_mapping = get_field_mapping(table_config)
        
        # 构建WHERE条件
        where_clause = ""
        params = {}
        
        if days is not None:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            where_clause = f"WHERE {field_mapping['created_at']} >= :start_date"
            params["start_date"] = start_date
        
        # 状态统计
        status_stats_sql = f"""
            SELECT {field_mapping['status']}, COUNT(*) as count
            FROM {table_name}
            {where_clause}
            GROUP BY {field_mapping['status']}
            ORDER BY count DESC
        """
        
        status_result = db.execute(text(status_stats_sql), params).fetchall()
        status_stats = [{"status": row[0], "count": row[1]} for row in status_result]
        
        # 每日统计
        daily_stats_sql = f"""
            SELECT 
                DATE({field_mapping['created_at']}) as date,
                COUNT(*) as total_count,
                COUNT(CASE WHEN {field_mapping['status']} = 'success' THEN 1 END) as success_count,
                COUNT(CASE WHEN {field_mapping['status']} = 'error' THEN 1 END) as error_count
            FROM {table_name}
            {where_clause}
            GROUP BY DATE({field_mapping['created_at']})
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
        
        # 操作类型统计
        operation_stats = []
        if field_mapping.get('operation_type'):
            operation_stats_sql = f"""
                SELECT {field_mapping['operation_type']}, COUNT(*) as count
                FROM {table_name}
                {where_clause}
                GROUP BY {field_mapping['operation_type']}
                ORDER BY count DESC
                LIMIT 10
            """
            
            operation_result = db.execute(text(operation_stats_sql), params).fetchall()
            operation_stats = [{"operation_type": row[0], "count": row[1]} for row in operation_result]
        
        return {
            "table_key": table_key,
            "table_name": table_config["display_name"],
            "period_days": days,
            "is_all_data": days is None,
            "status_stats": status_stats,
            "daily_stats": daily_stats,
            "operation_stats": operation_stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@router.get("/recent/{table_key}")
async def get_recent_logs(
    table_key: str,
    limit: int = Query(10, ge=1, le=50, description="记录数量"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """获取最近的日志记录"""
    
    if table_key not in LOG_TABLES:
        raise HTTPException(status_code=404, detail="日志表不存在")
    
    table_config = LOG_TABLES[table_key]
    table_name = table_config["table_name"]
    
    try:
        # 检查哪些字段实际存在于表中
        existing_columns_result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """), {"table_name": table_name})
        existing_columns = {row[0] for row in existing_columns_result.fetchall()}
        
        # 过滤出实际存在的列
        available_columns = [col for col in table_config["columns"] if col in existing_columns]
        
        # 查询数据（只查询存在的列）
        columns_str = ", ".join(available_columns) if available_columns else "*"
        query_sql = f"""
            SELECT {columns_str}
            FROM {table_name}
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        result = db.execute(text(query_sql), {"limit": limit})
        rows = result.fetchall()
        
        # 格式化数据
        logs = []
        for row in rows:
            log_dict = {}
            # 使用实际查询到的列
            for i, column in enumerate(available_columns):
                if i < len(row):
                    value = row[i]
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    log_dict[column] = value
                else:
                    log_dict[column] = None
            # 对于配置中存在但表中不存在的字段，设置为 None
            for column in table_config["columns"]:
                if column not in available_columns:
                    log_dict[column] = None
            logs.append(log_dict)
        
        return {
            "table_key": table_key,
            "table_name": table_config["display_name"],
            "data": logs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最近日志失败: {str(e)}") 