"""
ETF基金管理端API路由
前缀: /api/admin/etf
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from backend_api.database import get_db
from backend_api.models import FundBasicInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/etf", tags=["ETF基金管理"])

# 全局任务状态
_etf_task_status = {
    'is_running': False,
    'task_type': None,
    'progress': 0,
    'message': '',
    'result': None,
    'start_time': None
}


# ---------- 请求体 ----------
class ETFCollectBody(BaseModel):
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    etf_codes: Optional[list] = Field(None, description="指定ETF代码列表，空则采集全部")


# ---------- 接口 ----------

@router.get("/list")
async def list_etf_funds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = Query(None, description="按代码或名称搜索"),
    db: Session = Depends(get_db),
):
    """获取ETF基金列表"""
    try:
        query = db.query(FundBasicInfo)
        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                (FundBasicInfo.code.like(kw)) | (FundBasicInfo.name.like(kw))
            )
        total = query.count()
        rows = (
            query.order_by(FundBasicInfo.code.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        data = []
        for r in rows:
            data.append({
                'code': r.code,
                'name': r.name,
                'fund_type': r.fund_type,
                'listing_date': r.listing_date,
                'fund_company': r.fund_company,
                'collect_enabled': bool(r.collect_enabled) if r.collect_enabled is not None else True,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'updated_at': r.updated_at.isoformat() if r.updated_at else None,
            })
        return {
            'success': True,
            'data': data,
            'total': total,
            'page': page,
            'page_size': page_size
        }
    except Exception as e:
        logger.exception("获取ETF列表失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_etf_stats(db: Session = Depends(get_db)):
    """获取ETF统计信息"""
    try:
        total = db.query(func.count(FundBasicInfo.code)).scalar() or 0
        active = db.query(func.count(FundBasicInfo.code)).filter(
            FundBasicInfo.collect_enabled == True
        ).scalar() or 0

        # 历史行情数据统计
        hist_count = 0
        try:
            result = db.execute(text("SELECT COUNT(*) FROM fund_historical_quotes"))
            hist_count = result.scalar() or 0
        except Exception:
            pass

        # 最近采集日期
        latest_date = None
        try:
            result = db.execute(text(
                "SELECT MAX(date) FROM fund_historical_quotes"
            ))
            row = result.fetchone()
            if row and row[0]:
                latest_date = str(row[0])
        except Exception:
            pass

        return {
            'success': True,
            'data': {
                'total_funds': total,
                'active_funds': active,
                'historical_records': hist_count,
                'latest_date': latest_date,
                'task_running': _etf_task_status['is_running'],
            }
        }
    except Exception as e:
        logger.exception("获取ETF统计失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task-status")
async def get_task_status():
    """获取当前ETF采集任务状态"""
    return {
        'success': True,
        'data': {
            'is_running': _etf_task_status['is_running'],
            'task_type': _etf_task_status['task_type'],
            'progress': _etf_task_status['progress'],
            'message': _etf_task_status['message'],
            'result': _etf_task_status['result'],
            'start_time': _etf_task_status['start_time'],
        }
    }


@router.post("/sync-list")
async def sync_etf_list():
    """同步ETF基础信息列表"""
    global _etf_task_status
    if _etf_task_status['is_running']:
        raise HTTPException(status_code=400, detail="已有ETF任务正在运行，请等待完成")

    _etf_task_status = {
        'is_running': True,
        'task_type': 'sync_list',
        'progress': 0,
        'message': '正在同步ETF列表...',
        'result': None,
        'start_time': datetime.now().isoformat()
    }

    async def _run_sync():
        global _etf_task_status
        try:
            from backend_core.data_collectors.akshare.etf_collector import ETFCollector
            collector = ETFCollector()
            result = collector.sync_etf_list()
            _etf_task_status['progress'] = 100
            _etf_task_status['message'] = f"同步完成，共 {result.get('total', 0)} 只ETF"
            _etf_task_status['result'] = result
        except Exception as e:
            logger.exception("ETF列表同步失败")
            _etf_task_status['message'] = f"同步失败: {str(e)}"
            _etf_task_status['result'] = {'error': str(e)}
        finally:
            _etf_task_status['is_running'] = False

    asyncio.create_task(_run_sync())

    return {
        'success': True,
        'message': 'ETF列表同步任务已启动',
        'data': {'task_type': 'sync_list'}
    }


@router.post("/collect")
async def start_etf_collect(body: ETFCollectBody):
    """触发ETF历史行情采集任务"""
    global _etf_task_status
    if _etf_task_status['is_running']:
        raise HTTPException(status_code=400, detail="已有ETF任务正在运行，请等待完成")

    _etf_task_status = {
        'is_running': True,
        'task_type': 'collect',
        'progress': 0,
        'message': '正在启动ETF行情采集...',
        'result': None,
        'start_time': datetime.now().isoformat()
    }

    start_date = body.start_date
    end_date = body.end_date
    etf_codes = body.etf_codes

    async def _run_collect():
        global _etf_task_status
        try:
            from backend_core.data_collectors.akshare.etf_collector import ETFCollector
            collector = ETFCollector()
            _etf_task_status['message'] = f"ETF行情采集中（{start_date} ~ {end_date}）..."
            result = collector.collect_historical_data(start_date, end_date, etf_codes)
            _etf_task_status['progress'] = 100
            _etf_task_status['message'] = (
                f"采集完成: 共 {result.get('total', 0)} 只ETF，"
                f"成功 {result.get('success', 0)}，"
                f"新增 {result.get('collected', 0)} 条行情"
            )
            _etf_task_status['result'] = result
        except Exception as e:
            logger.exception("ETF行情采集失败")
            _etf_task_status['message'] = f"采集失败: {str(e)}"
            _etf_task_status['result'] = {'error': str(e)}
        finally:
            _etf_task_status['is_running'] = False

    asyncio.create_task(_run_collect())

    return {
        'success': True,
        'message': 'ETF行情采集任务已启动',
        'data': {
            'task_type': 'collect',
            'start_date': start_date,
            'end_date': end_date,
            'etf_codes': etf_codes
        }
    }
