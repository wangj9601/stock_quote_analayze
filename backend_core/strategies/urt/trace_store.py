# -*- coding: utf-8 -*-
"""URT 信号写入 urt_signal_trace。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 回测/预计算：某日全市场扫描无买点时写入占位，避免重复全市场计算
URT_TRACE_SCANNED_MARKER = "__URT_SCANNED__"


def _normalize_a_share_code(code: str) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def delete_trace_for_code_config(db: Session, *, code: str, config_id: int) -> int:
    """删除某股某参数版本的全部 URT 信号历史。"""
    from backend_api.models import URTSignalTrace

    code_n = _normalize_a_share_code(code)
    n = (
        db.query(URTSignalTrace)
        .filter(
            URTSignalTrace.code == code_n,
            URTSignalTrace.config_id == int(config_id),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


def recompute_trace_for_stock(
    db: Session,
    *,
    code: str,
    config_id: int,
    config: Dict[str, Any],
    lookback_calendar_days: Optional[int] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    对单股按交易日滚动重算 URT 信号并写入 urt_signal_trace（require_pass=False）。

    默认对齐 GMS：使用该股 historical_quotes 中的**全部**历史行情；
    仅跳过指标预热不足的最早若干日。进度分母为可评交易日数。
    若传入 lookback_calendar_days 或环境变量 URT_TRACE_RECOMPUTE_LOOKBACK_DAYS，
    则仅重算最近 N 个自然日（兼容旧行为/压测）。
    返回写入条数。
    """
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.indicators import min_bars_needed
    from backend_core.strategies.urt.signal_detector import evaluate_buy_signal

    code_n = _normalize_a_share_code(code)
    need = max(1, int(min_bars_needed(config)))

    # 默认全历史；显式参数或环境变量可限制窗口
    if lookback_calendar_days is None:
        env_raw = (os.getenv("URT_TRACE_RECOMPUTE_LOOKBACK_DAYS") or "").strip()
        if env_raw.isdigit() and int(env_raw) > 0:
            lookback_calendar_days = int(env_raw)

    delete_trace_for_code_config(db, code=code_n, config_id=config_id)

    loader = URTDataLoader(db)
    end_s = URTDataLoader.resolve_effective_history_end_date(db, None)
    try:
        end_d = datetime.strptime(end_s, "%Y-%m-%d").date()
    except ValueError:
        end_d = datetime.now().date()
        end_s = end_d.strftime("%Y-%m-%d")

    start_s: Optional[str] = None
    if lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
        # 限制窗口时额外多取预热段，避免窗口头部不可评
        fetch_days = int(lookback_calendar_days) + max(60, need * 3)
        start_s = (end_d - timedelta(days=fetch_days)).strftime("%Y-%m-%d")

    # 默认：不传 start_date，拉取该股全部历史行情
    hist = loader.fetch_historical_desc(code_n, start_date=start_s, end_date=end_s)
    if not hist:
        return 0

    name = str(hist[0].get("name") or "")
    bar_total = len(hist)
    # hist 为日期 DESC：index0=最新；可评条件 len(hist[i:]) >= need → i <= bar_total - need
    last_eval_i = bar_total - need
    if last_eval_i < 0:
        logger.info(
            "URT 单股重算 %s 历史不足 need=%s bars=%s，跳过写入",
            code_n,
            need,
            bar_total,
        )
        return 0

    eval_indices: List[int] = list(range(0, last_eval_i + 1))
    if lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
        window_start = (end_d - timedelta(days=int(lookback_calendar_days))).strftime("%Y-%m-%d")
        clipped: List[int] = []
        for i in eval_indices:
            date_i = str(hist[i].get("date") or "")[:10]
            if date_i < window_start:
                break
            clipped.append(i)
        eval_indices = clipped

    eval_total = len(eval_indices)
    if eval_total <= 0:
        return 0

    logger.info(
        "URT 单股全历史重算 %s config_id=%s bars=%s evaluable=%s lookback=%s",
        code_n,
        config_id,
        bar_total,
        eval_total,
        lookback_calendar_days,
    )

    rows: List[Dict[str, Any]] = []
    for idx, i in enumerate(eval_indices):
        date_i = str(hist[i].get("date") or "")[:10]
        if progress_cb:
            progress_cb(idx + 1, eval_total, f"正在计算 {date_i}（{idx + 1}/{eval_total}）")
        try:
            detail = evaluate_buy_signal(hist[i:], config, require_pass=False)
            if not detail:
                continue
            rows.append({"code": code_n, "name": name, **detail})
        except Exception as e:
            logger.debug("URT 单股重算跳过 %s day=%s: %s", code_n, date_i, e)
            continue

    written = upsert_trace_rows(db, config_id=config_id, rows=rows)
    # 完成时用实际写入数校正进度分母，与 GMS「写入 N 条」展示一致
    if progress_cb:
        progress_cb(written, written, f"写入完成（{written}/{written}）")
    return written


