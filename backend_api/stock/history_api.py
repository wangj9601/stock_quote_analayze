from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend_api.database import get_db
from typing import List, Optional
import io
import csv
from sqlalchemy import text
from datetime import datetime

router = APIRouter(prefix="/api/stock/history", tags=["StockHistory"])

def format_date_yyyymmdd(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    # 支持 "YYYY-MM-DD"、"YYYY/MM/DD"、"YYYY.MM.DD" 等
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
        except Exception:
            continue
    # 如果本身就是8位数字直接返回
    if len(date_str) == 8 and date_str.isdigit():
        return date_str
    return date_str  # fallback

@router.get("")
def get_stock_history(
    code: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    start_date_fmt = format_date_yyyymmdd(start_date)
    end_date_fmt = format_date_yyyymmdd(end_date)
    print(f"[get_stock_history] 输入参数: code={code}, start_date={start_date_fmt}, end_date={end_date_fmt}, page={page}, size={size}")
    query = "SELECT date, open, close, high, low, volume FROM historical_quotes WHERE code = :code"
    params = {"code": code}
    if start_date_fmt:
        query += " AND date >= :start_date"
        params["start_date"] = start_date_fmt
    if end_date_fmt:
        query += " AND date <= :end_date"
        params["end_date"] = end_date_fmt
    query += " ORDER BY date DESC"
    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = db.execute(text(count_query), params).scalar()

    query += " LIMIT :limit OFFSET :offset"
    params["limit"] = size
    params["offset"] = (page - 1) * size
    result = db.execute(text(query), params)   
    items = [
        {
            "date": row[0],
            "open": row[1],
            "close": row[2],
            "high": row[3],
            "low": row[4],
            "volume": row[5]
        }
        for row in result.fetchall()
    ]
    print(f"[get_stock_history] 输出: total={total}, items_count={len(items)}")
    return {"items": items, "total": total}

@router.get("/export")
def export_stock_history(
    code: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    start_date_fmt = format_date_yyyymmdd(start_date)
    end_date_fmt = format_date_yyyymmdd(end_date)
    print(f"[export_stock_history] 输入参数: code={code}, start_date={start_date_fmt}, end_date={end_date_fmt}")
    query = "SELECT date, open, close, high, low, volume FROM historical_quotes WHERE code = :code"
    params = {"code": code}
    if start_date_fmt:
        query += " AND date >= :start_date"
        params["start_date"] = start_date_fmt
    if end_date_fmt:
        query += " AND date <= :end_date"
        params["end_date"] = end_date_fmt
    query += " ORDER BY date DESC"
    result = db.execute(text(query), params)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "open", "close", "high", "low", "volume"])
    row_count = 0
    for row in result.fetchall():
        writer.writerow(row)
        row_count += 1
    output.seek(0)
    filename = f"{code}_history.csv"
    print(f"[export_stock_history] 导出行数: {row_count}")
    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
