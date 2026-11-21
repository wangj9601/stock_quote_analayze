#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资讯频道API路由
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func, or_
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from backend_api.database import get_db
from backend_api.models import StockNews

logger = logging.getLogger(__name__)

# 全局变量缓存字段检查结果
_read_count_field_exists = None

def check_read_count_field_exists(db: Session) -> bool:
    """检查read_count字段是否存在"""
    global _read_count_field_exists
    
    if _read_count_field_exists is not None:
        return _read_count_field_exists
    
    try:
        # 使用独立的连接来检查字段，避免影响主事务
        from database import SessionLocal
        temp_db = SessionLocal()
        try:
            # 尝试查询read_count字段
            temp_db.execute(text("SELECT read_count FROM stock_news LIMIT 1"))
            _read_count_field_exists = True
            logger.info("read_count字段存在")
        except Exception as e:
            if "read_count" in str(e) or "column" in str(e).lower():
                _read_count_field_exists = False
                logger.warning("read_count字段不存在")
            else:
                # 其他错误，假设字段存在
                _read_count_field_exists = True
                logger.warning(f"检查read_count字段时出现其他错误: {e}")
        finally:
            temp_db.close()
    except Exception as e:
        # 如果无法创建临时连接，默认假设字段不存在
        _read_count_field_exists = False
        logger.warning(f"无法检查read_count字段，默认假设不存在: {e}")
    
    return _read_count_field_exists