def upsert_trace_rows(
    db: Session,
    *,
    config_id: int,
    rows: List[Dict[str, Any]],
) -> int:
    """批量 upsert；每行需含 code、signal_date（或 date）。返回写入条数。"""
    from backend_api.models import URTSignalTrace

    n = 0
    now = datetime.now()
    for r in rows:
        code = str(r.get("code") or "").strip()
        date_s = str(r.get("signal_date") or r.get("date") or "")[:10]
        if not code or not date_s:
            continue
        existing = (
            db.query(URTSignalTrace)
            .filter(
                URTSignalTrace.code == code,
                URTSignalTrace.date == date_s,
                URTSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        fields = dict(
            name=r.get("name"),
            buy_signal=bool(r.get("buy_signal")),
            score=r.get("score"),
            signal_strength=r.get("signal_strength", r.get("score")),
            close=r.get("close"),
            open=r.get("open"),
            ma20=r.get("ma20"),
            above_ma20=r.get("above_ma20"),
            yang_count_4=r.get("yang_count_4"),
            yang_count_5=r.get("yang_count_5"),
            yang_rule=r.get("yang_rule"),
            volume=r.get("volume"),
            avg_volume_20=r.get("avg_volume_20"),
            volume_multiple=r.get("volume_multiple"),
            volume_ratio=r.get("volume_ratio"),
            turnover_rate=r.get("turnover_rate"),
            score_detail=r.get("score_detail"),
            created_at=now,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(
                URTSignalTrace(
                    code=code,
                    date=date_s,
                    config_id=int(config_id),
                    **fields,
                )
            )
        n += 1
        if n % 200 == 0:
            db.commit()
    db.commit()
    return n


def dates_with_trace_coverage(
    db: Session,
    *,
    config_id: int,
    dates: List[str],
) -> set:
    """返回在 urt_signal_trace 中已有任意记录（含扫描占位）的交易日集合。"""
    from backend_api.models import URTSignalTrace

    if not dates:
        return set()
    date_list = [str(d)[:10] for d in dates]
    rows = (
        db.query(URTSignalTrace.date)
        .filter(
            URTSignalTrace.config_id == int(config_id),
            URTSignalTrace.date.in_(date_list),
        )
        .distinct()
        .all()
    )
    return {str(r[0])[:10] for r in rows if r[0]}


def dates_ready_for_universe_backtest(
    db: Session,
    *,
    config_id: int,
    dates: List[str],
    stock_pool: Optional[List[str]] = None,
    min_full_market_codes: Optional[int] = None,
) -> set:
    """
    判断回测区间内哪些交易日已具备「全市场/股票池」级预计算，而非仅有零星个股 trace。

    就绪条件（满足其一即可）：
    1. 存在扫描占位 ``__URT_SCANNED__``（表示当日已做过全量扫描）；
    2. 全市场：当日去重股票数 ≥ min_full_market_codes（默认 500，可用环境变量
       URT_FULL_MARKET_TRACE_MIN_CODES 覆盖）；
    3. 指定股票池：当日覆盖池内代码数 ≥ max(1, ceil(0.8 * len(pool)))。
    """
    from sqlalchemy import func

    from backend_api.models import URTSignalTrace

    if not dates:
        return set()
    date_list = [str(d)[:10] for d in dates]
    cid = int(config_id)

    # 1) 扫描占位
    marker_rows = (
        db.query(URTSignalTrace.date)
        .filter(
            URTSignalTrace.config_id == cid,
            URTSignalTrace.code == URT_TRACE_SCANNED_MARKER,
            URTSignalTrace.date.in_(date_list),
        )
        .distinct()
        .all()
    )
    ready = {str(r[0])[:10] for r in marker_rows if r[0]}

    pending = [d for d in date_list if d not in ready]
    if not pending:
        return ready

    # 2) 按代码数量判断是否达到全市场/池级覆盖
    cnt_rows = (
        db.query(URTSignalTrace.date, func.count(func.distinct(URTSignalTrace.code)))
        .filter(
            URTSignalTrace.config_id == cid,
            URTSignalTrace.date.in_(pending),
            URTSignalTrace.code != URT_TRACE_SCANNED_MARKER,
        )
        .group_by(URTSignalTrace.date)
        .all()
    )
    count_by_date = {str(r[0])[:10]: int(r[1] or 0) for r in cnt_rows if r[0]}

    if stock_pool:
        pool_set = {
            str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
            for c in stock_pool
            if str(c).strip()
        }
        need = max(1, int((len(pool_set) * 4 + 4) // 5))  # ceil(0.8 * n)
        # 池内命中数：再查一次按池过滤（池很大时用阈值近似）
        if len(pool_set) <= 2000:
            pool_cnt_rows = (
                db.query(URTSignalTrace.date, func.count(func.distinct(URTSignalTrace.code)))
                .filter(
                    URTSignalTrace.config_id == cid,
                    URTSignalTrace.date.in_(pending),
                    URTSignalTrace.code.in_(list(pool_set)),
                )
                .group_by(URTSignalTrace.date)
                .all()
            )
            for r in pool_cnt_rows:
                d = str(r[0])[:10]
                if int(r[1] or 0) >= need:
                    ready.add(d)
        else:
            for d, n in count_by_date.items():
                if n >= need:
                    ready.add(d)
    else:
        if min_full_market_codes is None:
            env_raw = (os.getenv("URT_FULL_MARKET_TRACE_MIN_CODES") or "").strip()
            min_full_market_codes = int(env_raw) if env_raw.isdigit() else 500
        threshold = max(1, int(min_full_market_codes))
        for d, n in count_by_date.items():
            if n >= threshold:
                ready.add(d)

    return ready


def mark_date_scanned(
    db: Session,
    *,
    config_id: int,
    trade_date: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """写入/更新当日全量扫描占位。"""
    detail = {"marker": "universe_scanned"}
    if extra:
        detail.update(extra)
    upsert_trace_rows(
        db,
        config_id=int(config_id),
        rows=[
            {
                "code": URT_TRACE_SCANNED_MARKER,
                "name": "",
                "signal_date": str(trade_date)[:10],
                "buy_signal": False,
                "score": 0,
                "score_detail": detail,
            }
        ],
    )


def query_buy_signals_for_date(
    db: Session,
    *,
    trade_date: str,
    config_id: int,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = (
        db.query(URTSignalTrace)
        .filter(
            URTSignalTrace.date == str(trade_date)[:10],
            URTSignalTrace.config_id == int(config_id),
            URTSignalTrace.buy_signal.is_(True),
            URTSignalTrace.code != URT_TRACE_SCANNED_MARKER,
        )
        .order_by(URTSignalTrace.score.desc())
    )
    if min_score is not None:
        q = q.filter(URTSignalTrace.score >= float(min_score))
    if limit:
        q = q.limit(int(limit))
    out: List[Dict[str, Any]] = []
    for row in q.all():
        out.append(
            {
                "code": row.code,
                "name": row.name or "",
                "signal_date": row.date,
                "close": row.close,
                "open": row.open,
                "ma20": row.ma20,
                "above_ma20": row.above_ma20,
                "yang_count_4": row.yang_count_4,
                "yang_count_5": row.yang_count_5,
                "yang_rule": row.yang_rule,
                "avg_volume_20": row.avg_volume_20,
                "volume": row.volume,
                "volume_multiple": row.volume_multiple,
                "volume_ratio": row.volume_ratio,
                "turnover_rate": row.turnover_rate,
                "score": row.score,
                "signal_strength": row.signal_strength,
                "score_detail": row.score_detail,
                "buy_signal": True,
                "from_cache": True,
            }
        )
    return out


def query_trace_by_code(
    db: Session,
    *,
    code: str,
    config_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    from backend_api.models import URTSignalTrace

    q = db.query(URTSignalTrace).filter(URTSignalTrace.code == str(code).strip())
    if config_id is not None:
        q = q.filter(URTSignalTrace.config_id == int(config_id))
    if start_date:
        q = q.filter(URTSignalTrace.date >= str(start_date)[:10])
    if end_date:
        q = q.filter(URTSignalTrace.date <= str(end_date)[:10])
    rows = q.order_by(URTSignalTrace.date.desc()).limit(int(limit)).all()
    return [
        {
            "code": r.code,
            "name": r.name,
            "date": r.date,
            "config_id": r.config_id,
            "buy_signal": r.buy_signal,
            "score": r.score,
            "close": r.close,
            "open": r.open,
            "ma20": r.ma20,
            "above_ma20": r.above_ma20,
            "yang_count_4": r.yang_count_4,
            "yang_count_5": r.yang_count_5,
            "yang_rule": r.yang_rule,
            "volume": r.volume,
            "avg_volume_20": r.avg_volume_20,
            "volume_multiple": r.volume_multiple,
            "volume_ratio": r.volume_ratio,
            "turnover_rate": r.turnover_rate,
            "score_detail": r.score_detail,
        }
        for r in rows
    ]
