"""
行情数据管理API模块
提供行情数据管理相关的接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from datetime import datetime, timedelta
import logging
import csv
import json
import os
import akshare as ak
import pandas as pd
from pathlib import Path
from io import BytesIO, StringIO
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from backend_api.models import (
    QuoteData, QuoteDataCreate, QuoteDataInDB,
    User, QuoteSyncTask, QuoteSyncTaskCreate
)
from backend_api.database import get_db
from backend_api.auth import get_current_user, get_current_admin

# 定义分页响应模型
class PaginatedResponse(BaseModel):
    success: bool
    data: List[QuoteDataInDB]
    total: int
    page: int
    page_size: int

router = APIRouter(prefix="/api/admin/quotes", tags=["admin_quotes"])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quotes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _normalize_code(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    # 兼容 Excel 文本格式常见前缀，如 'SZ300668 或 ’SZ300668
    s = s.lstrip("'").lstrip("’").strip()
    if not s:
        return ""
    # 兼容 SH600000 / SZ000001 / BJ430047 等前缀；以及其它字母前缀场景
    while s and s[0].isalpha():
        s = s[1:]
    if "." in s:
        s = s.split(".")[0]
    if s.isdigit() and len(s) < 6:
        s = s.zfill(6)
    return s


def _pick_col(columns: List[str], aliases: List[str]) -> Optional[str]:
    lowered = {str(c).strip().lower(): c for c in columns}
    for a in aliases:
        key = a.strip().lower()
        if key in lowered:
            return lowered[key]
    return None


@router.post("/turnover/import")
async def import_turnover_rate(
    file: UploadFile = File(...),
    trade_date: Optional[str] = Query(None, description="可选，统一交易日 YYYY-MM-DD"),
    dry_run: bool = Query(False),
    max_errors: int = Query(200, ge=1, le=5000),
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """导入A股实时行情换手率（CSV/XLSX）。"""
    name = (file.filename or "").lower()
    content = await file.read()

    # 文件名后缀在浏览器上传时可能不可靠（如 Table-0...），按内容兜底探测
    df = None
    parse_errors: List[str] = []

    # 1) 明确是 csv 时优先按 csv 解析
    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                df = pd.read_csv(BytesIO(content), encoding=enc)
                break
            except Exception as e:
                parse_errors.append(f"csv({enc}): {e}")

    # 2) 明确是 excel 时优先按 excel 解析（xlsx/xls）
    if df is None and (name.endswith(".xlsx") or name.endswith(".xls")):
        for engine in ("openpyxl", "xlrd"):
            try:
                df = pd.read_excel(BytesIO(content), engine=engine)
                break
            except Exception as e:
                parse_errors.append(f"excel({engine}): {e}")

    # 3) 后缀不可靠时：先尝试 csv，再尝试 excel
    if df is None and not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                trial = pd.read_csv(BytesIO(content), encoding=enc)
                if trial is not None and not trial.empty and len(trial.columns) >= 2:
                    df = trial
                    break
            except Exception as e:
                parse_errors.append(f"probe-csv({enc}): {e}")
        if df is None:
            for engine in ("openpyxl", "xlrd"):
                try:
                    df = pd.read_excel(BytesIO(content), engine=engine)
                    break
                except Exception as e:
                    parse_errors.append(f"probe-excel({engine}): {e}")

    # 4) 兜底：有些“xls”实际是GBK/GB18030编码的文本（常见为制表符分隔）
    if df is None:
        for enc in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
            try:
                txt = content.decode(enc, errors="strict")
                # 优先按制表符读取；若不是制表符，交给 python 引擎自动探测分隔符
                if "\t" in txt:
                    trial = pd.read_csv(StringIO(txt), sep="\t")
                else:
                    trial = pd.read_csv(StringIO(txt), sep=None, engine="python")
                if trial is not None and not trial.empty and len(trial.columns) >= 2:
                    df = trial
                    break
            except Exception as e:
                parse_errors.append(f"probe-text({enc}): {e}")

    # 5) 兜底：有些“xls”实际是HTML表格，尝试 read_html
    if df is None:
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                html_tables = pd.read_html(BytesIO(content), encoding=enc)
                if html_tables:
                    df = html_tables[0]
                    break
            except Exception as e:
                parse_errors.append(f"probe-html({enc}): {e}")

    if df is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "文件解析失败，请上传标准 CSV/XLSX/XLS 文件（包含 code/代码 与 "
                "turnover_rate/换手率/还手 列）。解析尝试信息："
                + " | ".join(parse_errors[:3])
            ),
        )

    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="文件为空")

    # 统一清洗列名，兼容前后空格、全角空格、换行等
    df.columns = [
        str(c).replace("\u3000", " ").replace("\n", " ").replace("\r", " ").strip()
        for c in df.columns
    ]

    code_col = _pick_col(list(df.columns), ["code", "代码", "股票代码", "证券代码"])
    # 兼容用户当前文件列名“还手/还手率”
    rate_col = _pick_col(list(df.columns), ["turnover_rate", "换手率", "换手", "还手", "还手率"])
    date_col = _pick_col(list(df.columns), ["trade_date", "日期", "交易日期"])
    if not code_col or not rate_col:
        raise HTTPException(
            status_code=400,
            detail=(
                "缺少必要列：code/代码 与 turnover_rate/换手率/还手。"
                "（说明：换手 也支持）"
                f"当前识别到列: {list(df.columns)}"
            ),
        )

    # 仅保留导入所需列，其它业务列全部忽略
    needed_cols = [code_col, rate_col]
    if date_col:
        needed_cols.append(date_col)
    df = df[needed_cols].copy()

    success = 0
    skipped = 0
    failed = 0
    failures: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        code = _normalize_code(row.get(code_col))
        raw_rate = row.get(rate_col)
        row_date = trade_date or (str(row.get(date_col)).strip() if date_col else "")

        if not code:
            failed += 1
            failures.append({"row_no": row_no, "code": "", "message": "代码为空"})
            if failed >= max_errors:
                break
            continue
        if not row_date:
            failed += 1
            failures.append({"row_no": row_no, "code": code, "message": "缺少 trade_date（可传 query 或文件列）"})
            if failed >= max_errors:
                break
            continue
        try:
            rate = float(str(raw_rate).replace("%", "").strip())
            if rate < 0:
                raise ValueError("换手率不能为负")
        except Exception:
            failed += 1
            failures.append({"row_no": row_no, "code": code, "message": f"换手率非法: {raw_rate}"})
            if failed >= max_errors:
                break
            continue

        try:
            if dry_run:
                success += 1
                continue
            res = db.execute(
                text(
                    """
                    UPDATE stock_realtime_quote
                    SET turnover_rate = :turnover_rate, update_time = NOW()
                    WHERE code = :code AND trade_date = :trade_date
                    """
                ),
                {"turnover_rate": rate, "code": code, "trade_date": row_date},
            )
            if (res.rowcount or 0) > 0:
                success += 1
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            failures.append({"row_no": row_no, "code": code, "message": str(e)})
            if failed >= max_errors:
                break

    if dry_run:
        db.rollback()
    else:
        db.commit()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO operation_logs (log_type, log_message, affected_count, log_status, error_info, log_time)
                    VALUES (:log_type, :log_message, :affected_count, :log_status, :error_info, NOW())
                    """
                ),
                {
                    "log_type": "turnover_rate_import",
                    "log_message": f"导入A股实时行情换手率 by {getattr(current_user, 'username', 'admin')}",
                    "affected_count": success,
                    "log_status": "成功" if failed == 0 else "部分失败",
                    "error_info": None if failed == 0 else f"failed={failed}",
                },
            )
            db.commit()
        except Exception:
            db.rollback()

    return {
        "success": failed == 0,
        "data": {
            "filename": file.filename,
            "total_rows": int(len(df)),
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "dry_run": dry_run,
            "failed_sample": failures[:100],
        },
    }


