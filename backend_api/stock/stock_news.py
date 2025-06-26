from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import JSONResponse
import akshare as ak
from ..database import get_db
from sqlalchemy.orm import Session
import traceback
import datetime
import sqlite3
from backend_api.config import DB_PATH
import pandas as pd

router = APIRouter(prefix="/api/stock", tags=["stock_news"])

def clean_nan(obj):
    """清理NaN和inf值"""
    import math
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

@router.get("/news")
async def get_stock_news(
    symbol: str = Query(..., description="股票代码"),
    limit: int = Query(100, description="获取新闻数量，默认100条")
):
    """
    获取指定股票代码的新闻资讯数据
    """
    try:
        print(f"[stock_news] 获取股票新闻: symbol={symbol}, limit={limit}")
        
        # 调用AkShare获取新闻数据
        df = ak.stock_news_em(symbol=symbol)
        
        if df is None or df.empty:
            print(f"[stock_news] 未获取到新闻数据: {symbol}")
            return JSONResponse({"success": False, "message": f"未获取到股票 {symbol} 的新闻数据"}, status_code=404)
        
        print(f"[stock_news] 获取到 {len(df)} 条原始新闻数据")
        print(f"[stock_news] DataFrame columns: {df.columns.tolist()}")
        
        # 限制数量
        if len(df) > limit:
            df = df.head(limit)
        
        # 数据清理和格式化
        result = []
        for _, row in df.iterrows():
            # 处理发布时间
            publish_time = row.get('发布时间', '') or row.get('时间', '') or row.get('更新时间', '')
            if pd.isna(publish_time):
                publish_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                # 如果是datetime对象，转换为字符串
                if hasattr(publish_time, 'strftime'):
                    publish_time = publish_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    publish_time = str(publish_time)
            
            news_item = {
                "id": row.get('序号', '') or '',
                "title": row.get('新闻标题', '') or row.get('标题', '') or '',
                "content": row.get('新闻内容', '') or row.get('内容', '') or '',
                "keywords": row.get('关键词', '') or '',
                "publish_time": publish_time,
                "source": row.get('文章来源', '') or row.get('来源', '') or '东方财富',
                "url": row.get('新闻链接', '') or row.get('链接', '') or '',
                "summary": row.get('摘要', '') or '',
                "type": "news"
            }
            result.append(news_item)
        
        # 清理数据
        result = clean_nan(result)
        
        # 保存到数据库
        await save_news_to_db(symbol, result)
        
        print(f"[stock_news] 成功返回 {len(result)} 条新闻数据")
        return JSONResponse({"success": True, "data": result, "total": len(result)})
        
    except Exception as e:
        print(f"[stock_news] 获取新闻数据异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"获取新闻数据失败: {str(e)}"}, status_code=500)

@router.get("/announcements")
async def get_stock_announcements(
    symbol: str = Query(..., description="股票代码"),
    limit: int = Query(50, description="获取公告数量，默认50条")
):
    """
    获取指定股票代码的公告数据
    """
    try:
        print(f"[stock_announcements] 获取股票公告: symbol={symbol}, limit={limit}")
        
        # 调用AkShare获取公告数据
        df = ak.stock_notice_report(symbol=symbol)
        
        if df is None or df.empty:
            print(f"[stock_announcements] 未获取到公告数据: {symbol}")
            return JSONResponse({"success": False, "message": f"未获取到股票 {symbol} 的公告数据"}, status_code=404)
        
        print(f"[stock_announcements] 获取到 {len(df)} 条原始公告数据")
        print(f"[stock_announcements] DataFrame columns: {df.columns.tolist()}")
        
        # 限制数量
        if len(df) > limit:
            df = df.head(limit)
        
        # 数据清理和格式化
        result = []
        for _, row in df.iterrows():
            # 处理发布时间
            publish_time = row.get('公告日期', '') or row.get('时间', '') or row.get('更新时间', '')
            if pd.isna(publish_time):
                publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
            else:
                # 如果是datetime对象，转换为字符串
                if hasattr(publish_time, 'strftime'):
                    publish_time = publish_time.strftime('%Y-%m-%d')
                else:
                    publish_time = str(publish_time)
            
            announcement_item = {
                "id": row.get('序号', '') or '',
                "title": row.get('公告标题', '') or row.get('标题', '') or '',
                "content": row.get('公告摘要', '') or row.get('摘要', '') or '',
                "keywords": "",
                "publish_time": publish_time,
                "source": "上市公司公告",
                "url": row.get('公告链接', '') or row.get('相关链接', '') or '',
                "summary": row.get('公告摘要', '') or row.get('摘要', '') or '',
                "type": "announcement"
            }
            result.append(announcement_item)
        
        # 清理数据
        result = clean_nan(result)
        
        # 保存到数据库
        await save_news_to_db(symbol, result)
        
        print(f"[stock_announcements] 成功返回 {len(result)} 条公告数据")
        return JSONResponse({"success": True, "data": result, "total": len(result)})
        
    except Exception as e:
        print(f"[stock_announcements] 获取公告数据异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"获取公告数据失败: {str(e)}"}, status_code=500)

@router.get("/research_reports")
async def get_stock_research_reports(
    symbol: str = Query(..., description="股票代码"),
    limit: int = Query(20, description="获取研报数量，默认20条")
):
    """
    获取指定股票代码的研报数据
    """
    try:
        print(f"[stock_research] 获取股票研报: symbol={symbol}, limit={limit}")
        
        # 调用AkShare获取研报数据
        df = ak.stock_research_report_em(symbol=symbol)
        
        if df is None or df.empty:
            print(f"[stock_research] 未获取到研报数据: {symbol}")
            return JSONResponse({"success": False, "message": f"未获取到股票 {symbol} 的研报数据"}, status_code=404)
        
        print(f"[stock_research] 获取到 {len(df)} 条原始研报数据")
        print(f"[stock_research] DataFrame columns: {df.columns.tolist()}")
        
        # 限制数量
        if len(df) > limit:
            df = df.head(limit)
        
        # 数据清理和格式化
        result = []
        for _, row in df.iterrows():
            # 处理发布时间
            publish_time = row.get('发布日期', '') or row.get('时间', '') or row.get('更新时间', '')
            if pd.isna(publish_time):
                publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
            else:
                # 如果是datetime对象，转换为字符串
                if hasattr(publish_time, 'strftime'):
                    publish_time = publish_time.strftime('%Y-%m-%d')
                else:
                    publish_time = str(publish_time)
            
            research_item = {
                "id": row.get('序号', '') or '',
                "title": row.get('研报标题', '') or row.get('标题', '') or '',
                "content": row.get('研报摘要', '') or row.get('摘要', '') or '',
                "keywords": row.get('评级', '') or '',
                "publish_time": publish_time,
                "source": row.get('机构名称', '') or row.get('券商名称', '') or '研究机构',
                "url": row.get('研报链接', '') or row.get('链接', '') or '',
                "summary": row.get('研报摘要', '') or row.get('投资要点', '') or '',
                "type": "research",
                "rating": row.get('评级', '') or row.get('投资评级', '') or '',
                "target_price": row.get('目标价', '') or row.get('目标价格', '') or ''
            }
            result.append(research_item)
        
        # 清理数据
        result = clean_nan(result)
        
        # 保存到数据库
        await save_news_to_db(symbol, result)
        
        print(f"[stock_research] 成功返回 {len(result)} 条研报数据")
        return JSONResponse({"success": True, "data": result, "total": len(result)})
        
    except Exception as e:
        print(f"[stock_research] 获取研报数据异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"获取研报数据失败: {str(e)}"}, status_code=500)

@router.get("/news_combined")
async def get_stock_news_combined(
    symbol: str = Query(..., description="股票代码"),
    news_limit: int = Query(50, description="新闻数量"),
    announcement_limit: int = Query(20, description="公告数量"),
    research_limit: int = Query(10, description="研报数量")
):
    """
    获取指定股票代码的综合资讯数据（新闻+公告+研报）
    """
    try:
        print(f"[stock_news_combined] 获取综合资讯: symbol={symbol}")
        
        all_data = []
        
        # 获取新闻数据
        try:
            news_df = ak.stock_news_em(symbol=symbol)
            if news_df is not None and not news_df.empty:
                news_df = news_df.head(news_limit)
                for _, row in news_df.iterrows():
                    publish_time = row.get('发布时间', '') or row.get('时间', '')
                    if pd.isna(publish_time):
                        publish_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        if hasattr(publish_time, 'strftime'):
                            publish_time = publish_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            publish_time = str(publish_time)
                    
                    news_item = {
                        "id": f"news_{row.get('序号', '')}" or f"news_{len(all_data)}",
                        "title": row.get('新闻标题', '') or row.get('标题', '') or '',
                        "content": row.get('新闻内容', '') or row.get('内容', '') or '',
                        "keywords": row.get('关键词', '') or '',
                        "publish_time": publish_time,
                        "source": row.get('文章来源', '') or '东方财富',
                        "url": row.get('新闻链接', '') or '',
                        "summary": row.get('摘要', '') or '',
                        "type": "news"
                    }
                    all_data.append(news_item)
        except Exception as e:
            print(f"[stock_news_combined] 获取新闻数据失败: {e}")
        
        # 获取公告数据
        try:
            announcement_df = ak.stock_notice_report(symbol=symbol)
            if announcement_df is not None and not announcement_df.empty:
                announcement_df = announcement_df.head(announcement_limit)
                for _, row in announcement_df.iterrows():
                    publish_time = row.get('公告日期', '') or row.get('时间', '')
                    if pd.isna(publish_time):
                        publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
                    else:
                        if hasattr(publish_time, 'strftime'):
                            publish_time = publish_time.strftime('%Y-%m-%d')
                        else:
                            publish_time = str(publish_time)
                    
                    announcement_item = {
                        "id": f"ann_{row.get('序号', '')}" or f"ann_{len(all_data)}",
                        "title": row.get('公告标题', '') or row.get('标题', '') or '',
                        "content": row.get('公告摘要', '') or '',
                        "keywords": "",
                        "publish_time": publish_time,
                        "source": "上市公司公告",
                        "url": row.get('公告链接', '') or '',
                        "summary": row.get('公告摘要', '') or '',
                        "type": "announcement"
                    }
                    all_data.append(announcement_item)
        except Exception as e:
            print(f"[stock_news_combined] 获取公告数据失败: {e}")
        
        # 获取研报数据
        try:
            research_df = ak.stock_research_report_em(symbol=symbol)
            if research_df is not None and not research_df.empty:
                research_df = research_df.head(research_limit)
                for _, row in research_df.iterrows():
                    publish_time = row.get('发布日期', '') or row.get('时间', '')
                    if pd.isna(publish_time):
                        publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
                    else:
                        if hasattr(publish_time, 'strftime'):
                            publish_time = publish_time.strftime('%Y-%m-%d')
                        else:
                            publish_time = str(publish_time)
                    
                    research_item = {
                        "id": f"res_{row.get('序号', '')}" or f"res_{len(all_data)}",
                        "title": row.get('研报标题', '') or row.get('标题', '') or '',
                        "content": row.get('研报摘要', '') or '',
                        "keywords": row.get('评级', '') or '',
                        "publish_time": publish_time,
                        "source": row.get('机构名称', '') or '研究机构',
                        "url": row.get('研报链接', '') or '',
                        "summary": row.get('研报摘要', '') or '',
                        "type": "research",
                        "rating": row.get('评级', '') or '',
                        "target_price": row.get('目标价', '') or ''
                    }
                    all_data.append(research_item)
        except Exception as e:
            print(f"[stock_news_combined] 获取研报数据失败: {e}")
        
        # 按发布时间排序
        all_data.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
        
        # 清理数据
        all_data = clean_nan(all_data)
        
        # 保存到数据库
        await save_news_to_db(symbol, all_data)
        
        print(f"[stock_news_combined] 成功返回 {len(all_data)} 条综合资讯数据")
        return JSONResponse({"success": True, "data": all_data, "total": len(all_data)})
        
    except Exception as e:
        print(f"[stock_news_combined] 获取综合资讯异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"获取综合资讯失败: {str(e)}"}, status_code=500)

async def save_news_to_db(symbol: str, news_data: list):
    """保存新闻数据到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 先删除该股票的旧数据（保持当日最新）
        today = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute(
            "DELETE FROM stock_news WHERE stock_code = ? AND DATE(created_at) = ?",
            (symbol, today)
        )
        
        # 插入新数据
        for item in news_data:
            cursor.execute("""
                INSERT OR REPLACE INTO stock_news 
                (stock_code, title, content, keywords, publish_time, source, url, summary, type, rating, target_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                item.get('title', ''),
                item.get('content', ''),
                item.get('keywords', ''),
                item.get('publish_time', ''),
                item.get('source', ''),
                item.get('url', ''),
                item.get('summary', ''),
                item.get('type', 'news'),
                item.get('rating', ''),
                item.get('target_price', ''),
                datetime.datetime.now()
            ))
        
        conn.commit()
        conn.close()
        print(f"[save_news_to_db] 成功保存 {len(news_data)} 条数据到数据库")
        
    except Exception as e:
        print(f"[save_news_to_db] 保存数据到数据库失败: {e}")
        print(traceback.format_exc())

@router.get("/news_from_db")
async def get_stock_news_from_db(
    symbol: str = Query(..., description="股票代码"),
    type_filter: str = Query("all", description="类型过滤: all, news, announcement, research"),
    limit: int = Query(100, description="返回数量限制")
):
    """
    从数据库获取股票新闻数据
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 构建查询SQL
        if type_filter == "all":
            sql = """
                SELECT title, content, keywords, publish_time, source, url, summary, type, rating, target_price, created_at
                FROM stock_news 
                WHERE stock_code = ? 
                ORDER BY publish_time DESC, created_at DESC
                LIMIT ?
            """
            cursor.execute(sql, (symbol, limit))
        else:
            sql = """
                SELECT title, content, keywords, publish_time, source, url, summary, type, rating, target_price, created_at
                FROM stock_news 
                WHERE stock_code = ? AND type = ?
                ORDER BY publish_time DESC, created_at DESC
                LIMIT ?
            """
            cursor.execute(sql, (symbol, type_filter, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 格式化数据
        data = []
        for i, row in enumerate(rows):
            data.append({
                "id": f"{type_filter}_{i}",
                "title": row[0],
                "content": row[1],
                "keywords": row[2],
                "publish_time": row[3],
                "source": row[4],
                "url": row[5],
                "summary": row[6],
                "type": row[7],
                "rating": row[8] or '',
                "target_price": row[9] or ''
            })
        
        print(f"[stock_news_from_db] 从数据库返回 {len(data)} 条新闻数据")
        return JSONResponse({"success": True, "data": data, "total": len(data)})
        
    except Exception as e:
        print(f"[stock_news_from_db] 从数据库获取新闻数据异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"从数据库获取新闻数据失败: {str(e)}"}, status_code=500)