"""
用户 GMS 交易观察股：网站选股页「交易观察」加入 / 列表 / 移除。
"""

from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
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
from backend_api.utils.latest_close_lookup import batch_lookup_latest_closes
from backend_api.services.gms_audit_service import write_gms_audit
from backend_core.strategies.gms.trade_price_plan import (
    attach_price_plan_to_snapshot,
    compute_price_plan,
)
from backend_api.utils.industry_board_query import (
    batch_industry_board_names_by_stock_codes,
    clean_industry_display_text,
    normalize_industry_text,
)

router = APIRouter(prefix="/api/stock/gms-trade-observe", tags=["gms-trade-observe"])

_DEFAULT_WATCH_THRESHOLD = 60.0
_key_focus_schema_lock = threading.Lock()
_key_focus_schema_ensured = False
_latest_price_schema_lock = threading.Lock()
_latest_price_schema_ensured = False


def ensure_gms_trade_observe_key_focus_column(db: Session) -> None:
    """确保 gms_trade_observe_stocks 存在 key_focus_flag 列（PostgreSQL 生产库）。"""
    global _key_focus_schema_ensured
    if _key_focus_schema_ensured:
        return
    with _key_focus_schema_lock:
        if _key_focus_schema_ensured:
            return
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            db.execute(
                text(
                    """
                    ALTER TABLE gms_trade_observe_stocks
                    ADD COLUMN IF NOT EXISTS key_focus_flag BOOLEAN NOT NULL DEFAULT FALSE
                    """
                )
            )
        _key_focus_schema_ensured = True


def ensure_gms_trade_observe_latest_price_columns(db: Session) -> None:
    """确保 gms_trade_observe_stocks 存在 latest_close_price / latest_close_date 列。"""
    global _latest_price_schema_ensured
    if _latest_price_schema_ensured:
        return
    with _latest_price_schema_lock:
        if _latest_price_schema_ensured:
            return
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            db.execute(
                text(
                    """
                    ALTER TABLE gms_trade_observe_stocks
                    ADD COLUMN IF NOT EXISTS latest_close_price DOUBLE PRECISION
                    """
                )
            )
            db.execute(
                text(
                    """
                    ALTER TABLE gms_trade_observe_stocks
                    ADD COLUMN IF NOT EXISTS latest_close_date DATE
                    """
                )
            )
        _latest_price_schema_ensured = True


