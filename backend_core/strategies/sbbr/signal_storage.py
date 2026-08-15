"""SBBR 信号落库。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def upsert_signal_traces(
    db,
    rows: List[Dict[str, Any]],
    *,
    config_id: int,
    trade_date: str,
) -> int:
    from backend_api.models import SBBRSignalTrace

    n = 0
    for r in rows:
        code = str(r.get("code") or r.get("symbol") or "").strip()
        if not code:
            continue
        date_s = str(r.get("date") or trade_date)[:10]
        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
        except ValueError:
            continue

        existing = (
            db.query(SBBRSignalTrace)
            .filter(
                SBBRSignalTrace.code == code,
                SBBRSignalTrace.trade_date == d,
                SBBRSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        payload = dict(
            name=r.get("name"),
            market_type=r.get("market_type") or "CN",
            total_mv=r.get("total_mv"),
            circ_mv=r.get("circ_mv"),
            size_ok=r.get("size_ok"),
            bottom_mode=r.get("bottom_mode"),
            bottom_matched=bool(r.get("bottom_matched")),
            entry_signal=bool(r.get("entry_signal")),
            entry_low=r.get("entry_low"),
            defense_low=r.get("defense_low"),
            defense_high=r.get("defense_high"),
            defense_buffer_pct=r.get("defense_buffer_pct"),
            close_price=r.get("close"),
            ma20=r.get("ma20"),
            volume_ratio=r.get("volume_ratio"),
            exit_flags=r.get("exit_flags") or {},
            position_advice=r.get("position_advice") or {},
            detail={
                **(r.get("detail") or {}),
                **(
                    {"circ_shares_yi": r.get("circ_shares_yi")}
                    if r.get("circ_shares_yi") is not None
                    else {}
                ),
            },
            updated_at=datetime.now(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            db.add(
                SBBRSignalTrace(
                    code=code,
                    trade_date=d,
                    config_id=int(config_id),
                    created_at=datetime.now(),
                    **payload,
                )
            )
        n += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("SBBR upsert_signal_traces failed: %s", e)
        raise
    return n


def load_traces(
    db,
    *,
    trade_date: str,
    config_id: int,
    entry_only: bool = False,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    from backend_api.models import SBBRSignalTrace

    d = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    q = db.query(SBBRSignalTrace).filter(
        SBBRSignalTrace.trade_date == d,
        SBBRSignalTrace.config_id == int(config_id),
    )
    if entry_only:
        q = q.filter(SBBRSignalTrace.entry_signal.is_(True))
    rows = q.order_by(SBBRSignalTrace.entry_signal.desc(), SBBRSignalTrace.code.asc()).limit(limit).all()
    out = []
    for r in rows:
        detail = r.detail or {}
        structure = detail.get("structure") if isinstance(detail.get("structure"), dict) else {}
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else trade_date,
                "market_type": r.market_type,
                "total_mv": r.total_mv,
                "circ_mv": r.circ_mv,
                "circ_shares_yi": detail.get("circ_shares_yi"),
                "size_ok": r.size_ok,
                "bottom_mode": r.bottom_mode,
                "bottom_matched": r.bottom_matched,
                "entry_signal": r.entry_signal,
                "entry_low": r.entry_low,
                "defense_low": r.defense_low,
                "defense_high": r.defense_high,
                "defense_buffer_pct": r.defense_buffer_pct,
                "close": r.close_price,
                "ma20": r.ma20,
                "volume_ratio": r.volume_ratio,
                "box_support": detail.get("support"),
                "box_resistance": detail.get("resistance"),
                "nearest_support": structure.get("nearest_support"),
                "nearest_resistance": structure.get("nearest_resistance"),
                "kde_ok": structure.get("kde_ok"),
                "kde_reason": structure.get("kde_reason"),
                "kde_lookback_used": structure.get("kde_lookback_used"),
                "exit_flags": r.exit_flags or {},
                "position_advice": r.position_advice or {},
                "detail": detail,
                "config_id": r.config_id,
            }
        )
    return out


def query_traces_by_code(
    db,
    *,
    code: str,
    config_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entry_only: bool = False,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """按股票代码查询 sbbr_signal_trace（日期倒序）。"""
    from backend_api.models import SBBRSignalTrace

    code_n = str(code or "").strip()
    if code_n.isdigit() and len(code_n) <= 6:
        code_n = code_n.zfill(6)
    q = db.query(SBBRSignalTrace).filter(SBBRSignalTrace.code == code_n)
    if config_id is not None:
        q = q.filter(SBBRSignalTrace.config_id == int(config_id))
    if start_date:
        d0 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        q = q.filter(SBBRSignalTrace.trade_date >= d0)
    if end_date:
        d1 = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
        q = q.filter(SBBRSignalTrace.trade_date <= d1)
    if entry_only:
        q = q.filter(SBBRSignalTrace.entry_signal.is_(True))
    rows = q.order_by(SBBRSignalTrace.trade_date.desc()).limit(int(limit)).all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        detail = r.detail or {}
        structure = detail.get("structure") if isinstance(detail.get("structure"), dict) else {}
        out.append(
            {
                "code": r.code,
                "symbol": r.code,
                "name": r.name,
                "date": r.trade_date.isoformat() if r.trade_date else None,
                "market_type": r.market_type,
                "total_mv": r.total_mv,
                "circ_mv": r.circ_mv,
                "circ_shares_yi": detail.get("circ_shares_yi"),
                "size_ok": r.size_ok,
                "bottom_mode": r.bottom_mode,
                "bottom_matched": r.bottom_matched,
                "entry_signal": r.entry_signal,
                "entry_low": r.entry_low,
                "defense_low": r.defense_low,
                "defense_high": r.defense_high,
                "defense_buffer_pct": r.defense_buffer_pct,
                "close": r.close_price,
                "ma20": r.ma20,
                "volume_ratio": r.volume_ratio,
                "box_support": detail.get("support"),
                "box_resistance": detail.get("resistance"),
                "nearest_support": structure.get("nearest_support"),
                "nearest_resistance": structure.get("nearest_resistance"),
                "kde_ok": structure.get("kde_ok"),
                "kde_reason": structure.get("kde_reason"),
                "kde_lookback_used": structure.get("kde_lookback_used"),
                "exit_flags": r.exit_flags or {},
                "position_advice": r.position_advice or {},
                "detail": detail,
                "config_id": r.config_id,
                "source": "trace",
            }
        )
    return out


def delete_traces_for_code_config(db, *, code: str, config_id: int) -> int:
    """删除某股某参数版本的全部 SBBR trace。"""
    from backend_api.models import SBBRSignalTrace

    code_n = str(code or "").strip()
    if code_n.isdigit() and len(code_n) <= 6:
        code_n = code_n.zfill(6)
    n = (
        db.query(SBBRSignalTrace)
        .filter(
            SBBRSignalTrace.code == code_n,
            SBBRSignalTrace.config_id == int(config_id),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


def recompute_trace_for_stock(
    db,
    *,
    code: str,
    config_id: int,
    config: Optional[Dict[str, Any]] = None,
    lookback_calendar_days: Optional[int] = None,
    progress_cb=None,
) -> int:
    """
    对单股按交易日滚动重算 SBBR 信号并写入 sbbr_signal_trace。

    默认对齐 URT/GMS：使用该股 historical_quotes 中的全部历史行情；
    仅跳过指标预热不足的最早若干日。若传入 lookback_calendar_days
    或环境变量 SBBR_TRACE_RECOMPUTE_LOOKBACK_DAYS，则仅重算最近 N 个自然日。
    返回写入条数。
    """
    import os
    from datetime import datetime, timedelta

    from backend_core.strategies.gms.structure_levels import kde_bars_limit
    from backend_core.strategies.sbbr.config import SBBRConfigManager
    from backend_core.strategies.sbbr.data_loader import SBBRDataLoader, _norm_code
    from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

    code_n = _norm_code(code)
    cfg = config or SBBRConfigManager().get_config(int(config_id))
    scan_cfg = cfg.get("scan") or {}
    hist_n = int(scan_cfg.get("history_bars", 120))
    min_need = 30

    if lookback_calendar_days is None:
        env_raw = (os.getenv("SBBR_TRACE_RECOMPUTE_LOOKBACK_DAYS") or "").strip()
        if env_raw.isdigit() and int(env_raw) > 0:
            lookback_calendar_days = int(env_raw)

    delete_traces_for_code_config(db, code=code_n, config_id=int(config_id))

    engine = SBBRStrategyEngine(db_session=db, config=cfg)
    end_eff = engine.loader.resolve_effective_trade_date(None)
    try:
        end_d = datetime.strptime(end_eff, "%Y-%m-%d").date()
    except ValueError:
        end_d = datetime.now().date()
        end_eff = end_d.strftime("%Y-%m-%d")

    if lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
        fetch_days = int(lookback_calendar_days) + max(60, hist_n * 2)
        start_fetch = (end_d - timedelta(days=fetch_days)).strftime("%Y-%m-%d")
        load_n = fetch_days + max(hist_n, kde_bars_limit(cfg)) + 5
    else:
        start_fetch = None
        load_n = 8000

    bars_all = engine.loader.load_bars(code_n, end_date=end_eff, limit=load_n)
    bars_all = SBBRDataLoader.truncate_bars_asof(bars_all, end_eff)
    if start_fetch:
        bars_all = [b for b in bars_all if str(b.get("date") or "")[:10] >= start_fetch]
    if len(bars_all) < min_need:
        logger.info(
            "SBBR 单股重算 %s 历史不足 need=%s bars=%s，跳过写入",
            code_n,
            min_need,
            len(bars_all),
        )
        return 0

    trade_dates = [b["date"] for b in bars_all]
    eval_dates: List[str] = []
    for i, d in enumerate(trade_dates):
        if i + 1 < min_need:
            continue
        if lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
            window_start = (end_d - timedelta(days=int(lookback_calendar_days))).strftime("%Y-%m-%d")
            if d < window_start:
                continue
        eval_dates.append(d)

    if not eval_dates:
        return 0

    mkt_lookback = max(80, int(((cfg.get("entry") or {}).get("market_lookback_days") or 5)) + 20)
    idx_bars = engine.loader.load_bars(
        "000001",
        end_date=end_eff,
        limit=max(load_n, len(bars_all)) + mkt_lookback,
    )
    idx_bars = SBBRDataLoader.truncate_bars_asof(idx_bars, end_eff)
    dated_mrets = []
    for i in range(1, len(idx_bars)):
        p0 = float(idx_bars[i - 1].get("close") or 0)
        p1 = float(idx_bars[i].get("close") or 0)
        ret = (p1 - p0) / p0 if p0 > 0 else 0.0
        dated_mrets.append((idx_bars[i]["date"], ret))

    share_info = engine.loader.load_share_map([code_n], as_of_date=end_eff).get(code_n) or {}

    logger.info(
        "SBBR 单股全历史重算 %s config_id=%s bars=%s evaluable=%s lookback=%s",
        code_n,
        config_id,
        len(bars_all),
        len(eval_dates),
        lookback_calendar_days,
    )

    rows: List[Dict[str, Any]] = []
    total = len(eval_dates)
    batch_size = 80
    last_date = eval_dates[-1]

    for idx, d in enumerate(eval_dates):
        if progress_cb:
            progress_cb(idx + 1, total, f"正在计算 {d}（{idx + 1}/{total}）")
        try:
            mrets = [r for dd, r in dated_mrets if dd <= d][-mkt_lookback:]
            row = engine.evaluate_code(
                code_n,
                date=d,
                config=cfg,
                share_info=share_info,
                market_returns=mrets,
                bars=bars_all,
            )
            if not row:
                continue
            row["date"] = d
            if row.get("detail") and isinstance(row["detail"], dict):
                row["detail"] = dict(row["detail"])
                row["detail"]["asof_date"] = d
            rows.append(row)
        except Exception as e:
            logger.debug("SBBR 单股重算跳过 %s day=%s: %s", code_n, d, e)
            continue

        if len(rows) >= batch_size:
            upsert_signal_traces(db, rows, config_id=int(config_id), trade_date=d)
            rows = []

    if rows:
        upsert_signal_traces(db, rows, config_id=int(config_id), trade_date=last_date)

    from backend_api.models import SBBRSignalTrace

    written = (
        db.query(SBBRSignalTrace)
        .filter(
            SBBRSignalTrace.code == code_n,
            SBBRSignalTrace.config_id == int(config_id),
        )
        .count()
    )
    if progress_cb:
        progress_cb(written, written, f"写入完成（{written}/{written}）")
    return int(written)
