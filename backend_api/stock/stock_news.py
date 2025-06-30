from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import akshare as ak
from ..database import get_db
from sqlalchemy.orm import Session
import traceback
import datetime
import sqlite3
from backend_api.config import DB_PATH
import pandas as pd
import difflib
import time
import aiohttp
import logging

logger = logging.getLogger(__name__)

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

def is_news_related_to_stock(title: str, content: str, stock_info: dict) -> bool:
    """
    检查新闻是否与指定股票相关
    
    Args:
        title: 新闻标题
        content: 新闻内容  
        stock_info: 股票信息字典，包含name和code
    
    Returns:
        bool: 是否相关
    """
    try:
        stock_name = stock_info.get('name', '').strip()
        stock_code = stock_info.get('code', '').strip()
        
        # 如果股票名称或代码为空,返回True(避免过度过滤)
        if not stock_name and not stock_code:
            return True
            
        # 合并标题和内容进行检查
        text_to_check = f"{title} {content}".lower()
        
        # 检查股票代码(去掉前缀，如SZ、SH等)
        if stock_code:
            clean_code = stock_code
            if '.' in clean_code:
                clean_code = clean_code.split('.')[0]
            
            # 检查完整代码和清理后的代码
            if stock_code.lower() in text_to_check or clean_code in text_to_check:
                return True
        
        # 检查股票名称
        if stock_name and len(stock_name) >= 2:
            # 完整股票名称匹配
            if stock_name in text_to_check:
                return True
                
            # 移除常见后缀后匹配（如"股份"、"有限公司"、"集团"等）
            import re
            clean_name = re.sub(r'(股份|有限公司|集团|公司|控股|投资|科技|实业)$', '', stock_name)
            if len(clean_name) >= 2 and clean_name in text_to_check:
                return True
                
            # 检查股票简称（通常是前2-4个字符）
            if len(stock_name) >= 3:
                short_name = stock_name[:3]
                if short_name in text_to_check:
                    return True
        
        # 过滤明显无关的通用新闻关键词
        irrelevant_keywords = [
            '华为', '苹果', '特斯拉', '比亚迪', '小米', '腾讯', '阿里', '百度',
            '美联储', '央行', '拜登', '特朗普', '欧盟', '日本', '韩国',
            '比特币', '数字货币', '房地产', '楼市', '油价', '黄金',
            '奥运', '世界杯', '疫情', '新冠', 'AI', '人工智能',
            '芯片', '半导体', '新能源', '电动车', '锂电池'
        ]
        
        # 如果包含无关关键词但不包含股票相关信息，则认为不相关
        has_irrelevant = any(keyword in text_to_check for keyword in irrelevant_keywords)
        if has_irrelevant:
            # 二次确认：即使有无关关键词，如果明确提到该股票，仍然认为相关
            if stock_name and stock_name in text_to_check:
                return True
            if stock_code and stock_code.lower() in text_to_check:
                return True
            # 包含无关关键词且不提及该股票，认为不相关
            return False
        
        # 默认认为相关（保守策略，避免过度过滤）
        return True
        
    except Exception as e:
        print(f"[is_news_related_to_stock] 检查新闻相关性异常: {e}")
        # 出现异常时保守处理，认为相关
        return True

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

