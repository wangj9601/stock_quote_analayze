# -*- coding: utf-8 -*-
"""URT 信号写入 urt_signal_trace。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend_core.strategies.gms.json_safe import sanitize_for_pg_json

logger = logging.getLogger(__name__)

# 回测/预计算：某日全市场扫描无买点时写入占位，避免重复全市场计算
URT_TRACE_SCANNED_MARKER = "__URT_SCANNED__"


def _enrich_trace_structure_fields(
    item: Dict[str, Any],
    *,
    score_detail: Any,
    close: Any = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    从 score_detail.structure 展平支撑/阻力；旧数据缺 rr/risk_tags 时只读补算（不改买点分）。
    """
    sd = score_detail if isinstance(score_detail, dict) else {}
    st = dict(sd.get("structure")) if isinstance(sd.get("structure"), dict) else {}
    px = close
    if px is None:
        px = item.get("close")

    risk_tags = sd.get("risk_tags") if isinstance(sd.get("risk_tags"), list) else None
    need_rr = st and (st.get("rr") is None and st.get("rr_reason") is None)
    need_tags = risk_tags is None and bool(st)

    if need_rr or need_tags:
        try:
            from backend_core.strategies.urt.risk_tags import enrich_structure_with_rr
            from backend_core.strategies.urt.config import URTConfigManager

            use_cfg = cfg
            if use_cfg is None:
                use_cfg = URTConfigManager().get_default_config()
            enriched = enrich_structure_with_rr(st, price=px, cfg=use_cfg)
            st = enriched["structure"]
            if need_tags or not risk_tags:
                risk_tags = enriched["risk_tags"]
            # 仅内存合并，不回写 DB
            sd = dict(sd)
            sd["structure"] = st
            sd["risk_tags"] = risk_tags or []
            item["score_detail"] = sd
        except Exception as e:
            logger.debug("URT trace structure RR 补算跳过: %s", e)
            risk_tags = risk_tags or []

    item["support_levels"] = st.get("support_levels") or []
    item["resistance_levels"] = st.get("resistance_levels") or []
    item["nearest_support"] = st.get("nearest_support")
    item["nearest_resistance"] = st.get("nearest_resistance")
    item["kde_ok"] = st.get("kde_ok")
    item["kde_reason"] = st.get("kde_reason")
    item["kde_lookback_used"] = st.get("kde_lookback_used")
    item["structure_rr"] = st.get("rr")
    item["structure_rr_reason"] = st.get("rr_reason")
    item["structure_rr_downside_floored"] = st.get("rr_downside_floored")
    item["structure_rr_min_downside_pct"] = st.get("rr_min_downside_pct")
    item["structure_rr_upside_pct"] = st.get("rr_upside_pct")
    item["structure_rr_downside_pct"] = st.get("rr_downside_pct")
    item["structure_rr_floor_source"] = st.get("rr_floor_source")
    item["structure_rr_level_rank"] = st.get("rr_level_rank")
    item["risk_tags"] = risk_tags if isinstance(risk_tags, list) else (sd.get("risk_tags") or [])
    return item


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