@router.get("/turnover/import/template")
async def download_turnover_import_template(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: Any = Depends(get_current_admin),
):
    cols = ["code", "trade_date", "turnover_rate"]
    sample = [
        ["600519", "2026-03-26", 1.83],
        ["000001", "2026-03-26", 0.92],
    ]

    if format == "csv":
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow(cols)
        writer.writerows(sample)
        return StreamingResponse(
            iter([sio.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=turnover_rate_import_template.csv"},
        )

    df = pd.DataFrame(sample, columns=cols)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="template")
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=turnover_rate_import_template.xlsx"},
    )

# 行情数据相关路由
@router.get("/realtime", response_model=PaginatedResponse)
async def get_realtime_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取实时行情数据"""
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    total = query.count()
    quotes = query.order_by(desc(QuoteData.updated_at)) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()
    
    return {
        "success": True,
        "data": quotes,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/historical", response_model=PaginatedResponse)
async def get_historical_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    date_range: str = Query("today", regex="^(today|week|month|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取历史行情数据"""
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    # 处理日期范围
    now = datetime.now()
    if date_range == "today":
        query = query.filter(QuoteData.trade_date == now.date())
    elif date_range == "week":
        week_start = now - timedelta(days=now.weekday())
        query = query.filter(QuoteData.trade_date >= week_start.date())
    elif date_range == "month":
        month_start = now.replace(day=1)
        query = query.filter(QuoteData.trade_date >= month_start.date())
    elif date_range == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义日期范围需要提供开始和结束日期"
            )
        query = query.filter(
            QuoteData.trade_date >= start_date.date(),
            QuoteData.trade_date <= end_date.date()
        )
    
    total = query.count()
    quotes = query.order_by(desc(QuoteData.trade_date)) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()
    
    return {
        "success": True,
        "data": quotes,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/{quote_type}/export")
async def export_quote_data(
    quote_type: str,
    keyword: Optional[str] = None,
    date_range: str = Query("today", regex="^(today|week|month|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """导出行情数据"""
    if quote_type not in ["realtime", "historical"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的数据类型"
        )
    
    query = db.query(QuoteData)
    
    if keyword:
        query = query.filter(
            (QuoteData.stock_code.contains(keyword)) |
            (QuoteData.stock_name.contains(keyword))
        )
    
    # 处理日期范围
    now = datetime.now()
    if date_range == "today":
        query = query.filter(QuoteData.trade_date == now.date())
    elif date_range == "week":
        week_start = now - timedelta(days=now.weekday())
        query = query.filter(QuoteData.trade_date >= week_start.date())
    elif date_range == "month":
        month_start = now.replace(day=1)
        query = query.filter(QuoteData.trade_date >= month_start.date())
    elif date_range == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自定义日期范围需要提供开始和结束日期"
            )
        query = query.filter(
            QuoteData.trade_date >= start_date.date(),
            QuoteData.trade_date <= end_date.date()
        )
    
    quotes = query.order_by(desc(QuoteData.trade_date)).all()
    
    # 转换为DataFrame
    df = pd.DataFrame([{
        "股票代码": q.stock_code,
        "股票名称": q.stock_name,
        "最新价": q.last_price,
        "涨跌幅": q.change_percent,
        "成交量": q.volume,
        "成交额": q.amount,
        "最高价": q.high,
        "最低价": q.low,
        "开盘价": q.open,
        "昨收价": q.pre_close,
        "更新时间": q.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    } for q in quotes])
    
    # 创建Excel文件
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quotes_{quote_type}_{timestamp}.xlsx"
    filepath = output_dir / filename
    
    # 保存为Excel
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="行情数据")
        
        # 调整列宽
        worksheet = writer.sheets["行情数据"]
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
    
    return {
        "success": True,
        "message": "数据导出成功",
        "data": {
            "filename": filename,
            "download_url": f"/exports/{filename}"
        }
    } 