def _score_total_from_snapshot(snapshot: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("score_total") is not None:
        try:
            return float(snapshot["score_total"])
        except (TypeError, ValueError):
            return None
    if snapshot.get("signal_strength") is not None:
        try:
            return float(snapshot["signal_strength"]) * 100.0
        except (TypeError, ValueError):
            return None
    sd = snapshot.get("score_detail")
    if isinstance(sd, dict) and sd.get("score_total") is not None:
        try:
            return float(sd["score_total"])
        except (TypeError, ValueError):
            return None
    return None


def _watch_threshold_from_snapshot(snapshot: Optional[Dict[str, Any]]) -> float:
    if isinstance(snapshot, dict) and snapshot.get("watch_threshold") is not None:
        try:
            return float(snapshot["watch_threshold"])
        except (TypeError, ValueError):
            pass
    return _DEFAULT_WATCH_THRESHOLD


def snapshot_meets_watch_threshold(snapshot: Optional[Dict[str, Any]]) -> bool:
    """加入时总分是否达到策略「重点关注分数」阈值。"""
    total = _score_total_from_snapshot(snapshot)
    if total is None:
        return False
    return total >= _watch_threshold_from_snapshot(snapshot)


def resolve_key_focus_display(
    *,
    key_focus_flag: bool,
    snapshot: Optional[Dict[str, Any]],
) -> tuple[bool, bool, Optional[float], float]:
    """返回 (是否展示重点, 是否手动标记, 快照总分, 关注阈值)。"""
    watch_th = _watch_threshold_from_snapshot(snapshot)
    score_total = _score_total_from_snapshot(snapshot)
    auto_hit = snapshot_meets_watch_threshold(snapshot)
    show = bool(key_focus_flag) or auto_hit
    return show, bool(key_focus_flag), score_total, watch_th


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
    key_focus_flag: Optional[bool] = Field(
        None,
        description="是否标记为重点关注；省略时按快照总分与 watch_threshold 自动判定",
    )


class GmsTradeObserveKeyFocusBody(BaseModel):
    key_focus_flag: bool = Field(..., description="是否标记为重点关注")


class GmsTradeObserveItem(BaseModel):
    id: int
    market: str
    code: str
    name: Optional[str]
    industry: Optional[str] = None
    signal_date: Optional[str]
    snapshot: Optional[Dict[str, Any]]
    price_plan: Optional[Dict[str, Any]] = None
    key_focus_flag: bool = False
    key_focus_display: bool = False
    key_focus_auto: bool = False
    score_total: Optional[float] = None
    watch_threshold: Optional[float] = None
    latest_close_price: Optional[float] = None
    latest_close_date: Optional[str] = None
    created_at: str
    updated_at: str


class GmsTradeObserveLatestPriceResponse(BaseModel):
    id: int
    market: str
    code: str
    latest_close_price: Optional[float] = None
    latest_close_date: Optional[str] = None


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


def _parse_quote_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_stored_quote_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d")
    s = str(raw).strip()
    return s[:10] if s else None


def _apply_latest_close_to_row(
    row: GmsTradeObserveStock,
    *,
    close_price: Optional[float],
    close_date: Optional[str],
) -> None:
    row.latest_close_price = float(close_price) if close_price is not None else None
    row.latest_close_date = _parse_quote_date_optional(close_date)


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
        valid = clean_industry_display_text(raw)
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
            valid = clean_industry_display_text(industry)
            if valid:
                out[("CN", code)] = valid

        still_missing = [c for c in uniq if ("CN", c) not in out]
        if still_missing:
            for code, industry in (
                db.query(StockBasicInfo.code, StockBasicInfo.industry)
                .filter(StockBasicInfo.code.in_(still_missing))
                .all()
            ):
                valid = clean_industry_display_text(industry)
                if valid:
                    out.setdefault(("CN", str(code).strip()), valid)

    if need_hk:
        uniq = list(dict.fromkeys(need_hk))
        for code, industry in (
            db.query(StockBasicInfoHK.code, StockBasicInfoHK.industry)
            .filter(StockBasicInfoHK.code.in_(uniq))
            .all()
        ):
            valid = clean_industry_display_text(industry)
            if valid:
                out.setdefault(("HK", str(code).strip()), valid)

    return out


def _price_plan_for_row(
    db: Session,
    r: GmsTradeObserveStock,
    snap: Optional[Dict[str, Any]],
    *,
    recompute: bool = True,
) -> Optional[Dict[str, Any]]:
    if isinstance(snap, dict) and isinstance(snap.get("price_plan"), dict):
        return snap["price_plan"]
    if not recompute:
        return None
    sig_date = r.signal_date
    if sig_date is None and isinstance(snap, dict):
        sd = _resolve_signal_date_str(None, snap)
        if sd:
            try:
                sig_date = datetime.strptime(sd, "%Y-%m-%d").date()
            except ValueError:
                sig_date = None
    if sig_date is None:
        return None
    return compute_price_plan(
        db,
        market=r.market or "CN",
        code=r.code,
        signal_date=sig_date,
        snapshot=snap,
    )


def _row_to_item(
    db: Session,
    r: GmsTradeObserveStock,
    *,
    industry: Optional[str] = None,
    recompute_price_plan: bool = True,
) -> GmsTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    resolved_industry = industry or _industry_from_snapshot(snap)
    key_focus_flag = bool(getattr(r, "key_focus_flag", False))
    show_focus, manual_focus, score_total, watch_th = resolve_key_focus_display(
        key_focus_flag=key_focus_flag,
        snapshot=snap,
    )
    auto_focus = show_focus and not manual_focus
    return GmsTradeObserveItem(
        id=r.id,
        market=r.market or "CN",
        code=r.code,
        name=r.name,
        industry=resolved_industry,
        signal_date=sd,
        snapshot=snap,
        price_plan=_price_plan_for_row(db, r, snap, recompute=recompute_price_plan),
        key_focus_flag=key_focus_flag,
        key_focus_display=show_focus,
        key_focus_auto=auto_focus,
        score_total=score_total,
        watch_threshold=watch_th,
        latest_close_price=getattr(r, "latest_close_price", None),
        latest_close_date=_format_stored_quote_date(getattr(r, "latest_close_date", None)),
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
    ensure_gms_trade_observe_key_focus_column(db)
    ensure_gms_trade_observe_latest_price_columns(db)
    _purge_observe_rows_already_formal_traded(db, user.id)
    q = db.query(GmsTradeObserveStock).filter(GmsTradeObserveStock.user_id == user.id)
    total = q.count()
    rows = (
        q.order_by(
            GmsTradeObserveStock.key_focus_flag.desc(),
            GmsTradeObserveStock.updated_at.desc(),
            GmsTradeObserveStock.code,
        )
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
            _row_to_item(
                db,
                r,
                industry=industries.get(_observe_row_key(r)),
                recompute_price_plan=False,
            )
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

    snapshot_with_plan = attach_price_plan_to_snapshot(
        db,
        body.snapshot,
        market=market,
        code=code,
        signal_date=sig_date,
    )
    focus_flag = False if body.key_focus_flag is None else bool(body.key_focus_flag)

    if existing:
        existing.name = body.name or existing.name
        existing.signal_snapshot_json = snapshot_with_plan
        existing.signal_date = sig_date
        existing.key_focus_flag = focus_flag
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        industries = _batch_resolve_industries(db, [existing])
        return _row_to_item(
            db,
            existing,
            industry=industries.get(_observe_row_key(existing)),
        )

    row = GmsTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=body.name,
        signal_snapshot_json=snapshot_with_plan,
        signal_date=sig_date,
        key_focus_flag=focus_flag,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_gms_audit(
        db,
        "gms_trade_observe_add",
        {"user_id": user.id, "code": code, "market": market},
    )
    industries = _batch_resolve_industries(db, [row])
    return _row_to_item(
        db,
        row,
        industry=industries.get(_observe_row_key(row)),
    )


@router.get("/{item_id}/latest-price", response_model=GmsTradeObserveLatestPriceResponse)
def get_gms_trade_observe_latest_price(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按需查询单条观察股最新价格（实时行情优先，历史行情兜底），并写入观察记录。"""
    ensure_gms_trade_observe_latest_price_columns(db)
    row = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == item_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    key = _observe_row_key(row)
    latest = batch_lookup_latest_closes(db, [key]).get(key, (None, None))
    close_price, close_date = latest
    _apply_latest_close_to_row(row, close_price=close_price, close_date=close_date)
    db.commit()
    db.refresh(row)
    return GmsTradeObserveLatestPriceResponse(
        id=row.id,
        market=row.market or "CN",
        code=row.code,
        latest_close_price=row.latest_close_price,
        latest_close_date=_format_stored_quote_date(row.latest_close_date),
    )


@router.get("/{item_id}/price-plan")
def get_gms_trade_observe_price_plan(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """刷新单条观察股交易价格计划。"""
    row = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == item_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if row.signal_date is None:
        raise HTTPException(status_code=400, detail="缺少信号日期，无法计算价格计划")
    snap = row.signal_snapshot_json if isinstance(row.signal_snapshot_json, dict) else {}
    plan = compute_price_plan(
        db,
        market=row.market or "CN",
        code=row.code,
        signal_date=row.signal_date,
        snapshot=snap,
    )
    snap = dict(snap)
    snap["price_plan"] = plan
    row.signal_snapshot_json = snap
    row.updated_at = datetime.now()
    db.commit()
    return plan


@router.post("/{item_id}/key-focus", response_model=GmsTradeObserveItem)
def set_gms_trade_observe_key_focus(
    item_id: int,
    body: GmsTradeObserveKeyFocusBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """切换交易观察股「重点关注」标记。"""
    ensure_gms_trade_observe_key_focus_column(db)
    row = (
        db.query(GmsTradeObserveStock)
        .filter(GmsTradeObserveStock.id == item_id, GmsTradeObserveStock.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    row.key_focus_flag = bool(body.key_focus_flag)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    industries = _batch_resolve_industries(db, [row])
    return _row_to_item(
        db,
        row,
        industry=industries.get(_observe_row_key(row)),
        recompute_price_plan=False,
    )


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
    write_gms_audit(
        db,
        "gms_trade_observe_remove",
        {"user_id": user.id, "code": row.code, "market": row.market, "history_id": hist.id},
    )
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