def delete_trace_for_code_config_in_range(
    db: Session,
    *,
    code: str,
    config_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """删除某股某参数版本在指定日期区间内的 URT 信号（含区间端点）。"""
    from backend_api.models import URTSignalTrace

    code_n = _normalize_a_share_code(code)
    q = db.query(URTSignalTrace).filter(
        URTSignalTrace.code == code_n,
        URTSignalTrace.config_id == int(config_id),
    )
    start_s = str(start_date).strip()[:10] if start_date else None
    end_s = str(end_date).strip()[:10] if end_date else None
    if start_s:
        q = q.filter(URTSignalTrace.date >= start_s)
    if end_s:
        q = q.filter(URTSignalTrace.date <= end_s)
    n = q.delete(synchronize_session=False)
    db.commit()
    return int(n or 0)


def _throttled_progress_cb(
    progress_cb: Optional[Callable[[int, int, str], None]],
    *,
    min_step: int = 25,
    min_interval_sec: float = 2.0,
) -> Optional[Callable[[int, int, str], None]]:
    """降低进度回调频率，避免每个交易日写库。"""
    if progress_cb is None:
        return None
    state = {"last_current": 0, "last_ts": 0.0}

    def wrapper(current: int, total: int, msg: str) -> None:
        import time

        now = time.monotonic()
        force = current <= 1 or current >= total
        if (
            not force
            and current - state["last_current"] < min_step
            and now - state["last_ts"] < min_interval_sec
        ):
            return
        state["last_current"] = current
        state["last_ts"] = now
        progress_cb(current, total, msg)

    return wrapper


def count_trace_rows_for_config(db: Session, *, config_id: int) -> int:
    """统计某参数版本在 urt_signal_trace 中的行数（含扫描占位）。"""
    from sqlalchemy import func

    from backend_api.models import URTSignalTrace

    n = (
        db.query(func.count())
        .select_from(URTSignalTrace)
        .filter(URTSignalTrace.config_id == int(config_id))
        .scalar()
    )
    return int(n or 0)


def delete_trace_for_config(db: Session, *, config_id: int) -> int:
    """删除某参数版本的全部 URT 信号与扫描占位（__URT_SCANNED__）。"""
    from backend_api.models import URTSignalTrace

    n = (
        db.query(URTSignalTrace)
        .filter(URTSignalTrace.config_id == int(config_id))
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    对单股按交易日滚动重算 URT 信号并写入 urt_signal_trace（require_pass=False）。

    默认对齐 GMS：使用该股 historical_quotes 中的**全部**历史行情；
    仅跳过指标预热不足的最早若干日。进度分母为可评交易日数。
    若传入 start_date/end_date，仅重算该区间内可评日（并向前多取指标预热段），
    且只删除/覆盖区间内旧 trace。
    若传入 lookback_calendar_days 或环境变量 URT_TRACE_RECOMPUTE_LOOKBACK_DAYS，
    则仅重算最近 N 个自然日（兼容旧行为/压测；与显式 start_date 互斥时以 start_date 为准）。
    返回写入条数。
    """
    from backend_core.strategies.urt.data_loader import URTDataLoader
    from backend_core.strategies.urt.indicators import min_bars_needed
    from backend_core.strategies.urt.signal_detector import (
        evaluate_buy_signal,
        history_calendar_days_for_fetch,
    )

    code_n = _normalize_a_share_code(code)
    need = max(1, int(min_bars_needed(config)))
    progress_cb = _throttled_progress_cb(progress_cb)

    range_start = str(start_date).strip()[:10] if start_date else None
    range_end = str(end_date).strip()[:10] if end_date else None
    use_explicit_range = bool(range_start or range_end)

    # 默认全历史；显式参数或环境变量可限制窗口
    if not use_explicit_range and lookback_calendar_days is None:
        env_raw = (os.getenv("URT_TRACE_RECOMPUTE_LOOKBACK_DAYS") or "").strip()
        if env_raw.isdigit() and int(env_raw) > 0:
            lookback_calendar_days = int(env_raw)

    if use_explicit_range:
        delete_trace_for_code_config_in_range(
            db,
            code=code_n,
            config_id=config_id,
            start_date=range_start,
            end_date=range_end,
        )
    else:
        delete_trace_for_code_config(db, code=code_n, config_id=config_id)

    loader = URTDataLoader(db)
    end_s = range_end or URTDataLoader.resolve_effective_history_end_date(db, None)
    try:
        end_d = datetime.strptime(end_s, "%Y-%m-%d").date()
    except ValueError:
        end_d = datetime.now().date()
        end_s = end_d.strftime("%Y-%m-%d")

    start_s: Optional[str] = None
    if use_explicit_range and range_start:
        try:
            range_start_d = datetime.strptime(range_start, "%Y-%m-%d").date()
        except ValueError:
            range_start_d = None
        if range_start_d is not None:
            warmup_cal = max(
                int(history_calendar_days_for_fetch(config)),
                max(60, need * 3),
            )
            start_s = (range_start_d - timedelta(days=warmup_cal)).strftime("%Y-%m-%d")
    elif lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
        # 限制窗口时额外多取预热段，避免窗口头部不可评
        fetch_days = int(lookback_calendar_days) + max(60, need * 3)
        start_s = (end_d - timedelta(days=fetch_days)).strftime("%Y-%m-%d")

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
    if use_explicit_range:
        clipped: List[int] = []
        for i in eval_indices:
            date_i = str(hist[i].get("date") or "")[:10]
            if range_start and date_i < range_start:
                continue
            if range_end and date_i > range_end:
                continue
            clipped.append(i)
        eval_indices = clipped
    elif lookback_calendar_days is not None and int(lookback_calendar_days) > 0:
        window_start = (end_d - timedelta(days=int(lookback_calendar_days))).strftime("%Y-%m-%d")
        clipped_lb: List[int] = []
        for i in eval_indices:
            date_i = str(hist[i].get("date") or "")[:10]
            if date_i < window_start:
                break
            clipped_lb.append(i)
        eval_indices = clipped_lb

    eval_total = len(eval_indices)
    if eval_total <= 0:
        return 0

    logger.info(
        "URT 单股重算 %s config_id=%s bars=%s evaluable=%s range=%s..%s lookback=%s",
        code_n,
        config_id,
        bar_total,
        eval_total,
        range_start or "-",
        range_end or end_s,
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
            # 确保当日 KDE 支撑/阻力写入 score_detail.structure（记录表 JSON）
            sd = detail.get("score_detail")
            if not isinstance(sd, dict):
                sd = {}
                detail["score_detail"] = sd
            st = sd.get("structure") if isinstance(sd.get("structure"), dict) else {}
            if not st.get("method"):
                st = {
                    "support_levels": detail.get("support_levels") or [],
                    "resistance_levels": detail.get("resistance_levels") or [],
                    "nearest_support": detail.get("nearest_support"),
                    "nearest_resistance": detail.get("nearest_resistance"),
                    "kde_ok": detail.get("kde_ok"),
                    "kde_reason": detail.get("kde_reason"),
                    "kde_lookback_used": detail.get("kde_lookback_used"),
                    "kde_lookback_expanded": detail.get("kde_lookback_expanded"),
                    "method": "kde_volume_weighted",
                }
                sd["structure"] = st
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
            score_detail=sanitize_for_pg_json(r.get("score_detail")),
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


def marker_covers_universe_request(
    extra: Optional[Dict[str, Any]],
    *,
    want_pool: bool,
    pool_need: int = 1,
    min_full_market_codes: int = 500,
) -> bool:
    """``__URT_SCANNED__`` 占位是否覆盖当前回测范围。

    股票池扫描（scope=pool、candidates 约百只）不得冒充全市场已覆盖。
    """
    extra = extra if isinstance(extra, dict) else {}
    scope = str(extra.get("scope") or "").strip().lower()
    try:
        candidates = extra.get("candidates")
        cand_n = int(candidates) if candidates is not None else None
    except (TypeError, ValueError):
        cand_n = None
    threshold = max(1, int(min_full_market_codes))
    if not want_pool:
        if scope == "pool":
            return False
        if cand_n is not None and cand_n < threshold:
            return False
        if scope == "full_market":
            return True
        return cand_n is not None and cand_n >= threshold
    if scope == "full_market":
        return True
    if scope == "pool":
        return cand_n is not None and cand_n >= max(1, int(pool_need))
    return False


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
    1. 存在扫描占位 ``__URT_SCANNED__``，且占位范围覆盖本次请求
       （全市场任务不认 ``scope=pool`` 的小池占位）；
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
    if min_full_market_codes is None:
        env_raw = (os.getenv("URT_FULL_MARKET_TRACE_MIN_CODES") or "").strip()
        min_full_market_codes = int(env_raw) if env_raw.isdigit() else 500
    threshold = max(1, int(min_full_market_codes))
    want_pool = bool(stock_pool)
    pool_need = 1
    if want_pool:
        pool_n = len(
            {
                str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
                for c in stock_pool
                if str(c).strip()
            }
        )
        pool_need = max(1, int((pool_n * 4 + 4) // 5))

    # 1) 扫描占位（按 scope/candidates 过滤，避免小池占位冒充全市场）
    marker_rows = (
        db.query(URTSignalTrace.date, URTSignalTrace.score_detail)
        .filter(
            URTSignalTrace.config_id == cid,
            URTSignalTrace.code == URT_TRACE_SCANNED_MARKER,
            URTSignalTrace.date.in_(date_list),
        )
        .all()
    )
    ready = set()
    for r in marker_rows:
        d = str(r[0])[:10] if r[0] else ""
        if not d:
            continue
        if marker_covers_universe_request(
            r[1] if isinstance(r[1], dict) else {},
            want_pool=want_pool,
            pool_need=pool_need,
            min_full_market_codes=threshold,
        ):
            ready.add(d)

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
        item = {
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
        _enrich_trace_structure_fields(item, score_detail=row.score_detail, close=row.close)
        out.append(item)
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
    out: List[Dict[str, Any]] = []
    for r in rows:
        item = {
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
        _enrich_trace_structure_fields(item, score_detail=r.score_detail, close=r.close)
        out.append(item)
    return out


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace(" ", "T") if "T" not in s and " " in s else s)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        return None


def get_trace_freshness(
    db: Session,
    *,
    config_id: int,
    config_updated_at: Any = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    比较策略版本 updated_at 与 trace 最新 created_at，标记是否可能读到改参前缓存。
    不删数据；仅供提示。
    """
    from sqlalchemy import func

    from backend_api.models import URTSignalTrace, URTStrategyConfig

    cfg_dt = _parse_dt(config_updated_at)
    if cfg_dt is None:
        row = (
            db.query(URTStrategyConfig)
            .filter(URTStrategyConfig.id == int(config_id))
            .first()
        )
        cfg_dt = _parse_dt(getattr(row, "updated_at", None) if row else None)

    q = db.query(func.max(URTSignalTrace.created_at)).filter(
        URTSignalTrace.config_id == int(config_id)
    )
    if code:
        code_n = str(code).strip()
        if code_n.isdigit() and len(code_n) <= 6:
            code_n = code_n.zfill(6)
        q = q.filter(URTSignalTrace.code == code_n)
    trace_dt = _parse_dt(q.scalar())

    stale = bool(cfg_dt and trace_dt and trace_dt < cfg_dt)
    need_recompute = bool(cfg_dt and (trace_dt is None or trace_dt < cfg_dt))
    return {
        "config_id": int(config_id),
        "config_updated_at": cfg_dt.isoformat(sep=" ", timespec="seconds") if cfg_dt else None,
        "trace_computed_at": (
            trace_dt.isoformat(sep=" ", timespec="seconds") if trace_dt else None
        ),
        "stale": stale,
        "need_recompute": need_recompute,
    }