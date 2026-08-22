# -*- coding: utf-8 -*-
"""统一交易观察 / 正式交易服务层。

供统一 routes 与旧策略路由薄封装调用；旧表不再写入新数据。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend_api.models import FormalTrade, TradeObserveHistory, TradeObserveStock, User

logger = logging.getLogger(__name__)

# 来源枚举（字符串）
SOURCE_GMS = "gms"
SOURCE_URT = "urt"
SOURCE_SBBR = "sbbr"
SOURCE_RPE = "rpe"
SOURCE_TRIPLE_VOLUME = "triple_volume"
SOURCE_STOCK_ANALYSIS = "stock_analysis"
SOURCE_GANN_TREND = "gann_trend"

VALID_SOURCES = frozenset(
    {
        SOURCE_GMS,
        SOURCE_URT,
        SOURCE_SBBR,
        SOURCE_RPE,
        SOURCE_TRIPLE_VOLUME,
        SOURCE_STOCK_ANALYSIS,
        SOURCE_GANN_TREND,
    }
)

_DEFAULT_LOT_SIZE = 100


def normalize_market(market: Optional[str], code: str) -> str:
    """归一化市场代码：CN / HK。"""
    m = (market or "").strip().upper()
    if m in ("CN", "HK"):
        return m
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return "HK"
    return "CN"


def normalize_code(code: str) -> str:
    """归一化股票代码（A 股补齐 6 位，港股补齐 5 位）。"""
    c = str(code or "").strip()
    if len(c) == 5 and c.isdigit():
        return c.zfill(5)
    if c.isdigit() and len(c) <= 6:
        return c.zfill(6)
    return c


def validate_source(source: str) -> str:
    s = (source or "").strip().lower()
    if s not in VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"无效 source：{source}，允许值：{', '.join(sorted(VALID_SOURCES))}",
        )
    return s


def _as_extra(extra: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if extra is None:
        return None
    if not isinstance(extra, dict):
        return None
    return dict(extra)


def _merge_extra(
    existing: Optional[Dict[str, Any]],
    patch: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not patch:
        return existing if isinstance(existing, dict) else None
    base = dict(existing) if isinstance(existing, dict) else {}
    base.update(patch)
    return base


def _lot_size_for_market(market: Optional[str]) -> int:
    _ = (market or "").strip().upper()
    return _DEFAULT_LOT_SIZE


def compute_formal_trade_pnl(
    entry_price: Optional[float],
    exit_price: Optional[float],
    position_lots: Optional[int],
    market: Optional[str],
) -> Tuple[Optional[float], Optional[float]]:
    """计算盈亏金额（元）与盈亏比例（%）。"""
    if entry_price is None or exit_price is None:
        return None, None
    ep = float(entry_price)
    xp = float(exit_price)
    if ep <= 0:
        return None, None
    lots = max(0, int(position_lots or 0))
    shares = lots * _lot_size_for_market(market)
    pnl_amount = round((xp - ep) * shares, 2)
    pnl_percent = round((xp - ep) / ep * 100, 2)
    return pnl_amount, pnl_percent


def sync_formal_trade_pnl(row: FormalTrade) -> None:
    """平仓时写入盈亏；持仓中或重新开仓时清空。"""
    if (row.status or "open") == "closed" and row.exit_price is not None:
        amt, pct = compute_formal_trade_pnl(
            row.entry_price,
            row.exit_price,
            row.position_lots,
            row.market,
        )
        row.pnl_amount = amt
        row.pnl_percent = pct
    else:
        row.pnl_amount = None
        row.pnl_percent = None


def resolve_signal_date_str(
    stored: Optional[date],
    snapshot: Optional[Dict[str, Any]],
) -> Optional[str]:
    if stored and hasattr(stored, "strftime"):
        return stored.strftime("%Y-%m-%d")
    if stored:
        s = str(stored).strip()[:10]
        return s if s else None
    if isinstance(snapshot, dict):
        for key in ("signal_date", "search_date", "date", "observe_trade_date"):
            raw = snapshot.get(key)
            if raw:
                return str(raw).strip()[:10]
    return None


def parse_signal_date_optional(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="signal_date 格式应为 YYYY-MM-DD")


def code_key(market: Optional[str], code: Optional[str]) -> Optional[str]:
    c = normalize_code(str(code or ""))
    if not c:
        return None
    m = (market or "CN").upper()
    return f"{m}:{c}"


def add_observe(
    db: Session,
    user: User,
    *,
    source: str,
    code: str,
    market: Optional[str] = None,
    name: Optional[str] = None,
    signal_date: Optional[date] = None,
    snapshot: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    require_signal_date: bool = False,
) -> TradeObserveStock:
    """加入或更新交易观察；同 user+market+code+source 已存在则更新 snapshot/name/date/extra。"""
    src = validate_source(source)
    norm_code = normalize_code(code)
    if not norm_code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    norm_market = normalize_market(market, norm_code)
    snap = snapshot if isinstance(snapshot, dict) else None
    extra_dict = _as_extra(extra)

    if signal_date is None and snap:
        for key in ("signal_date", "search_date", "date", "observe_trade_date"):
            raw = snap.get(key)
            if raw:
                signal_date = parse_signal_date_optional(str(raw))
                break

    if require_signal_date and signal_date is None:
        raise HTTPException(status_code=400, detail="缺少 signal_date：请传入信号对应交易日")

    existing = (
        db.query(TradeObserveStock)
        .filter(
            TradeObserveStock.user_id == user.id,
            TradeObserveStock.market == norm_market,
            TradeObserveStock.code == norm_code,
            TradeObserveStock.source == src,
        )
        .first()
    )
    now = datetime.now()
    if existing:
        existing.name = name or existing.name
        if snap is not None:
            existing.signal_snapshot_json = snap
        if signal_date is not None:
            existing.signal_date = signal_date
        if extra_dict is not None:
            existing.extra_json = _merge_extra(
                existing.extra_json if isinstance(existing.extra_json, dict) else None,
                extra_dict,
            )
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        logger.info(
            "交易观察已更新 user_id=%s source=%s market=%s code=%s id=%s",
            user.id,
            src,
            norm_market,
            norm_code,
            existing.id,
        )
        return existing

    row = TradeObserveStock(
        user_id=user.id,
        market=norm_market,
        code=norm_code,
        name=name,
        source=src,
        signal_date=signal_date,
        signal_snapshot_json=snap,
        extra_json=extra_dict,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "交易观察已新增 user_id=%s source=%s market=%s code=%s id=%s",
        user.id,
        src,
        norm_market,
        norm_code,
        row.id,
    )
    return row


def get_observe(
    db: Session,
    user_id: int,
    observe_id: int,
    *,
    source: Optional[str] = None,
) -> Optional[TradeObserveStock]:
    q = db.query(TradeObserveStock).filter(
        TradeObserveStock.id == observe_id,
        TradeObserveStock.user_id == user_id,
    )
    if source:
        q = q.filter(TradeObserveStock.source == validate_source(source))
    return q.first()


def list_observe(
    db: Session,
    user_id: int,
    *,
    source: Optional[str] = None,
    page: int = 1,
    page_size: int = 200,
) -> Tuple[int, List[TradeObserveStock]]:
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(TradeObserveStock).filter(TradeObserveStock.user_id == user_id)
    if source:
        q = q.filter(TradeObserveStock.source == validate_source(source))
    total = q.count()
    rows = (
        q.order_by(TradeObserveStock.updated_at.desc(), TradeObserveStock.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, rows


def list_observe_codes(
    db: Session,
    user_id: int,
    *,
    source: Optional[str] = None,
) -> List[str]:
    q = db.query(TradeObserveStock.market, TradeObserveStock.code).filter(
        TradeObserveStock.user_id == user_id
    )
    if source:
        q = q.filter(TradeObserveStock.source == validate_source(source))
    out: List[str] = []
    for m, c in q.all():
        key = code_key(m, c)
        if key:
            out.append(key)
    return out


def _archive_observe_row(
    db: Session,
    row: TradeObserveStock,
    *,
    removed_at: Optional[datetime] = None,
) -> TradeObserveHistory:
    now = removed_at or datetime.now()
    hist = TradeObserveHistory(
        user_id=row.user_id,
        market=row.market,
        code=row.code,
        name=row.name,
        source=row.source,
        signal_date=row.signal_date,
        signal_snapshot_json=row.signal_snapshot_json,
        extra_json=row.extra_json,
        observe_created_at=row.created_at,
        observe_updated_at=row.updated_at,
        source_observe_id=row.id,
        removed_at=now,
    )
    db.add(hist)
    return hist


def remove_observe(
    db: Session,
    user: User,
    observe_id: int,
    *,
    source: Optional[str] = None,
) -> TradeObserveHistory:
    """移除观察并写入历史归档。"""
    row = get_observe(db, user.id, observe_id, source=source)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    hist = _archive_observe_row(db, row)
    db.delete(row)
    db.commit()
    db.refresh(hist)
    logger.info(
        "交易观察已移除并归档 user_id=%s source=%s id=%s history_id=%s",
        user.id,
        row.source,
        observe_id,
        hist.id,
    )
    return hist


def list_history(
    db: Session,
    user_id: int,
    *,
    source: Optional[str] = None,
    page: int = 1,
    page_size: int = 200,
) -> Tuple[int, List[TradeObserveHistory]]:
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(TradeObserveHistory).filter(TradeObserveHistory.user_id == user_id)
    if source:
        q = q.filter(TradeObserveHistory.source == validate_source(source))
    total = q.count()
    rows = (
        q.order_by(TradeObserveHistory.removed_at.desc(), TradeObserveHistory.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, rows


def find_open_formal(
    db: Session,
    user_id: int,
    *,
    market: str,
    code: str,
    source: str,
) -> Optional[FormalTrade]:
    return (
        db.query(FormalTrade)
        .filter(
            FormalTrade.user_id == user_id,
            FormalTrade.market == market,
            FormalTrade.code == code,
            FormalTrade.source == source,
            FormalTrade.status == "open",
        )
        .first()
    )


def add_formal_from_observe(
    db: Session,
    user: User,
    observe_id: int,
    *,
    entry_price: float,
    position_lots: int,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> FormalTrade:
    """从观察转入正式交易；同 user+market+code+source 至多一条 open。"""
    observe = get_observe(db, user.id, observe_id, source=source)
    if not observe:
        raise HTTPException(status_code=404, detail="交易观察记录不存在")
    now = datetime.now()
    existing_open = find_open_formal(
        db,
        user.id,
        market=observe.market,
        code=observe.code,
        source=observe.source,
    )
    if existing_open:
        _archive_observe_row(db, observe, removed_at=now)
        db.delete(observe)
        db.commit()
        db.refresh(existing_open)
        logger.info(
            "正式交易已存在 open 记录，已归档观察 user_id=%s source=%s trade_id=%s",
            user.id,
            observe.source,
            existing_open.id,
        )
        return existing_open

    if float(entry_price) <= 0:
        raise HTTPException(status_code=400, detail="入场价格无效")
    if int(position_lots) < 0:
        raise HTTPException(status_code=400, detail="仓位（手）不能为负")

    source_observe_id = observe.id
    row = FormalTrade(
        user_id=user.id,
        market=observe.market,
        code=observe.code,
        name=observe.name,
        source=observe.source,
        source_observe_id=source_observe_id,
        entry_price=float(entry_price),
        position_lots=int(position_lots),
        exit_price=None,
        status="open",
        signal_date=observe.signal_date,
        signal_snapshot_json=observe.signal_snapshot_json,
        notes=(notes or "").strip() or None,
        entry_at=now,
        exit_at=None,
        extra_json=_as_extra(extra)
        or (observe.extra_json if isinstance(observe.extra_json, dict) else None),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _archive_observe_row(db, observe, removed_at=now)
    db.delete(observe)
    db.commit()
    db.refresh(row)
    logger.info(
        "已从观察转入正式交易 user_id=%s source=%s trade_id=%s observe_id=%s",
        user.id,
        row.source,
        row.id,
        source_observe_id,
    )
    return row


def list_formal(
    db: Session,
    user_id: int,
    *,
    source: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 200,
) -> Tuple[int, List[FormalTrade]]:
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    q = db.query(FormalTrade).filter(FormalTrade.user_id == user_id)
    if source:
        q = q.filter(FormalTrade.source == validate_source(source))
    st = (status or "").strip().lower()
    if st in ("open", "closed"):
        q = q.filter(FormalTrade.status == st)
    total = q.count()
    rows = (
        q.order_by(FormalTrade.entry_at.desc(), FormalTrade.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, rows


def list_formal_codes(
    db: Session,
    user_id: int,
    *,
    source: Optional[str] = None,
) -> List[str]:
    q = db.query(FormalTrade.market, FormalTrade.code).filter(FormalTrade.user_id == user_id)
    if source:
        q = q.filter(FormalTrade.source == validate_source(source))
    out: List[str] = []
    for m, c in q.all():
        key = code_key(m, c)
        if key:
            out.append(key)
    return out


def get_formal(
    db: Session,
    user_id: int,
    trade_id: int,
    *,
    source: Optional[str] = None,
) -> Optional[FormalTrade]:
    q = db.query(FormalTrade).filter(
        FormalTrade.id == trade_id,
        FormalTrade.user_id == user_id,
    )
    if source:
        q = q.filter(FormalTrade.source == validate_source(source))
    return q.first()


def patch_formal(
    db: Session,
    user: User,
    trade_id: int,
    *,
    source: Optional[str] = None,
    entry_price: Optional[float] = None,
    position_lots: Optional[int] = None,
    exit_price: Optional[float] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    reopen: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> FormalTrade:
    """更新正式交易；至少支持 exit_price / status / notes / position_lots。"""
    row = get_formal(db, user.id, trade_id, source=source)
    if not row:
        raise HTTPException(status_code=404, detail="正式交易记录不存在")
    now = datetime.now()
    was_closed = (row.status or "open") == "closed"

    if entry_price is not None:
        if float(entry_price) <= 0:
            raise HTTPException(status_code=400, detail="入场价格无效")
        row.entry_price = float(entry_price)
    if position_lots is not None:
        if int(position_lots) < 0:
            raise HTTPException(status_code=400, detail="仓位（手）不能为负")
        row.position_lots = int(position_lots)
    if notes is not None:
        row.notes = notes.strip() or None
    if extra is not None:
        row.extra_json = _merge_extra(
            row.extra_json if isinstance(row.extra_json, dict) else None,
            _as_extra(extra),
        )

    if reopen:
        row.exit_price = None
        row.status = "open"
        row.exit_at = None
    elif exit_price is not None:
        if float(exit_price) <= 0:
            raise HTTPException(status_code=400, detail="出场价格无效")
        row.exit_price = float(exit_price)
        if not was_closed:
            row.status = "closed"
            row.exit_at = now

    if status is not None and not reopen:
        st = str(status).strip().lower()
        if st not in ("open", "closed"):
            raise HTTPException(status_code=400, detail="status 仅支持 open/closed")
        # 改为 open 时需确保不会与已有 open 冲突
        if st == "open" and (row.status or "") != "open":
            conflict = find_open_formal(
                db,
                user.id,
                market=row.market,
                code=row.code,
                source=row.source,
            )
            if conflict and conflict.id != row.id:
                raise HTTPException(
                    status_code=400,
                    detail="同来源下该股票已有持仓中的正式交易，无法重新开仓",
                )
        row.status = st
        if st == "closed" and row.exit_at is None:
            row.exit_at = now
        if st == "open":
            row.exit_at = None
            if exit_price is None:
                row.exit_price = None

    sync_formal_trade_pnl(row)
    row.updated_at = now
    db.commit()
    db.refresh(row)
    logger.info(
        "正式交易已更新 user_id=%s source=%s trade_id=%s status=%s",
        user.id,
        row.source,
        row.id,
        row.status,
    )
    return row


def delete_formal(
    db: Session,
    user: User,
    trade_id: int,
    *,
    source: Optional[str] = None,
) -> None:
    row = get_formal(db, user.id, trade_id, source=source)
    if not row:
        raise HTTPException(status_code=404, detail="正式交易记录不存在")
    db.delete(row)
    db.commit()
    logger.info(
        "正式交易已删除 user_id=%s source=%s trade_id=%s",
        user.id,
        source or "",
        trade_id,
    )


def update_observe_extra(
    db: Session,
    row: TradeObserveStock,
    patch: Dict[str, Any],
) -> TradeObserveStock:
    """合并更新观察记录的 extra_json。"""
    row.extra_json = _merge_extra(
        row.extra_json if isinstance(row.extra_json, dict) else None,
        patch,
    )
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def purge_observe_already_formal(
    db: Session,
    user_id: int,
    *,
    source: str,
) -> int:
    """已有正式交易（任意状态）的观察残留：归档并删除。"""
    src = validate_source(source)
    formal_keys = {
        ((m or "CN").upper(), normalize_code(c))
        for m, c in (
            db.query(FormalTrade.market, FormalTrade.code)
            .filter(FormalTrade.user_id == user_id, FormalTrade.source == src)
            .all()
        )
        if c
    }
    if not formal_keys:
        return 0
    rows = (
        db.query(TradeObserveStock)
        .filter(TradeObserveStock.user_id == user_id, TradeObserveStock.source == src)
        .all()
    )
    removed = 0
    now = datetime.now()
    for row in rows:
        key = ((row.market or "CN").upper(), normalize_code(row.code))
        if key in formal_keys:
            _archive_observe_row(db, row, removed_at=now)
            db.delete(row)
            removed += 1
    if removed:
        db.commit()
        logger.info(
            "已清理转入正式交易后残留的观察 user_id=%s source=%s count=%s",
            user_id,
            src,
            removed,
        )
    return removed
