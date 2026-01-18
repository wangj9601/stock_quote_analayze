"""
仪表板API模块
提供仪表板所需的数据接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from datetime import datetime, timedelta, date
import random
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend_api.models import User, Watchlist, WatchlistGroup

from backend_api.database import get_db
from backend_api.auth import get_current_admin

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin"])

# 模拟数据生成函数
def generate_stats():
    return {
        "userCount": random.randint(1000, 5000),
        "userChange": {
            "value": random.randint(-100, 100),
            "type": "positive" if random.random() > 0.5 else "negative",
            "unit": "%"
        },
        "stockCount": random.randint(3000, 4000),
        "stockChange": {
            "value": random.randint(-50, 50),
            "type": "positive" if random.random() > 0.5 else "negative",
            "unit": "%"
        },
        "dataSuccessRate": random.randint(95, 100),
        "dataChange": {
            "value": random.randint(-5, 5),
            "type": "positive" if random.random() > 0.5 else "negative",
            "unit": "%"
        },
        "responseTime": round(random.uniform(0.1, 0.5), 2),
        "responseChange": {
            "value": random.randint(-20, 20),
            "type": "positive" if random.random() > 0.5 else "negative",
            "unit": "%"
        }
    }

def generate_user_activity():
    # 生成过去7天的数据
    days = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
    values = [random.randint(100, 1000) for _ in range(7)]
    return {
        "labels": days,
        "values": values
    }

def generate_data_collection():
    total = 1000
    success = random.randint(800, 950)
    failed = random.randint(0, 50)
    in_progress = total - success - failed
    return {
        "success": success,
        "failed": failed,
        "inProgress": in_progress
    }

def generate_activities():
    activities = [
        {
            "icon": "👥",
            "title": "新用户注册",
            "description": "用户xxx完成了注册",
            "time": "10分钟前"
        },
        {
            "icon": "📊",
            "title": "数据更新",
            "description": "完成今日行情数据更新",
            "time": "30分钟前"
        },
        {
            "icon": "🔔",
            "title": "系统通知",
            "description": "系统维护通知已发布",
            "time": "1小时前"
        },
        {
            "icon": "📈",
            "title": "数据采集",
            "description": "完成历史数据采集任务",
            "time": "2小时前"
        },
        {
            "icon": "⚙️",
            "title": "系统配置",
            "description": "更新了系统配置参数",
            "time": "3小时前"
        }
    ]
    return activities

# API路由
@router.get("/stats")
async def get_dashboard_stats(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取仪表板统计数据"""
    try:
        # 尝试从数据库获取数据，如果失败则使用模拟数据
        try:
            # 用户统计
            active_users = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
            disabled_users = db.query(func.count(User.id)).filter(User.status == "disabled").scalar() or 0
            
            # 今日登录用户数
            today = date.today()
            today_logins = db.query(func.count(User.id)).filter(
                func.date(User.last_login) == today
            ).scalar() or 0
            
            # 自选股统计
            total_watchlist = db.query(func.count(Watchlist.id)).scalar() or 0
            total_groups = db.query(func.count(WatchlistGroup.id)).scalar() or 0
            
        except Exception as db_error:
            print(f"数据库查询失败，使用模拟数据: {db_error}")
            # 使用模拟数据
            active_users = 1234
            disabled_users = 56
            today_logins = 89
            total_watchlist = 567
            total_groups = 23
        
        # 系统状态
        system_status = {
            "status": "running",
            "data_sources": 2,  # 数据源数量
            "online_sources": 1,  # 在线数据源数量
            "last_update": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "data": {
                "userCount": active_users + disabled_users,  # 前端期望的字段名
                "stockCount": total_watchlist,
                "quoteCount": 56789,  # 模拟数据
                "alertCount": 5,  # 模拟数据
                "active_users": active_users,
                "disabled_users": disabled_users,
                "total_users": active_users + disabled_users,
                "today_logins": today_logins,
                "total_watchlist": total_watchlist,
                "total_groups": total_groups,
                "system_status": system_status
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取统计数据失败: {str(e)}"
        )

@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取最近活动"""
    try:
        # 获取最近登录的用户
        recent_logins = db.query(User).filter(
            User.last_login.isnot(None)
        ).order_by(
            User.last_login.desc()
        ).limit(limit).all()
        
        # 获取最近添加的自选股
        recent_watchlist = db.query(Watchlist).order_by(
            Watchlist.created_at.desc()
        ).limit(limit).all()
        
        activities = []
        
        # 处理登录活动
        for user in recent_logins:
            if user.last_login:
                activities.append({
                    "type": "login",
                    "user": {
                        "id": user.id,
                        "username": user.username
                    },
                    "timestamp": user.last_login.isoformat(),
                    "description": f"用户 {user.username} 登录系统"
                })
        
        # 处理自选股活动
        for watch in recent_watchlist:
            activities.append({
                "type": "watchlist",
                "user": {
                    "id": watch.user_id,
                    "username": db.query(User.username).filter(User.id == watch.user_id).scalar()
                },
                "timestamp": watch.created_at.isoformat(),
                "description": f"添加自选股 {watch.stock_name}({watch.stock_code})"
            })
        
        # 按时间排序
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "success": True,
            "data": activities[:limit]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取最近活动失败: {str(e)}"
        )

@router.get("/dashboard/user-activity")
async def get_user_activity(current_user: Any = Depends(get_current_admin)):
    """获取用户活跃度数据"""
    return {
        "success": True,
        "data": generate_user_activity()
    }

@router.get("/dashboard/data-collection")
async def get_data_collection(current_user: Any = Depends(get_current_admin)):
    """获取数据采集状态"""
    return {
        "success": True,
        "data": generate_data_collection()
    }

@router.get("/dashboard/activities")
async def get_activities(current_user: Any = Depends(get_current_admin)):
    """获取最近活动列表"""
    return {
        "success": True,
        "data": generate_activities()
    } 