def init_stock_research_table():
    """初始化个股研报信息表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建个股研报信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_research_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,                    -- 股票代码
                stock_name TEXT,                             -- 股票简称
                report_name TEXT NOT NULL,                   -- 报告名称
                dongcai_rating TEXT,                         -- 东财评级
                institution TEXT,                            -- 机构
                monthly_report_count INTEGER DEFAULT 0,      -- 近一个月研报数
                profit_2024 REAL,                           -- 2024-盈利预测-收益
                pe_2024 REAL,                               -- 2024-盈利预测-市盈率
                profit_2025 REAL,                           -- 2025-盈利预测-收益
                pe_2025 REAL,                               -- 2025-盈利预测-市盈率
                profit_2026 REAL,                           -- 2026-盈利预测-收益
                pe_2026 REAL,                               -- 2026-盈利预测-市盈率
                industry TEXT,                              -- 行业
                report_date TEXT,                           -- 日期
                pdf_url TEXT,                               -- 报告PDF链接
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, report_name, report_date)
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_research_code ON stock_research_reports(stock_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_research_date ON stock_research_reports(report_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_research_institution ON stock_research_reports(institution)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_research_rating ON stock_research_reports(dongcai_rating)")
        
        conn.commit()
        conn.close()
        print("[init_stock_research_table] 个股研报信息表初始化成功")
        
    except Exception as e:
        print(f"[init_stock_research_table] 初始化个股研报信息表失败: {e}")
        import traceback
        traceback.print_exc()

async def _get_research_data(symbol: str, limit: int = 20) -> list:
    """
    获取研报数据的内部函数
    
    Args:
        symbol: 股票代码
        limit: 研报数量限制
        
    Returns:
        list: 研报数据列表
    """
    research_data = []
    
    try:
        print(f"[_get_research_data] 开始获取{symbol}的研报数据...")
        
        # 添加延迟避免请求过于频繁
        time.sleep(2)  # 增加延迟到2秒
        
        # 尝试获取研报数据，如果失败则重试
        max_retries = 3
        retry_count = 0
        research_df = None
        
        while retry_count < max_retries:
            try:
                print(f"[_get_research_data] 第{retry_count + 1}次尝试获取研报数据...")
                research_df = ak.stock_research_report_em(symbol=symbol)
                if research_df is not None:
                    print(f"[_get_research_data] 成功获取研报数据")
                    break
                else:
                    print(f"[_get_research_data] 返回数据为空")
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                print(f"[_get_research_data] 第{retry_count}次请求失败: {error_msg}")
                
                # 检查是否是访问受限错误
                if "访问受限" in error_msg or "安全策略" in error_msg or "EdgeOne" in error_msg:
                    print(f"[_get_research_data] 检测到访问受限，使用更长等待时间")
                    wait_time = retry_count * 10  # 10秒、20秒、30秒
                else:
                    wait_time = retry_count * 5   # 5秒、10秒、15秒
                
                if retry_count < max_retries:
                    print(f"[_get_research_data] 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"[_get_research_data] 达到最大重试次数，返回空数据")
                    research_df = None
                    break
        
        if research_df is not None and not research_df.empty:
            print(f"[_get_research_data] AkShare返回{len(research_df)}条原始数据")
            print(f"[_get_research_data] 数据字段: {list(research_df.columns)}")
            research_df = research_df.head(limit)
            for _, row in research_df.iterrows():
                # 根据实际字段结构获取数据
                publish_time = row.get('日期', '')
                if pd.isna(publish_time):
                    publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
                else:
                    if hasattr(publish_time, 'strftime'):
                        publish_time = publish_time.strftime('%Y-%m-%d')
                    else:
                        publish_time = str(publish_time)
                
                # 根据实际字段名获取数据
                title = str(row.get('报告名称', '')).strip() if not pd.isna(row.get('报告名称', '')) else ''
                rating = str(row.get('东财评级', '')).strip() if not pd.isna(row.get('东财评级', '')) else ''
                source = str(row.get('机构', '')).strip() if not pd.isna(row.get('机构', '')) else ''
                url = str(row.get('报告PDF链接', '')).strip() if not pd.isna(row.get('报告PDF链接', '')) else ''
                
                # 获取盈利预测数据
                profit_2024 = row.get('2024-盈利预测-收益', None) if not pd.isna(row.get('2024-盈利预测-收益', None)) else None
                pe_2024 = row.get('2024-盈利预测-市盈率', None) if not pd.isna(row.get('2024-盈利预测-市盈率', None)) else None
                profit_2025 = row.get('2025-盈利预测-收益', None) if not pd.isna(row.get('2025-盈利预测-收益', None)) else None
                pe_2025 = row.get('2025-盈利预测-市盈率', None) if not pd.isna(row.get('2025-盈利预测-市盈率', None)) else None
                profit_2026 = row.get('2026-盈利预测-收益', None) if not pd.isna(row.get('2026-盈利预测-收益', None)) else None
                pe_2026 = row.get('2026-盈利预测-市盈率', None) if not pd.isna(row.get('2026-盈利预测-市盈率', None)) else None
                
                # 获取行业信息
                industry = str(row.get('行业', '')).strip() if not pd.isna(row.get('行业', '')) else ''
                
                # 获取近一月研报数
                monthly_count = row.get('近一月个股研报数', 0) if not pd.isna(row.get('近一月个股研报数', 0)) else 0
                
                research_item = {
                    "id": f"res_{row.get('序号', len(research_data))}",
                    "title": title if title else '研报标题',
                    "content": '',  # 研报内容字段不在数据中
                    "keywords": rating,
                    "publish_time": publish_time,
                    "source": source if source else '研究机构',
                    "url": url,
                    "summary": '',  # 摘要字段不在数据中
                    "type": "research",
                    "rating": rating if rating else '未评级',
                    "target_price": '',  # 目标价字段不在数据中
                    # 新增字段用于数据库保存
                    "profit_2024": profit_2024,
                    "pe_2024": pe_2024,
                    "profit_2025": profit_2025,
                    "pe_2025": pe_2025,
                    "profit_2026": profit_2026,
                    "pe_2026": pe_2026,
                    "industry": industry,
                    "monthly_count": monthly_count
                }
                research_data.append(research_item)
                
                # 调试：显示前3条处理后的数据
                if len(research_data) <= 3:
                    print(f"[_get_research_data] 第{len(research_data)}条处理后数据:")
                    print(f"  title: {research_item['title']}")
                    print(f"  rating: {research_item['rating']}")
                    print(f"  source: {research_item['source']}")
                    print(f"  summary: {research_item['summary'][:50]}..." if len(research_item['summary']) > 50 else f"  summary: {research_item['summary']}")
        
        else:
            print(f"[_get_research_data] AkShare未返回{symbol}的研报数据（可能该股票没有研报）")
            
            # 如果AkShare获取失败，不提供模拟数据，直接返回空列表
            print(f"[_get_research_data] AkShare获取失败，{symbol}暂无研报数据")
            research_data = []
                    
        print(f"[_get_research_data] 最终获取到 {len(research_data)} 条研报数据")
        
    except Exception as e:
        print(f"[_get_research_data] 获取研报数据失败: {e}")
        import traceback
        print(f"[_get_research_data] 错误详情: {traceback.format_exc()}")
    
    return research_data

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
        
        # 获取股票基本信息用于新闻过滤
        stock_name = await get_stock_name(symbol)
        stock_info = {"name": stock_name, "code": symbol}
        
        # 获取新闻数据
        try:
            news_df = ak.stock_news_em(symbol=symbol)
            if news_df is not None and not news_df.empty:
                print(f"[stock_news_combined] AkShare返回{len(news_df)}条原始新闻数据")
                
                # 过滤新闻 - 只保留与该股票相关的新闻
                filtered_news_count = 0
                for _, row in news_df.iterrows():
                    title = row.get('新闻标题', '') or row.get('标题', '') or ''
                    content = row.get('新闻内容', '') or row.get('内容', '') or ''
                    
                    # 检查新闻是否与该股票相关
                    if not is_news_related_to_stock(title, content, stock_info):
                        continue
                        
                    filtered_news_count += 1
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
                        "title": title,
                        "content": content,
                        "keywords": row.get('关键词', '') or '',
                        "publish_time": publish_time,
                        "source": row.get('文章来源', '') or '东方财富',
                        "url": row.get('新闻链接', '') or '',
                        "summary": row.get('摘要', '') or '',
                        "type": "news"
                    }
                    all_data.append(news_item)
                
                print(f"[stock_news_combined] 过滤后保留{filtered_news_count}条相关新闻")
        except Exception as e:
            print(f"[stock_news_combined] 获取新闻数据失败: {e}")
        
        # 获取公告数据
        try:
            # 直接连接SQLite数据库获取公告数据
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    id,
                    code,
                    name,
                    notice_title,
                    notice_type,
                    publish_date,
                    url,
                    created_at
                FROM stock_notice_report 
                WHERE code = ? 
                ORDER BY publish_date DESC 
                LIMIT ?
            """
            cursor.execute(query, (symbol, announcement_limit))
            announcement_data = cursor.fetchall()
            
            # 将结果转换为字典列表
            columns = ['id', 'code', 'name', 'notice_title', 'notice_type', 'publish_date', 'url', 'created_at']
            announcement_data = [dict(zip(columns, row)) for row in announcement_data]
            
            conn.close()
            
            if announcement_data:
                print(f"[stock_news_combined] 从数据库获取到公告数据: {len(announcement_data)} 条")
                for i, row in enumerate(announcement_data[:3]):
                    print(f"  第{i+1}条: {dict(row)}")
            else:
                print(f"[stock_news_combined] 未从数据库获取到公告数据")
            
            if announcement_data:
                for row in announcement_data:
                    publish_time = row.get('publish_date', '')
                    if not publish_time:
                        publish_time = datetime.datetime.now().strftime('%Y-%m-%d')
                    else:
                        if hasattr(publish_time, 'strftime'):
                            publish_time = publish_time.strftime('%Y-%m-%d')
                        else:
                            publish_time = str(publish_time)
                    
                    announcement_item = {
                        "id": f"ann_{row.get('id', '')}" or f"ann_{len(all_data)}",
                        "title": row.get('notice_title', '') or '',
                        "content": row.get('notice_title', '') or '',  # 使用公告标题作为内容
                        "keywords": row.get('notice_type', '') or '',
                        "publish_time": publish_time,
                        "source": "上市公司公告",
                        "url": row.get('url', '') or '',
                        "summary": row.get('notice_title', '') or '',
                        "type": "announcement"
                    }
                    all_data.append(announcement_item)
        except Exception as e:
            print(f"[stock_news_combined] 获取公告数据失败: {e}")
        
        # 获取研报数据 - 调用独立的研报获取逻辑
        try:
            research_data = await _get_research_data(symbol=symbol, limit=research_limit)
            if research_data:
                all_data.extend(research_data)
                print(f"[stock_news_combined] 从研报数据获取到 {len(research_data)} 条研报数据")
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

