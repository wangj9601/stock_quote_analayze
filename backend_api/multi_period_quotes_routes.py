"""
A股多周期历史行情数据API
支持日线、周线、月线、季线、半年线、年线数据查询
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from backend_api.database import get_db
from fastapi.responses import JSONResponse, Response
import logging
import pandas as pd
import io

router = APIRouter(prefix="/api/quotes", tags=["quotes"])
logger = logging.getLogger(__name__)

# 周期类型到表名的映射
PERIOD_TABLE_MAP = {
    'daily': 'historical_quotes',
    'weekly': 'weekly_quotes',
    'monthly': 'monthly_quotes',
    'quarterly': 'quarterly_quotes',
    'semiannual': 'semiannual_quotes',
    'annual': 'annual_quotes'
}

@router.get("/historical/multi-period")
def get_historical_quotes_multi_period(
    period: str = Query('daily', description="周期类型: daily(日线), weekly(周线), monthly(月线), quarterly(季线), semiannual(半年线), annual(年线)"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词(股票代码或名称)"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取A股多周期历史行情数据
    支持日线、周线、月线、季线、半年线、年线
    """
    try:
        # 验证周期类型
        if period not in PERIOD_TABLE_MAP:
            return JSONResponse(
                {'success': False, 'message': f'不支持的周期类型: {period}'},
                status_code=400
            )
        
        table_name = PERIOD_TABLE_MAP[period]
        
        # 构建查询条件
        where_conditions = []
        params = {}
        
        if keyword:
            where_conditions.append("(code LIKE :keyword OR name LIKE :keyword)")
            params['keyword'] = f'%{keyword}%'
        
        if start_date:
            where_conditions.append("date >= :start_date")
            params['start_date'] = start_date
        
        if end_date:
            where_conditions.append("date <= :end_date")
            params['end_date'] = end_date
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 查询总数
        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM {table_name}
            WHERE {where_clause}
        """)
        
        total_result = db.execute(count_query, params)
        total = total_result.scalar()
        
        # 查询数据
        offset = (page - 1) * page_size
        params['limit'] = page_size
        params['offset'] = offset
        
        data_query = text(f"""
            SELECT code, name, date, open, high, low, close, volume, amount, change_percent, turnover_rate
            FROM {table_name}
            WHERE {where_clause}
            ORDER BY date DESC, code ASC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(data_query, params)
        rows = result.fetchall()
        
        # 格式化数据
        data = []
        for row in rows:
            data.append({
                'code': row[0],
                'name': row[1],
                'date': row[2],
                'open': round(float(row[3]), 2) if row[3] else None,
                'high': round(float(row[4]), 2) if row[4] else None,
                'low': round(float(row[5]), 2) if row[5] else None,
                'close': round(float(row[6]), 2) if row[6] else None,
                'volume': round(float(row[7]), 2) if row[7] else None,
                'amount': round(float(row[8]), 2) if row[8] else None,
                'change_percent': round(float(row[9]), 2) if row[9] else None,
                'turnover_rate': round(float(row[10]), 4) if row[10] is not None else None,
            })
        
        logger.info(f"查询{period}数据成功: 共{total}条, 返回{len(data)}条")
        
        return JSONResponse({
            'success': True,
            'data': data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'period': period
        })
        
    except Exception as e:
        logger.error(f"查询多周期历史数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {'success': False, 'message': f'查询失败: {str(e)}'},
            status_code=500
        )

@router.get("/historical/export")
def export_historical_quotes(
    target_date: Optional[str] = Query(None, description="指定日期 YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    format: str = Query('xlsx', description="导出格式: txt, xlsx"),
    market: str = Query('CN', description="市场: CN, HK"),
    db: Session = Depends(get_db)
):
    """
    导出历史行情数据
    """
    try:
        where_conditions = []
        params = {}
        
        if target_date:
            where_conditions.append("date = :target_date")
            params['target_date'] = target_date
        else:
            if start_date:
                where_conditions.append("date >= :start_date")
                params['start_date'] = start_date
            if end_date:
                where_conditions.append("date <= :end_date")
                params['end_date'] = end_date
                
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        table_name = "historical_quotes" if market == 'CN' else "historical_quotes_hk"
        data_query = text(f"""
            SELECT code, name, date, open, high, low, close, pre_close, volume, amount, change_percent, turnover_rate
            FROM {table_name}
            WHERE {where_clause}
            ORDER BY date DESC, code ASC
        """)
        
        result = db.execute(data_query, params)
        rows = result.fetchall()
        
        df = pd.DataFrame(rows, columns=['code', 'name', 'date', 'open', 'high', 'low', 'close', 'pre_close', 'volume', 'amount', 'change_percent', 'turnover_rate'])
        
        if format == 'xlsx':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Historical Quotes')
            output.seek(0)
            return Response(
                content=output.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=historical_quotes.{format}"
                }
            )
        else:
            # txt
            output = io.StringIO()
            df.to_csv(output, index=False, sep='\\t')
            return Response(
                content=output.getvalue().encode('utf-8'),
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=historical_quotes.{format}"
                }
            )
    except Exception as e:
        logger.error(f"导出历史数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {'success': False, 'message': f'导出失败: {str(e)}'},
            status_code=500
        )

