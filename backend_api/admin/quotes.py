"""
行情数据管理API模块
提供行情数据管理相关的接口
"""

from typing import List, Optional, Dict, Any, Literal
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, func, cast, String
from sqlalchemy import Date as SA_Date
from datetime import datetime, timedelta, date as date_type
import logging
from backend_core.logging_utils import resolve_log_file
import csv
import json
import os
import akshare as ak
import pandas as pd
from pathlib import Path
from io import BytesIO, StringIO
from pydantic import BaseModel, Field, model_validator
from fastapi.responses import StreamingResponse

from backend_api.models import (
    QuoteData, QuoteDataCreate, QuoteDataInDB,
    User, QuoteSyncTask, QuoteSyncTaskCreate,
    StockRealtimeQuote,
    IndexRealtimeQuotes,
    HistoricalQuotes,
    IndustryBoardRealtimeQuotes,
    IndustryBoardConstituent,
    StockRealtimeQuoteHK,
    HistoricalQuotesHK,
    HKIndexRealtimeQuotes,
    HKIndexHistoricalQuotes,
    FundRealtimeQuote,
    FundHistoricalQuotes,
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
        logging.FileHandler(resolve_log_file('quotes.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _try_append_operation_log(
    db: Session,
    *,
    log_type: str,
    log_message: str,
    affected_count: int,
    log_status: str,
    error_info: Optional[str],
) -> None:
    """
    尝试写入 operation_logs。部分库中该表为旧结构（缺少 log_type 等列），
    写入失败时仅记录 warning，不影响主流程（主事务应先已 commit）。
    """
    try:
        db.execute(
            text(
                """
                INSERT INTO operation_logs (log_type, log_message, affected_count, log_status, error_info, log_time)
                VALUES (:log_type, :log_message, :affected_count, :log_status, :error_info, NOW())
                """
            ),
            {
                "log_type": log_type,
                "log_message": log_message,
                "affected_count": affected_count,
                "log_status": log_status,
                "error_info": error_info,
            },
        )
        db.commit()
    except Exception as ex:
        db.rollback()
        logger.warning(
            "写入 operation_logs 失败（若需记录系统日志，请为表 operation_logs 补齐列 "
            "log_type, log_message, affected_count, log_status, error_info, log_time）: %s",
            ex,
        )


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


def _normalize_board_code(raw: Any) -> str:
    """行业板块 board_code（如 BK0479）：仅去空白与统一大写，不剥字母前缀。"""
    s = str(raw or "").strip().upper()
    s = s.lstrip("'").lstrip("’").strip()
    return s


def _normalize_hk_stock_code(raw: Any) -> str:
    """港股股票代码：去掉常见市场前缀，不强制补零到 6 位（避免 00700 被改成 007000）。"""
    s = str(raw or "").strip().upper()
    s = s.lstrip("'").lstrip("’").strip()
    if not s:
        return ""
    while s and s[0].isalpha():
        s = s[1:]
    if "." in s:
        s = s.split(".")[0]
    return s


def _normalize_hk_index_code(raw: Any) -> str:
    """港股指数代码（可能含字母，如 HSI）：仅规范化空白与大小写。"""
    s = str(raw or "").strip().upper()
    s = s.lstrip("'").lstrip("’").strip()
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
        _try_append_operation_log(
            db,
            log_type="turnover_rate_import",
            log_message=f"导入A股实时行情换手率 by {getattr(current_user, 'username', 'admin')}",
            affected_count=success,
            log_status="成功" if failed == 0 else "部分失败",
            error_info=None if failed == 0 else f"failed={failed}",
        )

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


@router.post("/turnover/import-historical")
async def import_turnover_rate_historical(
    file: UploadFile = File(...),
    trade_date: Optional[str] = Query(None, description="可选，统一交易日 YYYY-MM-DD"),
    dry_run: bool = Query(False),
    max_errors: int = Query(200, ge=1, le=5000),
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """导入A股历史行情换手率（CSV/XLSX/XLS）。"""
    name = (file.filename or "").lower()
    content = await file.read()

    df = None
    parse_errors: List[str] = []

    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                df = pd.read_csv(BytesIO(content), encoding=enc)
                break
            except Exception as e:
                parse_errors.append(f"csv({enc}): {e}")

    if df is None and (name.endswith(".xlsx") or name.endswith(".xls")):
        for engine in ("openpyxl", "xlrd"):
            try:
                df = pd.read_excel(BytesIO(content), engine=engine)
                break
            except Exception as e:
                parse_errors.append(f"excel({engine}): {e}")

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

    if df is None:
        for enc in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
            try:
                txt = content.decode(enc, errors="strict")
                if "\t" in txt:
                    trial = pd.read_csv(StringIO(txt), sep="\t")
                else:
                    trial = pd.read_csv(StringIO(txt), sep=None, engine="python")
                if trial is not None and not trial.empty and len(trial.columns) >= 2:
                    df = trial
                    break
            except Exception as e:
                parse_errors.append(f"probe-text({enc}): {e}")

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

    df.columns = [
        str(c).replace("\u3000", " ").replace("\n", " ").replace("\r", " ").strip()
        for c in df.columns
    ]
    code_col = _pick_col(list(df.columns), ["code", "代码", "股票代码", "证券代码"])
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
                    UPDATE historical_quotes
                    SET turnover_rate = :turnover_rate
                    WHERE code = :code AND date = :trade_date
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
        _try_append_operation_log(
            db,
            log_type="turnover_rate_import_historical",
            log_message=f"导入A股历史行情换手率 by {getattr(current_user, 'username', 'admin')}",
            affected_count=success,
            log_status="成功" if failed == 0 else "部分失败",
            error_info=None if failed == 0 else f"failed={failed}",
        )

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
    date_range: str = Query("today", pattern="^(today|week|month|custom)$"),
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


_TRADE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_optional_trade_date(label: str, s: Optional[str]) -> Optional[str]:
    if s is None or not str(s).strip():
        return None
    t = str(s).strip()
    if not _TRADE_DATE_RE.match(t):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label}须为 YYYY-MM-DD 格式",
        )
    return t


class DeleteAshareRealtimeQuotesBody(BaseModel):
    """删除 A 股表 stock_realtime_quote 中的记录（管理端）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(None, description="交易日下限（含），YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="交易日上限（含），YYYY-MM-DD")

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个股票」时必须填写股票代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


@router.post("/realtime/stocks/delete")
async def delete_ashare_realtime_quotes(
    body: DeleteAshareRealtimeQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    删除 A 股股票实时行情（表 stock_realtime_quote）。
    - scope=single：按股票代码删除，可配合 start_date/end_date 限定交易日。
    - scope=all：删除全部 A 股实时记录，可配合日期范围；不填日期则删除整张表全部记录。
    """
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(StockRealtimeQuote)
    if body.scope == "single":
        norm = _normalize_code(body.code)
        if not norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="股票代码无效")
        q = q.filter(StockRealtimeQuote.code == norm)
    if start:
        q = q.filter(StockRealtimeQuote.trade_date >= start)
    if end:
        q = q.filter(StockRealtimeQuote.trade_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()

    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="ashare_realtime_delete",
        log_message=(
            f"删除A股实时行情 scope={body.scope} code={body.code or '-'} "
            f"start={start or '-'} end={end or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )

    return {
        "success": True,
        "data": {"deleted": deleted},
        "message": f"已删除 {deleted} 条记录",
    }


class DeleteAshareIndexRealtimeQuotesBody(BaseModel):
    """删除 A 股指数实时表 index_realtime_quotes（管理端）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(
        None, description="按记录更新时间筛选：日期下限（含），YYYY-MM-DD，对应 update_time 日期部分"
    )
    end_date: Optional[str] = Field(None, description="日期上限（含），YYYY-MM-DD")

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个指数」时必须填写指数代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


@router.post("/realtime/indices/delete")
async def delete_ashare_index_realtime_quotes(
    body: DeleteAshareIndexRealtimeQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    删除 A 股指数实时行情（表 index_realtime_quotes）。
    - 时间段按每条记录的 update_time 的日期部分（前 10 位）筛选。
    - scope=single：按指数代码删除；可与日期组合。
    - scope=all：删除全部指数记录；可与日期组合；不填日期则清空整张表。
    """
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(IndexRealtimeQuotes)
    if body.scope == "single":
        norm = _normalize_code(body.code)
        if not norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="指数代码无效")
        q = q.filter(IndexRealtimeQuotes.code == norm)
    # update_time 可能为 TEXT 或 TIMESTAMP，先 cast 为字符串再取日期部分比较
    idx_ut_day = func.substr(cast(IndexRealtimeQuotes.update_time, String), 1, 10)
    if start:
        q = q.filter(idx_ut_day >= start)
    if end:
        q = q.filter(idx_ut_day <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()

    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="ashare_index_realtime_delete",
        log_message=(
            f"删除A股指数实时行情 scope={body.scope} code={body.code or '-'} "
            f"start={start or '-'} end={end or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )

    return {
        "success": True,
        "data": {"deleted": deleted},
        "message": f"已删除 {deleted} 条记录",
    }


class DeleteAshareIndustryRealtimeQuotesBody(BaseModel):
    """删除 A 股行业板块实时表 industry_board_realtime_quotes（管理端）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(
        None, description="按 update_time 日期部分（前 10 位）筛选，下限 YYYY-MM-DD"
    )
    end_date: Optional[str] = Field(None, description="上限 YYYY-MM-DD（含）")

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个板块」时必须填写板块代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


@router.post("/realtime/industries/delete")
async def delete_ashare_industry_realtime_quotes(
    body: DeleteAshareIndustryRealtimeQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    删除 A 股行业板块实时行情（表 industry_board_realtime_quotes）。
    - 按 update_time 字符串的日期部分（前 10 位）做区间筛选。
    - scope=single：按 board_code（body.code）删除；可与日期组合；不选日期则删该板块全部记录。
    - scope=all：全部板块；可与日期组合；不选日期则清空整张表。
    """
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(IndustryBoardRealtimeQuotes)
    if body.scope == "single":
        bcode = _normalize_board_code(body.code)
        if not bcode:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="板块代码无效")
        q = q.filter(IndustryBoardRealtimeQuotes.board_code == bcode)
    ind_ut_day = func.substr(cast(IndustryBoardRealtimeQuotes.update_time, String), 1, 10)
    if start:
        q = q.filter(ind_ut_day >= start)
    if end:
        q = q.filter(ind_ut_day <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()

    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="ashare_industry_realtime_delete",
        log_message=(
            f"删除A股行业板块实时行情 scope={body.scope} board_code={body.code or '-'} "
            f"start={start or '-'} end={end or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )

    return {
        "success": True,
        "data": {"deleted": deleted},
        "message": f"已删除 {deleted} 条记录",
    }


class SyncIndustryBoardConstituentsBody(BaseModel):
    """触发行业板块成分股全量同步（后台执行 AKShare 采集）。"""

    board_codes: Optional[List[str]] = Field(
        None, description="仅同步指定板块代码；空则同步全部"
    )


@router.post("/realtime/industries/constituents/sync")
async def sync_industry_board_constituents(
    body: SyncIndustryBoardConstituentsBody,
    current_user: Any = Depends(get_current_admin),
):
    """管理端：同步东财行业板块成分股到 industry_board_constituents。"""
    try:
        from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
            IndustryBoardConstituentsCollector,
        )

        collector = IndustryBoardConstituentsCollector()
        codes = body.board_codes if body.board_codes else None
        collector.run(board_codes=codes)
        uname = getattr(current_user, "username", None) or "admin"
        return {
            "success": True,
            "message": f"成分股同步任务已执行（操作人 {uname}）",
        }
    except Exception as e:
        logging.exception("成分股同步失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


class DeleteIndustryBoardConstituentsBody(BaseModel):
    scope: Literal["single", "all"]
    code: Optional[str] = None

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope == "single" and not (self.code or "").strip():
            raise ValueError("选择「单个板块」时必须填写板块代码")
        return self


@router.post("/realtime/industries/constituents/delete")
async def delete_industry_board_constituents(
    body: DeleteIndustryBoardConstituentsBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 industry_board_constituents 成分股记录。"""
    q = db.query(IndustryBoardConstituent)
    if body.scope == "single":
        bcode = _normalize_board_code(body.code)
        if not bcode:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="板块代码无效")
        q = q.filter(IndustryBoardConstituent.board_code == bcode)
    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="industry_board_constituents_delete",
        log_message=f"删除成分股 scope={body.scope} board={body.code or '-'} by {uname}",
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {
        "success": True,
        "data": {"deleted": deleted},
        "message": f"已删除 {deleted} 条成分股",
    }


class DeleteAshareHistoricalQuotesBody(BaseModel):
    """删除 A 股历史行情表 historical_quotes（管理端）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(None, description="K 线日期下限（含），YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="K 线日期上限（含），YYYY-MM-DD")

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个股票」时必须填写股票代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


def _parse_optional_iso_date(label: str, s: Optional[str]) -> Optional[date_type]:
    """将 YYYY-MM-DD 转为 date，供 HistoricalQuotes.date 列比较。"""
    raw = _parse_optional_trade_date(label, s)
    if raw is None:
        return None
    return date_type.fromisoformat(raw)


@router.post("/historical/delete")
async def delete_ashare_historical_quotes(
    body: DeleteAshareHistoricalQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    删除 A 股历史行情（表 historical_quotes，按 K 线日期 date）。
    - scope=single：按股票代码删除；可与 start_date/end_date 限定日期区间。
    - scope=all：删除全部 A 股历史记录；可与日期区间组合；不填日期则清空整张表。
    """
    start = _parse_optional_iso_date("开始日期", body.start_date)
    end = _parse_optional_iso_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(HistoricalQuotes)
    if body.scope == "single":
        norm = _normalize_code(body.code)
        if not norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="股票代码无效")
        q = q.filter(HistoricalQuotes.code == norm)
    # 部分库中 date 列为 TEXT，直接与 Python date 比较会在 PostgreSQL 上报 text >= date；统一 cast 为 DATE
    date_as_sql_date = cast(HistoricalQuotes.date, SA_Date)
    if start:
        q = q.filter(date_as_sql_date >= start)
    if end:
        q = q.filter(date_as_sql_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()

    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="ashare_historical_delete",
        log_message=(
            f"删除A股历史行情 scope={body.scope} code={body.code or '-'} "
            f"start={body.start_date or '-'} end={body.end_date or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )

    return {
        "success": True,
        "data": {"deleted": deleted},
        "message": f"已删除 {deleted} 条记录",
    }


class DeleteHkQuotesBody(BaseModel):
    """港股行情删除公共请求体（股票/指数、实时/历史）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(None, description="日期下限 YYYY-MM-DD（含）")
    end_date: Optional[str] = Field(None, description="日期上限 YYYY-MM-DD（含）")

    @model_validator(mode="after")
    def _validate_hk_delete(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个」时必须填写代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


@router.post("/hk/stocks/realtime/delete")
async def delete_hk_stock_realtime_quotes(
    body: DeleteHkQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除港股股票实时行情 stock_realtime_quote_hk（按 trade_date 字符串区间）。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(StockRealtimeQuoteHK)
    if body.scope == "single":
        c = _normalize_hk_stock_code(body.code)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="股票代码无效")
        q = q.filter(StockRealtimeQuoteHK.code == c)
    if start:
        q = q.filter(StockRealtimeQuoteHK.trade_date >= start)
    if end:
        q = q.filter(StockRealtimeQuoteHK.trade_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="hk_stock_realtime_delete",
        log_message=f"删除港股实时行情 scope={body.scope} code={body.code or '-'} start={start or '-'} end={end or '-'} by {uname}",
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


@router.post("/hk/stocks/historical/delete")
async def delete_hk_stock_historical_quotes(
    body: DeleteHkQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除港股股票历史行情 historical_quotes_hk（按 date 字符串）。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(HistoricalQuotesHK)
    if body.scope == "single":
        c = _normalize_hk_stock_code(body.code)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="股票代码无效")
        q = q.filter(HistoricalQuotesHK.code == c)
    if start:
        q = q.filter(HistoricalQuotesHK.date >= start)
    if end:
        q = q.filter(HistoricalQuotesHK.date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="hk_stock_historical_delete",
        log_message=f"删除港股历史行情 scope={body.scope} code={body.code or '-'} start={start or '-'} end={end or '-'} by {uname}",
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


@router.post("/hk/indices/realtime/delete")
async def delete_hk_index_realtime_quotes(
    body: DeleteHkQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除港股指数实时行情 hk_index_realtime_quotes（按 trade_date）。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(HKIndexRealtimeQuotes)
    if body.scope == "single":
        c = _normalize_hk_index_code(body.code)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="指数代码无效")
        q = q.filter(HKIndexRealtimeQuotes.code == c)
    if start:
        q = q.filter(HKIndexRealtimeQuotes.trade_date >= start)
    if end:
        q = q.filter(HKIndexRealtimeQuotes.trade_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="hk_index_realtime_delete",
        log_message=f"删除港股指数实时行情 scope={body.scope} code={body.code or '-'} start={start or '-'} end={end or '-'} by {uname}",
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


@router.post("/hk/indices/historical/delete")
async def delete_hk_index_historical_quotes(
    body: DeleteHkQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除港股指数历史行情 hk_index_historical_quotes（按 date 字符串）。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(HKIndexHistoricalQuotes)
    if body.scope == "single":
        c = _normalize_hk_index_code(body.code)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="指数代码无效")
        q = q.filter(HKIndexHistoricalQuotes.code == c)
    if start:
        q = q.filter(HKIndexHistoricalQuotes.date >= start)
    if end:
        q = q.filter(HKIndexHistoricalQuotes.date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="hk_index_historical_delete",
        log_message=f"删除港股指数历史行情 scope={body.scope} code={body.code or '-'} start={start or '-'} end={end or '-'} by {uname}",
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


class DeleteEtfQuotesBody(BaseModel):
    """ETF 行情删除（实时 / 历史）。"""

    scope: Literal["single", "all"]
    code: Optional[str] = None
    start_date: Optional[str] = Field(None, description="日期下限 YYYY-MM-DD（含）")
    end_date: Optional[str] = Field(None, description="日期上限 YYYY-MM-DD（含）")

    @model_validator(mode="after")
    def _validate_etf_delete(self):
        if self.scope == "single":
            if not (self.code or "").strip():
                raise ValueError("选择「单个」时必须填写 ETF 代码")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


@router.post("/etf/realtime/delete")
async def delete_etf_realtime_quotes(
    body: DeleteEtfQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 ETF 实时行情 fund_realtime_quote（按 trade_date 字符串区间）。"""
    start = _parse_optional_trade_date("开始日期", body.start_date)
    end = _parse_optional_trade_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(FundRealtimeQuote)
    if body.scope == "single":
        c = _normalize_code(body.code)
        if not c:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ETF 代码无效")
        q = q.filter(FundRealtimeQuote.code == c)
    if start:
        q = q.filter(FundRealtimeQuote.trade_date >= start)
    if end:
        q = q.filter(FundRealtimeQuote.trade_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="etf_realtime_delete",
        log_message=(
            f"删除ETF实时行情 scope={body.scope} code={body.code or '-'} "
            f"start={start or '-'} end={end or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


@router.post("/etf/historical/delete")
async def delete_etf_historical_quotes(
    body: DeleteEtfQuotesBody,
    current_user: Any = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除 ETF 历史行情 fund_historical_quotes（按 K 线 date）。"""
    start = _parse_optional_iso_date("开始日期", body.start_date)
    end = _parse_optional_iso_date("结束日期", body.end_date)
    if start and end and start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期不能晚于结束日期")

    q = db.query(FundHistoricalQuotes)
    if body.scope == "single":
        norm = _normalize_code(body.code)
        if not norm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ETF 代码无效")
        q = q.filter(FundHistoricalQuotes.code == norm)
    date_as_sql_date = cast(FundHistoricalQuotes.date, SA_Date)
    if start:
        q = q.filter(date_as_sql_date >= start)
    if end:
        q = q.filter(date_as_sql_date <= end)

    deleted = q.delete(synchronize_session=False)
    db.commit()
    uname = getattr(current_user, "username", None) or "admin"
    _try_append_operation_log(
        db,
        log_type="etf_historical_delete",
        log_message=(
            f"删除ETF历史行情 scope={body.scope} code={body.code or '-'} "
            f"start={body.start_date or '-'} end={body.end_date or '-'} by {uname}"
        ),
        affected_count=deleted,
        log_status="成功",
        error_info=None,
    )
    return {"success": True, "data": {"deleted": deleted}, "message": f"已删除 {deleted} 条记录"}


@router.get("/{quote_type}/export")
async def export_quote_data(
    quote_type: str,
    keyword: Optional[str] = None,
    date_range: str = Query("today", pattern="^(today|week|month|custom)$"),
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