"""
用户 GMS 交易观察股：网站选股页「交易观察」加入 / 列表 / 移除。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import (
    GmsFormalTrade,
    GmsTradeObserveHistory,
    GmsTradeObserveStock,
    StockBasicInfo,
    StockBasicInfoHK,
    User,
)
from backend_api.utils.industry_board_query import (
    batch_industry_board_names_by_stock_codes,
    normalize_industry_text,
)

router = APIRouter(prefix="/api/stock/gms-trade-observe", tags=["gms-trade-observe"])


def _normalize_market(market: Optional[str], code: str) -> str:
    m = (market or "").strip().upper()
    if m in ("CN", "HK"):
        return m
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return "HK"
    return "CN"


def _normalize_code(code: str) -> str:
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return c.zfill(5)
    if c.isdigit() and len(c) <= 6:
        return c.zfill(6)
    return c


class GmsTradeObserveAddRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    market: Optional[str] = Field(None, description="CN 或 HK，可省略由代码推断")
    name: Optional[str] = None
    signal_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    snapshot: Optional[Dict[str, Any]] = None


class GmsTradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    industry: Optional[str] = None
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class GmsTradeObserveListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GmsTradeObserveItem]


class GmsTradeObserveHistoryItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    observe_created_at: Optional[str]
    observe_updated_at: Optional[str]
    removed_at: str
    source_observe_id: Optional[int]


class GmsTradeObserveHistoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GmsTradeObserveHistoryItem]


def _resolve_signal_date_str(
    stored: Optional[date],
    snapshot: Optional[Dict[str, Any]],
) -> Optional[str]:
    if stored and hasattr(stored, "strftime"):
        return stored.strftime("%Y-%m-%d")
    if stored:
        s = str(stored).strip()[:10]
        return s if s else None
    if isinstance(snapshot, dict):
        for key in ("signal_date", "indicator_date", "search_date", "d20_date", "date"):
            raw = snapshot.get(key)
            if raw:
                return str(raw).strip()[:10]
    return None


def _parse_signal_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="signal_date 格式应为 YYYY-MM-DD")


def _signal_date_from_body(body: GmsTradeObserveAddRequest) -> Optional[date]:
    if body.signal_date:
        return _parse_signal_date_optional(body.signal_date)
    snap = body.snapshot if isinstance(body.snapshot, dict) else None
    if snap:
        for key in ("signal_date", "indicator_date", "search_date", "d20_date", "date"):
            raw = snap.get(key)
            if raw:
                return _parse_signal_date_optional(str(raw))
    return None


def _observe_row_key(row: GmsTradeObserveStock) -> tuple[str, str]:
    market = (row.market or "CN").upper()
    return market, _normalize_code(row.code)


def _formal_trade_keys_for_user(db: Session, user_id: int) -> set[tuple[str, str]]:
    rows = (
        db.query(GmsFormalTrade.market, GmsFormalTrade.code)
        .filter(GmsFormalTrade.user_id == user_id)
        .all()
    )
    return {
        ((m or "CN").upper(), _normalize_code(c))
        for m, c in rows
        if c
    }


def _purge_observe_rows_already_formal_traded(db: Session, user_id: int) -> int:
    """已转入正式交易但观察记录仍残留时，归档并删除（兼容历史数据）。"""
    formal_keys = _formal_trade_keys_for_user(db, user_id)
    if not formal_keys:
        return 0
    rows = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.user_id == user_id)
        .all()
    )
    removed = 0
    now = datetime.now()
    for row in rows:
        if _observe_row_key(row) in formal_keys:
            _archive_trade_observe_row(db, row, removed_at=now)
            db.delete(row)
            removed += 1
    if removed:
        db.commit()
    return removed


def _industry_from_snapshot(snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(snapshot, dict):
        return None
    for key in ("industry", "所属行业"):
        raw = snapshot.get(key)
        valid = normalize_industry_text(raw)
        if valid:
            return valid
    return None


def _batch_resolve_industries(
    db: Session, rows: List[GmsTradeObserveStock]
) -> Dict[tuple[str, str], str]:
    """批量解析观察股所属行业：snapshot → 基础信息表 → 行业板块成分。"""
    out: Dict[tuple[str, str], str] = {}
    need_pairs: List[tuple[str, str]] = []
    for row in rows:
        key = _observe_row_key(row)
        snap_val = _industry_from_snapshot(
            row.signal_snapshot_json if isinstance(row.signal_snapshot_json, dict) else None
        )
        if snap_val:
            out[key] = snap_val
            continue
        need_pairs.append(key)
    if need_pairs:
        out.update(batch_resolve_industries_by_pairs(db, need_pairs))
    return out


def batch_resolve_industries_by_pairs(
    db: Session,
    pairs: List[tuple[str, str]],
) -> Dict[tuple[str, str], str]:
    """按 (market, code) 批量解析所属行业：A 股优先行业板块表，其次基础信息表。"""
    out: Dict[tuple[str, str], str] = {}
    need_cn: List[str] = []
    need_hk: List[str] = []
    seen: set[tuple[str, str]] = set()

    for market, code in pairs:
        m = (market or "CN").upper()
        c = _normalize_code(str(code or ""))
        if not c:
            continue
        key = (m, c)
        if key in seen:
            continue
        seen.add(key)
        if m == "HK":
            need_hk.append(c)
        else:
            need_cn.append(c)

    if need_cn:
        uniq = list(dict.fromkeys(need_cn))
        board_map = batch_industry_board_names_by_stock_codes(db, uniq)
        for code, industry in board_map.items():
            valid = normalize_industry_text(industry)
            if valid:
                out[("CN", code)] = valid

        still_missing = [c for c in uniq if ("CN", c) not in out]
        if still_missing:
            for code, industry in (
                db.query(StockBasicInfo.code, StockBasicInfo.industry)
                .filter(StockBasicInfo.code.in_(still_missing))
                .all()
            ):
                valid = normalize_industry_text(industry)
                if valid:
                    out.setdefault(("CN", str(code).strip()), valid)

    if need_hk:
        uniq = list(dict.fromkeys(need_hk))
        for code, industry in (
            db.query(StockBasicInfoHK.code, StockBasicInfoHK.industry)
            .filter(StockBasicInfoHK.code.in_(uniq))
            .all()
        ):
            valid = normalize_industry_text(industry)
            if valid:
                out.setdefault(("HK", str(code).strip()), valid)

    return out


def _row_to_item(
    r: GmsTradeObserveStock,
    *,
    industry: Optional[str] = None,
) -> GmsTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    resolved_industry = industry or _industry_from_snapshot(snap)
    return GmsTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        industry=resolved_industry,
        signal_date=sd,
        snapshot=snap,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _archive_trade_observe_row(
    db: Session,
    row: GmsTradeObserveStock,
    *,
    removed_at: Optional[datetime] = None,
) -> GmsTradeObserveHistory:
    """将当前观察记录写入历史表后由调用方删除原记录。"""
    now = removed_at or datetime.now()
    hist = GmsTradeObserveHistory(
        user_id=row.user_id,
        market=row.market,
        code=row.code,
        name=row.name,
        signal_snapshot_json=row.signal_snapshot_json,
        signal_date=row.signal_date,
        observe_created_at=row.created_at,
        observe_updated_at=row.updated_at,
        source_observe_id=row.id,
        removed_at=now,
    )
    db.add(hist)
    return hist


def _history_row_to_item(r: GmsTradeObserveHistory) -> GmsTradeObserveHistoryItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    return GmsTradeObserveHistoryItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        signal_date=sd,
        snapshot=snap,
        observe_created_at=r.observe_created_at.isoformat() if r.observe_created_at else None,
        observe_updated_at=r.observe_updated_at.isoformat() if r.observe_updated_at else None,
        removed_at=r.removed_at.isoformat() if r.removed_at else "",
        source_observe_id=r.source_observe_id,
    )


@router.get("/list", response_model=GmsTradeObserveListResponse)
def list_gms_trade_observe(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    _purge_observe_rows_already_formal_traded(db, user.id)
    q = db.query(GmsTradeObserveStock).filter(GmsTradeObserveStock.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(GmsTradeObserveStock.updated_at.desc(), GmsTradeObserveStock.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    industries = _batch_resolve_industries(db, rows)
    return GmsTradeObserveListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            _row_to_item(r, industry=industries.get(_observe_row_key(r)))
            for r in rows
        ],
    )


def list_user_trade_observe_code_keys(db: Session, user_id: int) -> List[str]:
    """当前用户交易观察 code 键（CN:000001，code 已归一化），供信号列表按钮态。"""
    _purge_observe_rows_already_formal_traded(db, user_id)
    rows = (
        db.query(GmsTradeObserveStock.market, GmsTradeObserveStock.code)
        .filter(GmsTradeObserveStock.user_id == user_id)
        .all()
    )
    return [
        f"{(m or 'CN').upper()}:{_normalize_code(c)}"
        for m, c in rows
        if c
    ]


@router.get("/codes", response_model=List[str])
def list_gms_trade_observe_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户已加入观察的 code 列表（用于信号列表按钮态）。"""
    return list_user_trade_observe_code_keys(db, user.id)