async def save_research_reports_to_db(symbol: str, research_data: list):
    """保存研报信息到个股研报信息表"""
    try:
        # 确保表已创建
        init_stock_research_table()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 获取股票名称（从其他表或API获取）
        stock_name = await get_stock_name(symbol)
        
        # 获取近一个月研报数
        monthly_count = len(research_data)
        
        saved_count = 0
        for i, item in enumerate(research_data):
            try:
                # 提取和处理各字段
                report_name = item.get('title', '').strip()
                
                # 调试信息
                print(f"[DEBUG] 第{i+1}条研报: title='{report_name}', rating='{item.get('rating', '')}', source='{item.get('source', '')}'")
                
                # 修改过滤条件 - 允许默认标题但添加序号
                if not report_name:
                    report_name = f"研报_{symbol}_{i+1}"
                elif report_name in ['研报标题', '暂无研报标题']:
                    report_name = f"{report_name}_{symbol}_{i+1}"
                
                dongcai_rating = item.get('rating', '').strip()
                institution = item.get('source', '').strip()
                report_date = item.get('publish_time', '').split(' ')[0] if item.get('publish_time') else ''
                pdf_url = item.get('url', '').strip()
                
                print(f"[DEBUG] 准备保存研报: {report_name}")
                
                # 直接从研报数据中获取盈利预测信息
                profit_2024 = item.get('profit_2024', None)
                pe_2024 = item.get('pe_2024', None)
                profit_2025 = item.get('profit_2025', None)
                pe_2025 = item.get('pe_2025', None)
                profit_2026 = item.get('profit_2026', None)
                pe_2026 = item.get('pe_2026', None)
                
                # 直接从研报数据中获取行业信息
                industry = item.get('industry', '') or await get_stock_industry(symbol)
                
                # 获取近一月研报数
                monthly_count = item.get('monthly_count', len(research_data))
                
                # 插入或更新数据
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_research_reports 
                    (stock_code, stock_name, report_name, dongcai_rating, institution, 
                     monthly_report_count, profit_2024, pe_2024, profit_2025, pe_2025, 
                     profit_2026, pe_2026, industry, report_date, pdf_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    stock_name,
                    report_name,
                    dongcai_rating if dongcai_rating and dongcai_rating != '未评级' else None,
                    institution if institution and institution != '研究机构' else None,
                    monthly_count,
                    profit_2024,
                    pe_2024,
                    profit_2025,
                    pe_2025,
                    profit_2026,
                    pe_2026,
                    industry,
                    report_date if report_date else None,
                    pdf_url if pdf_url else None,
                    datetime.datetime.now()
                ))
                
                saved_count += 1
                print(f"[DEBUG] 成功保存第{i+1}条研报: {report_name}")
                
            except Exception as e:
                print(f"[save_research_reports_to_db] 保存第{i+1}条研报数据失败: {e}")
                print(f"[DEBUG] 失败的研报数据: {item}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"[save_research_reports_to_db] 成功保存 {saved_count}/{len(research_data)} 条研报数据到数据库")
        
    except Exception as e:
        print(f"[save_research_reports_to_db] 保存研报数据到数据库失败: {e}")
        import traceback
        traceback.print_exc()

def extract_profit_forecast(summary: str, year: str):
    """从研报摘要中提取盈利预测信息"""
    try:
        import re
        
        # 简单的正则表达式匹配盈利预测（需要根据实际数据格式调整）
        profit_pattern = rf'{year}.*?(?:盈利|收益|利润).*?(\d+\.?\d*)'
        pe_pattern = rf'{year}.*?(?:市盈率|PE).*?(\d+\.?\d*)'
        
        profit_match = re.search(profit_pattern, summary)
        pe_match = re.search(pe_pattern, summary)
        
        profit = float(profit_match.group(1)) if profit_match else None
        pe = float(pe_match.group(1)) if pe_match else None
        
        return profit, pe
        
    except Exception:
        return None, None

async def get_stock_name(symbol: str) -> str:
    """获取股票名称"""
    try:
        # 尝试从AkShare获取股票基本信息
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        if stock_info is not None and not stock_info.empty:
            # 查找股票名称字段
            name_row = stock_info[stock_info['item'] == '股票简称']
            if not name_row.empty:
                return str(name_row['value'].iloc[0]).strip()
    except Exception as e:
        print(f"[get_stock_name] 获取股票名称失败: {e}")
    
    return ""

async def get_stock_industry(symbol: str) -> str:
    """获取股票行业信息"""
    try:
        # 尝试从AkShare获取股票基本信息
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        if stock_info is not None and not stock_info.empty:
            # 查找行业字段
            industry_row = stock_info[stock_info['item'] == '所处行业']
            if not industry_row.empty:
                return str(industry_row['value'].iloc[0]).strip()
    except Exception as e:
        print(f"[get_stock_industry] 获取股票行业失败: {e}")
    
    return ""

@router.get("/research_reports")
async def get_research_reports(
    symbol: str = Query(..., description="股票代码"),
    limit: int = Query(20, description="研报数量限制")
):
    """
    获取指定股票代码的研报数据
    """
    try:
        print(f"[research_reports] 获取研报数据: symbol={symbol}, limit={limit}")
        
        # 调用内部研报数据获取函数
        research_data = await _get_research_data(symbol=symbol, limit=limit)
        
        # 清理数据
        research_data = clean_nan(research_data)
        
        # 保存研报信息到数据库
        if research_data:
            await save_research_reports_to_db(symbol=symbol, research_data=research_data)
        
        print(f"[research_reports] 成功返回 {len(research_data)} 条研报数据")
        return JSONResponse({"success": True, "data": research_data, "total": len(research_data)})
        
    except Exception as e:
        print(f"[research_reports] 获取研报数据异常: {e}")
        print(traceback.format_exc())
        return JSONResponse({"success": False, "message": f"获取研报数据失败: {str(e)}"}, status_code=500)

@router.get("/download_pdf")
async def download_pdf_proxy(
    url: str = Query(..., description="PDF文件URL"),
    filename: str = Query(None, description="下载文件名")
):
    """
    代理下载PDF文件，解决前端跨域问题
    """
    try:
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 使用aiohttp获取PDF文件
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"无法获取PDF文件，状态码: {response.status}"
                    )
                
                # 检查内容类型
                content_type = response.headers.get('content-type', '')
                if 'pdf' not in content_type.lower() and 'octet-stream' not in content_type.lower():
                    # 如果不是PDF，可能是错误页面，检查内容
                    content_preview = await response.text()
                    if len(content_preview) < 10000 and ('error' in content_preview.lower() or 'access denied' in content_preview.lower()):
                        raise HTTPException(status_code=400, detail="访问被拒绝或文件不存在")
                
                # 设置下载文件名
                if not filename:
                    # 从URL或响应头中提取文件名
                    content_disposition = response.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"\'')
                    else:
                        filename = url.split('/')[-1]
                        if not filename.endswith('.pdf'):
                            filename = "研报.pdf"
                
                # 流式返回PDF内容
                async def generate():
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        yield chunk
                
                return StreamingResponse(
                    generate(),
                    media_type='application/pdf',
                    headers={
                        'Content-Disposition': f'attachment; filename="{filename}"',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Expose-Headers': 'Content-Disposition'
                    }
                )
                
    except aiohttp.ClientError as e:
        logger.error(f"下载PDF失败: {e}")
        raise HTTPException(status_code=400, detail=f"网络请求失败: {str(e)}")
    except Exception as e:
        logger.error(f"代理下载PDF异常: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

@router.get("/pdf_redirect")
async def pdf_redirect_page(
    url: str = Query(..., description="PDF文件URL"),
    title: str = Query("PDF文档", description="文档标题")
):
    """
    生成PDF重定向页面，彻底去除referrer绕过防盗链
    """
    try:
        # 创建HTML重定向页面
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>正在访问: {title}</title>
    <meta name="referrer" content="no-referrer">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            text-align: center;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            width: 90%;
        }}
        .title {{
            font-size: 24px;
            margin-bottom: 20px;
            font-weight: 300;
        }}
        .subtitle {{
            font-size: 16px;
            margin-bottom: 30px;
            opacity: 0.8;
        }}
        .spinner {{
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-top: 3px solid white;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 30px auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .manual-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            transition: all 0.3s ease;
        }}
        .manual-link:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
        .countdown {{
            font-size: 14px;
            opacity: 0.7;
            margin-top: 20px;
        }}
        .url-display {{
            background: rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 8px;
            margin: 20px 0;
            word-break: break-all;
            font-size: 12px;
            font-family: monospace;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="title">正在访问PDF文档</div>
        <div class="subtitle">{title}</div>
        <div class="spinner"></div>
        <div class="countdown">
            <span id="countdown">3</span> 秒后自动跳转...
        </div>
        <a href="javascript:void(0)" onclick="openPDF()" class="manual-link">
            立即访问
        </a>
        <div class="url-display" onclick="copyUrl()" title="点击复制链接">
            {url}
        </div>
        <div style="font-size: 12px; opacity: 0.6; margin-top: 10px;">
            如遇访问限制，请将上方链接复制到新浏览器窗口
        </div>
    </div>

    <script>
        let countdown = 3;
        const countdownElement = document.getElementById('countdown');
        const pdfUrl = `{url}`;
        
        // 倒计时
        const timer = setInterval(() => {{
            countdown--;
            countdownElement.textContent = countdown;
            if (countdown <= 0) {{
                clearInterval(timer);
                openPDF();
            }}
        }}, 1000);
        
        // 打开PDF的函数
        function openPDF() {{
            // 方法1：直接替换当前页面位置（最强力的去referrer方法）
            try {{
                window.location.replace(pdfUrl);
            }} catch(e) {{
                // 方法2：使用window.open
                try {{
                    const newWindow = window.open('about:blank', '_self');
                    newWindow.location.href = pdfUrl;
                }} catch(e2) {{
                    // 方法3：创建表单提交（POST方式不会发送referrer）
                    const form = document.createElement('form');
                    form.method = 'GET';
                    form.action = pdfUrl;
                    form.target = '_blank';
                    form.style.display = 'none';
                    document.body.appendChild(form);
                    form.submit();
                    document.body.removeChild(form);
                }}
            }}
        }}
        
        // 复制URL
        function copyUrl() {{
            if (navigator.clipboard) {{
                navigator.clipboard.writeText(pdfUrl).then(() => {{
                    alert('链接已复制到剪贴板');
                }});
            }} else {{
                // 降级方案
                const textArea = document.createElement('textarea');
                textArea.value = pdfUrl;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert('链接已复制到剪贴板');
            }}
        }}
        
        // 阻止页面被缓存
        window.addEventListener('beforeunload', function() {{
            // 清理定时器
            clearInterval(timer);
        }});
        
        // 防止浏览器记住referrer
        if (document.referrer) {{
            history.replaceState(null, '', location.href);
        }}
    </script>
</body>
</html>
        """
        
        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache", 
                "Expires": "0",
                "Referrer-Policy": "no-referrer"
            }
        )
        
    except Exception as e:
        logger.error(f"生成PDF重定向页面失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成重定向页面失败: {str(e)}")
