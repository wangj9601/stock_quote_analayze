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
import difflib

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

def calculate_similarity(title1, title2):
    """计算两个标题的相似度"""
    if not title1 or not title2:
        return 0.0
    return difflib.SequenceMatcher(None, title1, title2).ratio()

def deduplicate_news(news_list, similarity_threshold=0.8):
    """
    新闻去重函数
    优先保留东方财富网的新闻，相似度超过阈值的新闻只保留一条
    """
    if not news_list:
        return news_list
    
    # 按来源优先级排序：东方财富 > 其他来源
    def get_source_priority(item):
        source = item.get('source', '').lower()
        if '东方财富' in source:
            return 1  # 最高优先级
        elif '财经' in source or '证券' in source:
            return 2  # 财经类媒体次优先
        else:
            return 3  # 其他来源最低优先级
    
    # 先按时间倒序，再按来源优先级排序
    sorted_news = sorted(news_list, key=lambda x: (x.get('publish_time', ''), get_source_priority(x)), reverse=True)
    
    unique_news = []
    processed_titles = []
    
    for news_item in sorted_news:
        title = news_item.get('title', '')
        if not title:
            continue
            
        # 检查是否与已处理的标题相似
        is_duplicate = False
        for processed_title in processed_titles:
            similarity = calculate_similarity(title, processed_title)
            if similarity >= similarity_threshold:
                is_duplicate = True
                print(f"[deduplicate_news] 发现重复新闻: '{title}' 与 '{processed_title}' 相似度: {similarity:.2f}")
                break
        
        if not is_duplicate:
            unique_news.append(news_item)
            processed_titles.append(title)
    
    print(f"[deduplicate_news] 去重前: {len(news_list)} 条，去重后: {len(unique_news)} 条")
    return unique_news

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
        
        # 去重处理 - 在合并后统一去重，这样可以跨类型去重
        all_data = deduplicate_news(all_data)
        
        # 按发布时间排序
        all_data.sort(key=lambda x: x.get('publish_time', ''), reverse=True)
        
        # 根据类型限制数量
        news_count = 0
        announcement_count = 0
        research_count = 0
        filtered_data = []
        
        for item in all_data:
            item_type = item.get('type', '')
            if item_type == 'news' and news_count < news_limit:
                filtered_data.append(item)
                news_count += 1
            elif item_type == 'announcement' and announcement_count < announcement_limit:
                filtered_data.append(item)
                announcement_count += 1
            elif item_type == 'research' and research_count < research_limit:
                filtered_data.append(item)
                research_count += 1
        
        # 清理数据
        filtered_data = clean_nan(filtered_data)
        
        # 保存到数据库
        await save_news_to_db(symbol, filtered_data)
        
        print(f"[stock_news_combined] 成功返回 {len(filtered_data)} 条综合资讯数据 (新闻:{news_count}, 公告:{announcement_count}, 研报:{research_count})")
        return JSONResponse({"success": True, "data": filtered_data, "total": len(filtered_data)})
        
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