def get_available_fields(db: Session) -> dict:
    """获取stock_news表中可用的字段"""
    try:
        from database import SessionLocal
        temp_db = SessionLocal()
        try:
            # 获取表结构
            result = temp_db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'stock_news' 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """))
            columns = [row[0] for row in result.fetchall()]
            
            return {
                'read_count': 'read_count' in columns,
                'is_hot': 'is_hot' in columns,
                'tags': 'tags' in columns,
                'image_url': 'image_url' in columns,
                'category_id': 'category_id' in columns
            }
        finally:
            temp_db.close()
    except Exception as e:
        logger.warning(f"无法检查表结构，使用默认字段: {e}")
        return {
            'read_count': False,
            'is_hot': False,
            'tags': False,
            'image_url': False,
            'category_id': False
        }

router = APIRouter(prefix="/api/news", tags=["news_channel"])

@router.get("/categories")
async def get_news_categories(db: Session = Depends(get_db)):
    """获取资讯分类列表"""
    try:
        # 先检查news_categories表是否存在
        result = db.execute(text("""
            SELECT id, name, description, sort_order 
            FROM news_categories 
            WHERE is_active = TRUE 
            ORDER BY sort_order
        """))
        categories = result.fetchall()
        
        return JSONResponse({
            "success": True,
            "data": [
                {
                    "id": cat[0],
                    "name": cat[1],
                    "description": cat[2],
                    "sort_order": cat[3]
                }
                for cat in categories
            ]
        })
    except Exception as e:
        if "news_categories" in str(e) or "does not exist" in str(e).lower():
            # 如果表不存在，返回默认分类
            logger.warning("news_categories表不存在，返回默认分类")
            default_categories = [
                {"id": 1, "name": "全部", "description": "所有资讯", "sort_order": 1},
                {"id": 2, "name": "市场动态", "description": "市场行情、指数变化等", "sort_order": 2},
                {"id": 3, "name": "政策解读", "description": "政策法规、监管动态等", "sort_order": 3},
                {"id": 4, "name": "公司资讯", "description": "上市公司公告、财报等", "sort_order": 4},
                {"id": 5, "name": "国际财经", "description": "国际市场、汇率等", "sort_order": 5},
                {"id": 6, "name": "分析研判", "description": "专业分析、投资建议等", "sort_order": 6}
            ]
            
            return JSONResponse({
                "success": True,
                "data": default_categories
            })
        else:
            # 其他错误，重新抛出
            raise e
            
    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取分类失败: {str(e)}"
        }, status_code=500)

@router.get("/list")
async def get_news_list(
    category_id: Optional[int] = Query(None, description="分类ID"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
):
    """获取资讯列表"""
    try:
        # 检查可用字段
        fields = get_available_fields(db)
        
        # 构建查询条件
        where_conditions = []
        params = {}
        
        if category_id and category_id != 1:  # 1表示"全部"
            if fields['category_id']:
                where_conditions.append("category_id = :category_id")
                params["category_id"] = category_id
            else:
                # 如果category_id字段不存在，忽略分类过滤
                logger.warning("category_id字段不存在，忽略分类过滤")
        
        if keyword:
            where_conditions.append("(title ILIKE :keyword OR content ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 分页参数
        offset = (page - 1) * page_size
        params["offset"] = offset
        params["limit"] = page_size
        
        # 查询总数
        count_sql = f"""
            SELECT COUNT(*) FROM stock_news 
            WHERE {where_clause}
        """
        total_result = db.execute(text(count_sql), params)
        total = total_result.scalar()
        
        # 构建查询字段列表
        select_fields = ["id", "title", "summary", "publish_time", "source"]
        if fields['read_count']:
            select_fields.append("read_count")
        if fields['is_hot']:
            select_fields.append("is_hot")
        if fields['tags']:
            select_fields.append("tags")
        if fields['image_url']:
            select_fields.append("image_url")
        if fields['category_id']:
            select_fields.append("category_id")
        
        # 查询数据
        data_sql = f"""
            SELECT {', '.join(select_fields)}
            FROM stock_news 
            WHERE {where_clause}
            ORDER BY publish_time DESC
            OFFSET :offset LIMIT :limit
        """
        
        result = db.execute(text(data_sql), params)
        news_list = result.fetchall()
        
        # 构建响应数据
        items = []
        for news in news_list:
            item = {
                        "id": news[0],
                        "title": news[1],
                        "summary": news[2] or (news[1][:200] + "..." if len(news[1]) > 200 else news[1]),
                        "publish_time": str(news[3]) if news[3] else '',
                        "source": news[4] or '',
                "read_count": 0,
                "is_hot": False,
                "tags": [],
                "image_url": '',
                "category_id": None
            }
            
            # 根据可用字段动态设置值
            field_index = 5
            if fields['read_count']:
                item["read_count"] = news[field_index] or 0
                field_index += 1
            if fields['is_hot']:
                item["is_hot"] = news[field_index] or False
                field_index += 1
            if fields['tags']:
                item["tags"] = news[field_index] or []
                field_index += 1
            if fields['image_url']:
                item["image_url"] = news[field_index] or ''
                field_index += 1
            if fields['category_id']:
                item["category_id"] = news[field_index]
            
            items.append(item)
        
        return JSONResponse({
            "success": True,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        })
    except Exception as e:
        logger.error(f"获取资讯列表失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取资讯列表失败: {str(e)}"
        }, status_code=500)

@router.get("/hot")
async def get_hot_news(limit: int = Query(10, description="数量限制"), db: Session = Depends(get_db)):
    """获取热门资讯"""
    try:
        # 检查可用字段
        fields = get_available_fields(db)
        
        # 构建查询字段列表
        select_fields = ["id", "title", "summary", "publish_time", "source"]
        if fields['read_count']:
            select_fields.append("read_count")
        if fields['is_hot']:
            select_fields.append("is_hot")
        
        # 构建WHERE条件
        where_clause = "1=1"
        if fields['is_hot']:
            where_clause = "is_hot = TRUE"
        
        # 构建排序条件
        order_by = "ORDER BY publish_time DESC"
        if fields['read_count']:
            order_by = "ORDER BY read_count DESC"
        
        # 查询数据
        data_sql = f"""
            SELECT {', '.join(select_fields)}
            FROM stock_news 
            WHERE {where_clause}
            {order_by}
            LIMIT :limit
        """
        
        result = db.execute(text(data_sql), {"limit": limit})
        hot_news = result.fetchall()
        
        # 构建响应数据
        items = []
        for news in hot_news:
            item = {
                    "id": news[0],
                    "title": news[1],
                    "summary": news[2] or news[1][:100] + "...",
                    "publish_time": str(news[3]) if news[3] else '',
                "source": news[4] or '',
                "read_count": 0,
                "is_hot": False
            }
            
            # 根据可用字段动态设置值
            field_index = 5
            if fields['read_count']:
                item["read_count"] = news[field_index] or 0
                field_index += 1
            if fields['is_hot']:
                item["is_hot"] = news[field_index] or False
            
            items.append(item)
        
        return JSONResponse({
            "success": True,
            "data": items
        })
    except Exception as e:
        logger.error(f"获取热门资讯失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取热门资讯失败: {str(e)}"
        }, status_code=500)

@router.get("/detail/{news_id}")
async def get_news_detail(news_id: int, db: Session = Depends(get_db)):
    """获取资讯详情"""
    try:
        # 查询资讯详情
        result = db.execute(text("""
            SELECT id, title, content, summary, publish_time, source, url, 
                   read_count, tags, image_url, stock_code, category_id
            FROM stock_news 
            WHERE id = :news_id
        """), {"news_id": news_id})
        news = result.fetchone()
        
        if not news:
            return JSONResponse({
                "success": False,
                "message": "资讯不存在"
            }, status_code=404)
        
        # 增加阅读量
        db.execute(text("""
            UPDATE stock_news 
            SET read_count = COALESCE(read_count, 0) + 1 
            WHERE id = :news_id
        """), {"news_id": news_id})
        db.commit()
        
        return JSONResponse({
            "success": True,
            "data": {
                "id": news[0],
                "title": news[1],
                "content": news[2] or '',
                "summary": news[3] or '',
                "publish_time": str(news[4]) if news[4] else '',
                "source": news[5] or '',
                "url": news[6] or '',
                "read_count": (news[7] or 0) + 1,  # 显示更新后的阅读量
                "tags": news[8] or [],
                "image_url": news[9] or '',
                "stock_code": news[10] or '',
                "category_id": news[11]
            }
        })
    except Exception as e:
        logger.error(f"获取资讯详情失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取资讯详情失败: {str(e)}"
        }, status_code=500)

@router.get("/featured")
async def get_featured_news(db: Session = Depends(get_db)):
    """获取头条新闻（最新且阅读量较高的）"""
    try:
        # 检查可用字段
        fields = get_available_fields(db)
        
        # 构建查询字段列表
        select_fields = ["id", "title", "summary", "publish_time", "source"]
        if fields['read_count']:
            select_fields.append("read_count")
        if fields['is_hot']:
            select_fields.append("is_hot")
        
        # 构建排序条件
        order_by = "ORDER BY publish_time DESC"
        if fields['read_count']:
            order_by += ", read_count DESC"
        
        # 查询数据
        data_sql = f"""
            SELECT {', '.join(select_fields)}
            FROM stock_news 
            {order_by}
            LIMIT 1
        """
        
        result = db.execute(text(data_sql))
        featured = result.fetchone()
        
        if not featured:
            return JSONResponse({
                "success": False,
                "message": "暂无头条新闻"
            }, status_code=404)
        
        # 构建响应数据
        data = {
                "id": featured[0],
                "title": featured[1],
                "summary": featured[2] or featured[1][:200] + "...",
                "publish_time": str(featured[3]) if featured[3] else '',
                "source": featured[4] or '',
            "read_count": 0,
            "is_hot": False
        }
        
        # 根据可用字段动态设置值
        field_index = 5
        if fields['read_count']:
            data["read_count"] = featured[field_index] or 0
            field_index += 1
        if fields['is_hot']:
            data["is_hot"] = featured[field_index] or False
        
        return JSONResponse({
            "success": True,
            "data": data
        })
    except Exception as e:
        logger.error(f"获取头条新闻失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取头条新闻失败: {str(e)}"
        }, status_code=500)

@router.get("/search")
async def search_news(
    keyword: str = Query(..., description="搜索关键词"),
    category_id: Optional[int] = Query(None, description="分类ID"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    """搜索资讯"""
    try:
        # 构建查询条件
        where_conditions = ["(title ILIKE :keyword OR content ILIKE :keyword OR summary ILIKE :keyword)"]
        params = {"keyword": f"%{keyword}%"}
        
        if category_id and category_id != 1:
            where_conditions.append("category_id = :category_id")
            params["category_id"] = category_id
        
        where_clause = " AND ".join(where_conditions)
        
        # 分页参数
        offset = (page - 1) * page_size
        params["offset"] = offset
        params["limit"] = page_size
        
        # 查询总数
        count_sql = f"""
            SELECT COUNT(*) FROM stock_news 
            WHERE {where_clause}
        """
        total_result = db.execute(text(count_sql), params)
        total = total_result.scalar()
        
        # 查询数据
        data_sql = f"""
            SELECT id, title, summary, publish_time, source, read_count, 
                   is_hot, tags, image_url, category_id
            FROM stock_news 
            WHERE {where_clause}
            ORDER BY publish_time DESC
            OFFSET :offset LIMIT :limit
        """
        result = db.execute(text(data_sql), params)
        news_list = result.fetchall()
        
        return JSONResponse({
            "success": True,
            "data": {
                "items": [
                    {
                        "id": news[0],
                        "title": news[1],
                        "summary": news[2] or news[1][:200] + "...",
                        "publish_time": str(news[3]) if news[3] else '',
                        "source": news[4] or '',
                        "read_count": news[5] or 0,
                        "is_hot": news[6] or False,
                        "tags": news[7] or [],
                        "image_url": news[8] or '',
                        "category_id": news[9]
                    }
                    for news in news_list
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "keyword": keyword
            }
        })
    except Exception as e:
        logger.error(f"搜索资讯失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"搜索资讯失败: {str(e)}"
        }, status_code=500)

@router.get("/statistics")
async def get_news_statistics(db: Session = Depends(get_db)):
    """获取资讯统计信息"""
    try:
        # 总资讯数
        total_result = db.execute(text("SELECT COUNT(*) FROM stock_news"))
        total_news = total_result.scalar()
        
        # 今日资讯数
        today_result = db.execute(text("""
            SELECT COUNT(*) FROM stock_news 
            WHERE DATE(publish_time) = CURRENT_DATE
        """))
        today_news = today_result.scalar()
        
        # 热门资讯数
        hot_result = db.execute(text("SELECT COUNT(*) FROM stock_news WHERE is_hot = TRUE"))
        hot_news_count = hot_result.scalar()
        
        # 总阅读量
        reads_result = db.execute(text("SELECT SUM(COALESCE(read_count, 0)) FROM stock_news"))
        total_reads = reads_result.scalar() or 0
        
        # 分类统计
        category_result = db.execute(text("""
            SELECT nc.name, COUNT(sn.id) as count
            FROM news_categories nc
            LEFT JOIN stock_news sn ON nc.id = sn.category_id
            WHERE nc.is_active = TRUE
            GROUP BY nc.id, nc.name
            ORDER BY nc.sort_order
        """))
        category_stats = category_result.fetchall()
        
        return JSONResponse({
            "success": True,
            "data": {
                "total_news": total_news,
                "today_news": today_news,
                "hot_news_count": hot_news_count,
                "total_reads": total_reads,
                "category_stats": [
                    {"name": stat[0], "count": stat[1]}
                    for stat in category_stats
                ]
            }
        })
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return JSONResponse({
            "success": False,
        }, status_code=500)

@router.get("/homepage")
async def get_homepage_news(limit: int = Query(3, description="数量限制"), db: Session = Depends(get_db)):
    """获取首页市场资讯（最新3条）"""
    try:
        # 检查read_count字段是否存在
        has_read_count = check_read_count_field_exists(db)
        
        if has_read_count:
            result = db.execute(text("""
            SELECT id, title, summary, publish_time, source, read_count
            FROM stock_news 
            ORDER BY publish_time DESC
            LIMIT :limit
        """), {"limit": limit})
        else:
            result = db.execute(text("""
                SELECT id, title, summary, publish_time, source
            FROM stock_news 
            ORDER BY publish_time DESC
            LIMIT :limit
        """), {"limit": limit})
        news_list = result.fetchall()
        
        # 使用之前检查的结果
        
        return JSONResponse({
            "success": True,
            "data": [
                {
                    "id": news[0],
                    "title": news[1],
                    "summary": news[2] or news[1][:100] + "..." if len(news[1]) > 100 else news[1],
                    "publish_time": str(news[3]) if news[3] else '',
                    "source": news[4] or '',
                    "read_count": news[5] if has_read_count else 0
                }
                for news in news_list
            ]
        })
    except Exception as e:
        logger.error(f"获取首页市场资讯失败: {e}")
        return JSONResponse({
            "success": False,
            "message": f"获取首页市场资讯失败: {str(e)}"
        }, status_code=500)
