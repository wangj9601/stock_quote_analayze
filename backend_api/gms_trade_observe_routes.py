"""
用户 GMS 交易观察股：薄封装，读写走统一 trade_observe_service（source=gms）。
响应形状保持旧前端兼容（key_focus_flag / latest_close_* 来自 extra_json）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.permissions import require_permission
from backend_api.models import (
    StockBasicInfo,
    StockBasicInfoHK,
    TradeObserveHistory,
    TradeObserveStock,
    User,
)
from backend_api import trade_observe_service as svc
from backend_api.utils.latest_close_lookup import batch_lookup_latest_closes
from backend_api.services.gms_audit_service import write_gms_audit
from backend_core.strategies.gms.trade_price_plan import (
    attach_price_plan_to_snapshot,
    compute_price_plan,
)
from backend_api.utils.industry_board_query import (
    batch_industry_board_names_by_stock_codes,
    clean_industry_display_text,
)
from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE

router = APIRouter(prefix="/api/stock/gms-trade-observe", tags=["gms-trade-observe"])

SOURCE = svc.SOURCE_GMS
_DEFAULT_WATCH_THRESHOLD = 60.0


def ensure_gms_trade_observe_key_focus_column(db: Session) -> None:
    """兼容旧调用：统一表后 key_focus 存 extra_json，无需改列。"""
    _ = db


def ensure_gms_trade_observe_latest_price_columns(db: Session) -> None:
    """兼容旧调用：统一表后最新价存 extra_json，无需改列。"""
    _ = db


def ensure_gms_trade_observe_schema(db: Session) -> None:
    """兼容旧调用：统一表无需补齐旧列。"""
    _ = db


def _extra_dict(row: TradeObserveStock) -> Dict[str, Any]:
    return dict(row.extra_json) if isinstance(row.extra_json, dict) else {}


def _extra_bool(row: TradeObserveStock, key: str, default: bool = False) -> bool:
    extra = _extra_dict(row)
    if key not in extra:
        return default
    return bool(extra.get(key))


def _extra_float(row: TradeObserveStock, key: str) -> Optional[float]:
    raw = _extra_dict(row).get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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
    return svc.normalize_market(market, code)


def _normalize_code(code: str) -> str:
    return svc.normalize_code(code)


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
    row: TradeObserveStock,
    *,
    close_price: Optional[float],
    close_date: Optional[str],
) -> None:
    patch: Dict[str, Any] = {
        "latest_close_price": float(close_price) if close_price is not None else None,
        "latest_close_date": (
            _parse_quote_date_optional(close_date).isoformat()
            if _parse_quote_date_optional(close_date)
            else None
        ),
    }
    extra = _extra_dict(row)
    extra.update(patch)
    row.extra_json = extra


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


def _observe_row_key(row: TradeObserveStock) -> tuple[str, str]:
    market = (row.market or "CN").upper()
    return market, _normalize_code(row.code)


def _purge_observe_rows_already_formal_traded(db: Session, user_id: int) -> int:
    """已转入正式交易但观察记录仍残留时，归档并删除（兼容历史数据）。"""
    return svc.purge_observe_already_formal(db, user_id, source=SOURCE)


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
    db: Session, rows: List[TradeObserveStock]
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
    *,
    board_code_source: Optional[str] = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[tuple[str, str], str]:
    """按 (market, code) 批量解析所属行业：A 股优先行业板块表，其次基础信息表。

    A 股行业板默认仅取同花顺（``tonghuashun``）口径。
    """
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
        board_map = batch_industry_board_names_by_stock_codes(
            db, uniq, board_code_source=board_code_source
        )
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
    r: TradeObserveStock,
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
    r: TradeObserveStock,
    *,
    industry: Optional[str] = None,
    recompute_price_plan: bool = True,
) -> GmsTradeObserveItem:
    snap = r.signal_snapshot_json if isinstance(r.signal_snapshot_json, dict) else None
    sd = _resolve_signal_date_str(r.signal_date, snap)
    resolved_industry = industry or _industry_from_snapshot(snap)
    key_focus_flag = _extra_bool(r, "key_focus_flag", False)
    show_focus, manual_focus, score_total, watch_th = resolve_key_focus_display(
        key_focus_flag=key_focus_flag,
        snapshot=snap,
    )
    auto_focus = show_focus and not manual_focus
    latest_close_date_raw = _extra_dict(r).get("latest_close_date")
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
        latest_close_price=_extra_float(r, "latest_close_price"),
        latest_close_date=_format_stored_quote_date(latest_close_date_raw),
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _archive_trade_observe_row(
    db: Session,
    row: TradeObserveStock,
    *,
    removed_at: Optional[datetime] = None,
) -> TradeObserveHistory:
    """将当前观察记录写入统一历史表后由调用方删除原记录。"""
    now = removed_at or datetime.now()
    hist = TradeObserveHistory(
        user_id=row.user_id,
        market=row.market,
        code=row.code,
        name=row.name,
        source=row.source or SOURCE,
        signal_snapshot_json=row.signal_snapshot_json,
        signal_date=row.signal_date,
        extra_json=row.extra_json,
        observe_created_at=row.created_at,
        observe_updated_at=row.updated_at,
        source_observe_id=row.id,
        removed_at=now,
    )
    db.add(hist)
    return hist


def _history_row_to_item(r: TradeObserveHistory) -> GmsTradeObserveHistoryItem:
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
    # 取较多记录后按重点关注排序，保持旧前端体验
    total, all_rows = svc.list_observe(
        db, user.id, source=SOURCE, page=1, page_size=500
    )
    all_rows = sorted(
        all_rows,
        key=lambda r: (
            not _extra_bool(r, "key_focus_flag", False),
            -(r.updated_at.timestamp() if r.updated_at else 0),
            r.code or "",
        ),
    )
    start = (page - 1) * page_size
    rows = all_rows[start : start + page_size]
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
    return svc.list_observe_codes(db, user_id, source=SOURCE)


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
    _perm: None = Depends(require_permission("channel.screening.tab.gms.btn.refresh")),
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
    row = svc.add_observe(
        db,
        user,
        source=SOURCE,
        code=code,
        market=market,
        name=body.name,
        signal_date=sig_date,
        snapshot=snapshot_with_plan,
        extra={"key_focus_flag": focus_flag},
        require_signal_date=True,
    )
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
    row = svc.get_observe(db, user.id, item_id, source=SOURCE)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    key = _observe_row_key(row)
    latest = batch_lookup_latest_closes(db, [key]).get(key, (None, None))
    close_price, close_date = latest
    _apply_latest_close_to_row(row, close_price=close_price, close_date=close_date)
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return GmsTradeObserveLatestPriceResponse(
        id=row.id,
        market=row.market or "CN",
        code=row.code,
        latest_close_price=_extra_float(row, "latest_close_price"),
        latest_close_date=_format_stored_quote_date(_extra_dict(row).get("latest_close_date")),
    )


@router.get("/{item_id}/price-plan")
def get_gms_trade_observe_price_plan(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """刷新单条观察股交易价格计划。"""
    row = svc.get_observe(db, user.id, item_id, source=SOURCE)
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
    row = svc.get_observe(db, user.id, item_id, source=SOURCE)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    svc.update_observe_extra(db, row, {"key_focus_flag": bool(body.key_focus_flag)})
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
    total, rows = svc.list_history(
        db, user.id, source=SOURCE, page=page, page_size=page_size
    )
    return GmsTradeObserveHistoryListResponse(
        total=total,
        page=max(1, int(page)),
        page_size=min(500, max(1, int(page_size))),
        items=[_history_row_to_item(r) for r in rows],
    )


@router.delete("/{item_id}")
def remove_gms_trade_observe(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.screening.tab.gms.btn.refresh")),
):
    row = svc.get_observe(db, user.id, item_id, source=SOURCE)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    code, market = row.code, row.market
    hist = svc.remove_observe(db, user, item_id, source=SOURCE)
    write_gms_audit(
        db,
        "gms_trade_observe_remove",
        {"user_id": user.id, "code": code, "market": market, "history_id": hist.id},
    )
    return {
        "success": True,
        "message": "已移出交易观察列表并归档",
        "history_id": hist.id,
    }
