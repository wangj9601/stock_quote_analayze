"""
GMS MA60 数据源：以 ma_indicators.ma60 为唯一权威，写入 mean_frequency_resonance_indicators.ma60_d。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

Ma60Key = Tuple[str, str, str]  # (code, date YYYY-MM-DD, market_type)

# MA60 走平判定默认参数（回看周期默认与 GMS observation_period 一致，20 个交易日）
DEFAULT_OBSERVATION_PERIOD = 20
DEFAULT_MA60_FLAT_LOOKBACK_DAYS = DEFAULT_OBSERVATION_PERIOD
DEFAULT_MA60_FLAT_TOL = 0.015


def resolve_ma60_flat_lookback_days(config: Optional[Dict[str, Any]] = None) -> int:
    """解析 MA60 走平回看交易日数：优先 scoring.ma60_flat_lookback_days，否则 observation_period。"""
    cfg = config or {}
    scoring = cfg.get("scoring") or {}
    explicit = scoring.get("ma60_flat_lookback_days")
    if explicit is not None:
        try:
            return max(1, int(explicit))
        except (TypeError, ValueError):
            pass
    obs = cfg.get("observation_period", DEFAULT_OBSERVATION_PERIOD)
    try:
        return max(1, int(obs))
    except (TypeError, ValueError):
        return DEFAULT_MA60_FLAT_LOOKBACK_DAYS


def normalize_indicator_date(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if len(s) >= 10:
        return s[:10]
    return s


def ma60_key(code: Any, date: Any, market_type: Any) -> Ma60Key:
    return (str(code or "").strip(), normalize_indicator_date(date), str(market_type or "CN").strip())


def lookup_ma60_d(db, code: str, date: Any, market_type: str = "CN") -> Optional[float]:
    """从 ma_indicators 读取 ma60，作为 GMS ma60_d。"""
    from backend_api.models import MAIndicators

    code_s = str(code or "").strip()
    date_s = normalize_indicator_date(date)
    mt = str(market_type or "CN").strip()
    if not code_s or not date_s:
        return None
    row = (
        db.query(MAIndicators.ma60)
        .filter(
            MAIndicators.code == code_s,
            MAIndicators.date == date_s,
            MAIndicators.market_type == mt,
        )
        .first()
    )
    if not row or row[0] is None:
        return None
    try:
        v = float(row[0])
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def batch_lookup_ma60_d(db, keys: Iterable[Ma60Key]) -> Dict[Ma60Key, float]:
    """批量读取 ma_indicators.ma60。"""
    from sqlalchemy import tuple_

    from backend_api.models import MAIndicators

    norm: List[Ma60Key] = []
    seen = set()
    for code, date, mt in keys:
        k = ma60_key(code, date, mt)
        if not k[0] or not k[1] or k in seen:
            continue
        seen.add(k)
        norm.append(k)
    if not norm:
        return {}

    out: Dict[Ma60Key, float] = {}
    chunk = 400
    for i in range(0, len(norm), chunk):
        part = norm[i : i + chunk]
        rows = (
            db.query(
                MAIndicators.code,
                MAIndicators.date,
                MAIndicators.market_type,
                MAIndicators.ma60,
            )
            .filter(tuple_(MAIndicators.code, MAIndicators.date, MAIndicators.market_type).in_(part))
            .all()
        )
        for code, date, mt, ma60 in rows:
            if ma60 is None:
                continue
            try:
                v = float(ma60)
                if v > 0:
                    out[ma60_key(code, date, mt)] = v
            except (TypeError, ValueError):
                continue
    return out


def is_ma60_flat(ma60_now: Any, ma60_lag: Any, tol: float) -> bool:
    """MA60 走平：|ma60_now - ma60_lag| / ma60_lag < tol。缺数据视为非走平。"""
    if ma60_now is None or ma60_lag is None:
        return False
    try:
        now = float(ma60_now)
        lag = float(ma60_lag)
        t = float(tol)
    except (TypeError, ValueError):
        return False
    if now <= 0 or lag <= 0 or t <= 0:
        return False
    return abs(now - lag) / lag < t


def batch_lookup_ma60_lag(
    db,
    keys: Iterable[Ma60Key],
    lookback_days: int = DEFAULT_MA60_FLAT_LOOKBACK_DAYS,
) -> Dict[Ma60Key, float]:
    """批量读取各 key 对应日期前第 N 个交易日的 ma60（N = lookback_days）。"""
    from sqlalchemy import desc

    from backend_api.models import MAIndicators

    lookback = max(1, int(lookback_days))
    norm: List[Ma60Key] = []
    seen: set[Ma60Key] = set()
    for code, date, mt in keys:
        k = ma60_key(code, date, mt)
        if not k[0] or not k[1] or k in seen:
            continue
        seen.add(k)
        norm.append(k)
    if not norm:
        return {}

    by_cm: Dict[Tuple[str, str], List[str]] = {}
    for code, date, mt in norm:
        by_cm.setdefault((code, mt), []).append(date)

    out: Dict[Ma60Key, float] = {}
    for (code, mt), dates in by_cm.items():
        max_date = max(dates)
        rows = (
            db.query(MAIndicators.date, MAIndicators.ma60)
            .filter(
                MAIndicators.code == code,
                MAIndicators.market_type == mt,
                MAIndicators.date <= max_date,
                MAIndicators.ma60.isnot(None),
            )
            .order_by(desc(MAIndicators.date))
            .all()
        )
        history: List[Tuple[str, float]] = []
        for d, ma60 in rows:
            if ma60 is None:
                continue
            try:
                v = float(ma60)
                if v > 0:
                    history.append((normalize_indicator_date(d), v))
            except (TypeError, ValueError):
                continue

        for target_date in dates:
            prior = [(d, m) for d, m in history if d < target_date]
            if len(prior) < lookback:
                continue
            lag_ma60 = prior[lookback - 1][1]
            out[ma60_key(code, target_date, mt)] = lag_ma60
    return out


def enrich_rows_ma60_flat(
    db,
    rows: List[Dict[str, Any]],
    *,
    lookback_days: int = DEFAULT_MA60_FLAT_LOOKBACK_DAYS,
    tol: float = DEFAULT_MA60_FLAT_TOL,
) -> None:
    """为 GMS 指标 row 补全 ma60_d_lag、ma60_flat、ma60_flat_change_pct。"""
    if not rows:
        return
    keys: List[Ma60Key] = []
    for r in rows:
        k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
        if k[0] and k[1]:
            keys.append(k)
    if not keys:
        return
    try:
        lag_cache = batch_lookup_ma60_lag(db, keys, lookback_days=lookback_days)
        for r in rows:
            k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
            ma60_now = r.get("ma60_d")
            ma60_lag = lag_cache.get(k)
            r["ma60_d_lag"] = ma60_lag
            r["ma60_flat"] = is_ma60_flat(ma60_now, ma60_lag, tol)
            if ma60_now is not None and ma60_lag is not None:
                try:
                    lag_f = float(ma60_lag)
                    if lag_f > 0:
                        r["ma60_flat_change_pct"] = abs(float(ma60_now) - lag_f) / lag_f
                    else:
                        r["ma60_flat_change_pct"] = None
                except (TypeError, ValueError):
                    r["ma60_flat_change_pct"] = None
            else:
                r["ma60_flat_change_pct"] = None
    except Exception as e:
        logger.warning("GMS 补全 ma60_flat 失败: %s", e)


def enrich_rows_ma60_d(db, rows: List[Dict[str, Any]]) -> None:
    """为 GMS 指标 row 补全 ma60_d（仅当缺失时，来源 ma_indicators.ma60）。"""
    need_keys = []
    for r in rows:
        if r.get("ma60_d") is not None:
            continue
        k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
        if k[0] and k[1]:
            need_keys.append(k)
    if not need_keys:
        return
    try:
        cache = batch_lookup_ma60_d(db, need_keys)
        for r in rows:
            if r.get("ma60_d") is not None:
                continue
            k = ma60_key(r.get("code"), r.get("date"), r.get("market_type"))
            if k in cache:
                r["ma60_d"] = cache[k]
    except Exception as e:
        logger.warning("GMS 从 ma_indicators 补全 ma60_d 失败: %s", e)


def _terminate_conflicting_ma60_sync_sessions(db) -> int:
    """终止仍在跑的历史 ma60_d 同步 UPDATE，避免互相锁死。"""
    from sqlalchemy import text

    rows = db.execute(
        text(
            """
            SELECT pid
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
              AND state = 'active'
              AND query ILIKE '%mean_frequency_resonance_indicators%'
              AND query ILIKE '%ma60_d%'
            """
        )
    ).fetchall()
    n = 0
    for (pid,) in rows:
        if db.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}).scalar():
            n += 1
    if n:
        db.commit()
        logger.warning("已终止 %s 个冲突中的 ma60_d 同步会话，请勿并行重复执行本脚本", n)
    return n


def sync_mfr_ma60_d_from_ma_indicators(
    db,
    *,
    log_every: int = 50,
    terminate_conflicts: bool = True,
) -> int:
    """
    将 mean_frequency_resonance_indicators.ma60_d 与 ma_indicators.ma60 对齐。
    按 (code, market_type) 分批 UPDATE，避免大表全量 JOIN 长时间无响应。
    返回受影响行数。
    """
    import time

    from sqlalchemy import text

    if terminate_conflicts:
        _terminate_conflicting_ma60_sync_sessions(db)

    pairs_sql = text(
        """
        SELECT DISTINCT m.code, m.market_type
        FROM mean_frequency_resonance_indicators AS m
        WHERE m.ma60_d IS NULL
           OR EXISTS (
                SELECT 1
                FROM ma_indicators AS ma
                WHERE ma.code = m.code
                  AND ma.date = m.date
                  AND ma.market_type = m.market_type
                  AND ma.ma60 IS NOT NULL
                  AND m.ma60_d IS DISTINCT FROM ma.ma60
            )
        ORDER BY m.market_type, m.code
        """
    )
    pairs = db.execute(pairs_sql).fetchall()
    logger.info("待处理标的: %s 只（按 code+market 更新，请勿重复开多个窗口）", len(pairs))
    if not pairs:
        return 0

    update_sql = text(
        """
        UPDATE mean_frequency_resonance_indicators AS m
        SET ma60_d = ma.ma60
        FROM ma_indicators AS ma
        WHERE m.code = :code
          AND m.market_type = :market_type
          AND m.date = ma.date
          AND ma.code = m.code
          AND ma.market_type = m.market_type
          AND ma.ma60 IS NOT NULL
          AND (m.ma60_d IS NULL OR m.ma60_d IS DISTINCT FROM ma.ma60)
        """
    )

    total = 0
    t0 = time.time()
    for i, (code, market_type) in enumerate(pairs, start=1):
        result = db.execute(update_sql, {"code": code, "market_type": market_type})
        n = int(result.rowcount or 0)
        if n > 0:
            total += n
            db.commit()
        if i == 1 or i % log_every == 0 or i == len(pairs):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0.0
            eta = (len(pairs) - i) / rate if rate > 0 else 0.0
            logger.info(
                "进度 %s/%s 标的，累计 %s 行，已用 %.0fs，预计剩余 %.0fs",
                i,
                len(pairs),
                total,
                elapsed,
                eta,
            )
    db.commit()
    return total