@router.post("/add", response_model=GmsTradeObserveItem)
def add_gms_trade_observe(
    body: GmsTradeObserveAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = _normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    market = _normalize_market(body.market, code)
    sig_date = _signal_date_from_body(body)
    if sig_date is None:
        raise HTTPException(
            status_code=400,
            detail="缺少 signal_date：请传入信号对应交易日（与 GMS 筛选基准日一致）",
        )

    existing = (
        db.query(GmsTradeObserveStock)
        .filter(
            GmsTradeObserveStock.user_id == user.id,
            GmsTradeObserveStock.market == market,
            GmsTradeObserveStock.code == code,
        )
        .first()
    )
    now = datetime.now()

    from backend_api.services.gms_strategy_watchlist import ensure_gms_strategy_watchlist_stock

    ensure_gms_strategy_watchlist_stock(db, market=market, code=code, name=body.name)

    if existing:
        existing.name = body.name or existing.name
        existing.signal_snapshot_json = body.snapshot if body.snapshot is not None else existing.signal_snapshot_json
        existing.signal_date = sig_date
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        industries = _batch_resolve_industries(db, [existing])
        return _row_to_item(existing, industry=industries.get(_observe_row_key(existing)))

    row = GmsTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=body.name,
        signal_snapshot_json=body.snapshot,
        signal_date=sig_date,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    industries = _batch_resolve_industries(db, [row])
    return _row_to_item(row, industry=industries.get(_observe_row_key(row)))


@router.get("/history", response_model=GmsTradeObserveHistoryListResponse)
def list_gms_trade_observe_history(
    page: int = 1,
    page_size: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """已移出交易观察的归档列表。"""
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(GmsTradeObserveHistory).filter(GmsTradeObserveHistory.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(GmsTradeObserveHistory.removed_at.desc(), GmsTradeObserveHistory.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return GmsTradeObserveHistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_history_row_to_item(r) for r in rows],
    )


@router.delete("/{item_id}")
def remove_gms_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == item_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    hist = _archive_trade_observe_row(db, row)
    db.delete(row)
    db.commit()
    db.refresh(hist)
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
