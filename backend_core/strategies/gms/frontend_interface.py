"""
GMS 前端选股接口
供 API 与回测调用的选股入口。
策略信号记录优先从 gms_signal_trace 表读取；若不存在或缺失，则增量重新计算，结果回填写入 gms_signal_trace。
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime

from sqlalchemy import cast, distinct, func, String

from .data_loader import GMSDataLoader
from .strategy_engine import GMSStrategyEngine
from .config import GMSConfigManager
from .json_safe import sanitize_for_pg_json

from backend_api.services.gms_selection_snapshot import enrich_trace_meta

logger = logging.getLogger(__name__)

_GMS_BATCH_SIZE = max(50, int(os.getenv("GMS_SCREENING_BATCH_SIZE", "200")))


def _is_a_share(code: str) -> bool:
    from backend_api.utils.cn_listed_board_filter import is_cn_listed_equity_code

    return is_cn_listed_equity_code(code)


def _is_etf(code: str) -> bool:
    s = str(code).strip()
    return len(s) >= 6 and s.isdigit() and s[0] in "518"


def _infer_market_type(code: str) -> str:
    if _is_a_share(code):
        return "CN"
    if _is_etf(code):
        return "ETF"
    return "HK"


def _normalize_cn_pool_code(code: Any) -> str:
    if code is None:
        return ""
    s = str(code).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _normalize_hk_pool_code(code: Any) -> str:
    if code is None:
        return ""
    s = str(code).strip()
    if s.isdigit() and len(s) < 5:
        return s.zfill(5)
    return s


def _normalize_etf_pool_code(code: Any) -> str:
    return str(code).strip() if code is not None else ""


def _resolve_pool_date_for_quotes(db, requested: str, model) -> str:
    """
    将请求日解析为行情表上可用的池基准日：
    - 晚于表内最新日：钳到 MAX(date)
    - 当日无采集记录：回退 MAX(date)
    - 否则使用请求日
    """
    requested = str(requested or "").strip()[:10]
    if not requested:
        requested = datetime.now().strftime("%Y-%m-%d")

    col = model.date
    row_max = db.query(func.max(col)).scalar()
    if row_max is None:
        return requested
    if hasattr(row_max, "strftime"):
        max_s = row_max.strftime("%Y-%m-%d")
    else:
        max_s = str(row_max).strip()[:10]

    if requested > max_s:
        return max_s

    exists = (
        db.query(model.code)
        .filter(cast(col, String) == requested)
        .limit(1)
        .first()
    )
    if exists is not None:
        return requested
    return max_s


def _distinct_codes_from_quotes(
    db,
    model,
    date_str: str,
    normalize_fn: Callable[[Any], str],
) -> List[str]:
    """取指定交易日行情表内 DISTINCT code（即当日已采集股票）。"""
    rows = (
        db.query(distinct(model.code))
        .filter(cast(model.date, String) == date_str)
        .order_by(model.code)
        .all()
    )
    out: List[str] = []
    seen: set[str] = set()
    for row in rows:
        if not row or row[0] is None:
            continue
        code = normalize_fn(row[0])
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _trace_row_to_result(row) -> dict:
    """将 gms_signal_trace 表的一行转为与 engine.screen 一致的选股结果 dict。"""
    code_str = str(row.code).strip() if row.code is not None else ""
    delta = getattr(row, "delta", None)
    d = getattr(row, "d", None)
    instant_deviation = getattr(row, "instant_deviation", None)
    # 与 strategy_engine 中 score_detail 的口径对齐：
    # d20 = d + instant_deviation
    # d1  = d20 - delta
    d20 = (d + instant_deviation) if (d is not None and instant_deviation is not None) else None
    d1 = (d20 - delta) if (d20 is not None and delta is not None) else None
    score_detail = {
        "score_total": getattr(row, "score_total", None),
        "score_accumulation": getattr(row, "score_accumulation", None),
        "score_momentum": getattr(row, "score_momentum", None),
        "score_acc_fz": getattr(row, "score_acc_fz", None),
        "score_acc_balance": getattr(row, "score_acc_balance", None),
        "score_acc_volume": getattr(row, "score_acc_volume", None),
        "score_mom_ratio_d1": getattr(row, "score_mom_ratio_d1", None),
        "score_mom_deviation": getattr(row, "score_mom_deviation", None),
        "score_mom_volume": getattr(row, "score_mom_volume", None),
        "acc_fz_judge": getattr(row, "acc_fz_judge", None),
        "acc_balance_judge": getattr(row, "acc_balance_judge", None),
        "acc_volume_judge": getattr(row, "acc_volume_judge", None),
        "mom_ratio_d1_judge": getattr(row, "mom_ratio_d1_judge", None),
        "mom_deviation_judge": getattr(row, "mom_deviation_judge", None),
        "mom_volume_judge": getattr(row, "mom_volume_judge", None),
        "accumulation_grade": getattr(row, "accumulation_grade", None),
        "momentum_grade": getattr(row, "momentum_grade", None),
        # 指标细项（前端得分明细面板直接读取这些字段）
        "delta": delta,
        "d": d,
        "d20": d20,
        "d1": d1,
        "ratio_d20": getattr(row, "ratio_d20", None),
        "ratio_d1": getattr(row, "ratio_d1", None),
        "fz_ratio": getattr(row, "fz_ratio", None),
        "volume_ratio": getattr(row, "volume_ratio", None),
        "instant_deviation": instant_deviation,
        "rising_days": getattr(row, "rising_days", None),
        "falling_days": getattr(row, "falling_days", None),
    }
    risk_tags = getattr(row, "risk_tags", None)
    if risk_tags is None and hasattr(row, "__dict__"):
        risk_tags = row.__dict__.get("risk_tags")
    # 合并库内 JSON 明细（含 ratio_d / avg_volume_20d 等），避免读出后被列级重建冲掉、触发昂贵兜底重算
    stored_sd = getattr(row, "score_detail", None)
    if isinstance(stored_sd, dict) and stored_sd:
        merged = dict(stored_sd)
        for k, v in score_detail.items():
            if merged.get(k) is None and v is not None:
                merged[k] = v
        score_detail = merged
    # 顶层展示字段从明细回填
    ratio_d = score_detail.get("ratio_d")
    avg_volume_20d = score_detail.get("avg_volume_20d")
    current_volume = score_detail.get("current_volume")
    out = {
        "symbol": code_str,
        "code": code_str,
        "date": row.date,
        "market_type": row.market_type,
        "score_total": row.score_total,
        "score_accumulation": getattr(row, "score_accumulation", None),
        "score_momentum": getattr(row, "score_momentum", None),
        "left_buy_signal": row.left_buy_signal,
        "right_buy_signal": row.right_buy_signal,
        "buy_type": (row.buy_type or "").strip(),
        "signal_strength": getattr(row, "signal_strength", None),
        "sell_signal": getattr(row, "sell_signal", None),
        "delta": delta,
        "d": d,
        "ratio_d20": getattr(row, "ratio_d20", None),
        "ratio_d1": getattr(row, "ratio_d1", None),
        "ratio_d": ratio_d,
        "fz_ratio": getattr(row, "fz_ratio", None),
        "rising_days": getattr(row, "rising_days", None),
        "falling_days": getattr(row, "falling_days", None),
        "avg_volume_20d": avg_volume_20d,
        "current_volume": current_volume,
        "score_detail": score_detail,
        "risk_tags": risk_tags or [],
    }
    # 从 score_detail.structure 展平 KDE 支撑/阻力（与 URT 口径一致）
    st = score_detail.get("structure") if isinstance(score_detail.get("structure"), dict) else {}
    if st:
        from .structure_levels import flatten_structure_to_result

        flatten_structure_to_result(out, st)
    return out


def result_needs_structure(result: Optional[dict]) -> bool:
    """旧版 trace/快照无 structure，或未写入 method 时需补算 KDE 支撑/阻力。"""
    if not isinstance(result, dict):
        return False
    sd = result.get("score_detail") if isinstance(result.get("score_detail"), dict) else {}
    st = sd.get("structure") if isinstance(sd.get("structure"), dict) else None
    if not st:
        return True
    # 已跑过 compute_structure_levels / empty_structure（含失败空结果）则不再重算
    return st.get("method") != "kde_volume_weighted"


def _persist_structure_to_trace(
    db,
    *,
    code: str,
    date: str,
    market_type: str,
    config_id: int,
    structure: dict,
) -> None:
    """回填 score_detail.structure（可与减分同步一并调用）。"""
    if not code or not date or structure is None:
        return
    try:
        from sqlalchemy.orm.attributes import flag_modified
        from backend_api.models import GMSSignalTrace

        row = (
            db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.code == str(code).strip(),
                GMSSignalTrace.date == str(date).strip()[:10],
                GMSSignalTrace.market_type == str(market_type or "").strip(),
                GMSSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        if not row:
            return
        sd = dict(row.score_detail) if isinstance(row.score_detail, dict) else {}
        sd["structure"] = structure
        row.score_detail = sanitize_for_pg_json(sd)
        flag_modified(row, "score_detail")
        with db.begin_nested():
            db.flush()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("回填 gms_signal_trace.structure 失败 %s: %s", code, e)


def _persist_penalty_score_to_trace(
    db,
    *,
    code: str,
    date: str,
    market_type: str,
    config_id: int,
    score_detail: dict,
    score_total: float,
    signal_strength: Optional[float] = None,
) -> None:
    """回填减分同步后的总分与 score_detail。"""
    if not code or not date:
        return
    try:
        from sqlalchemy.orm.attributes import flag_modified
        from backend_api.models import GMSSignalTrace

        row = (
            db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.code == str(code).strip(),
                GMSSignalTrace.date == str(date).strip()[:10],
                GMSSignalTrace.market_type == str(market_type or "").strip(),
                GMSSignalTrace.config_id == int(config_id),
            )
            .first()
        )
        if not row:
            return
        row.score_detail = sanitize_for_pg_json(score_detail)
        flag_modified(row, "score_detail")
        row.score_total = float(score_total)
        if signal_strength is not None:
            row.signal_strength = float(signal_strength)
        with db.begin_nested():
            db.flush()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("回填 gms_signal_trace 减分得分失败 %s: %s", code, e)


def sync_penalties_with_structure(
    db,
    results: List[dict],
    config: Optional[dict],
    *,
    date: Optional[str] = None,
    config_id: Optional[int] = None,
    persist: bool = True,
) -> int:
    """
    减分版在已有 KDE structure 时重跑 PenaltyEngine，修正「仅展示 RR、未扣分」的旧 trace。
    以 score_base_total（或 总分+旧减分）为基准重算最终分。
    """
    if not results:
        return 0
    scoring = (config or {}).get("scoring") or {}
    if (scoring.get("mechanism") or "").strip() != "tiered_dual_penalty":
        return 0
    rules = scoring.get("penalty_rules") or []
    if not any(
        isinstance(r, dict) and r.get("id") == "poor_structure_rr" and r.get("enabled", True)
        for r in rules
    ):
        return 0

    from .scoring.penalties import PenaltyEngine

    engine = PenaltyEngine(config or {})
    updated = 0
    for r in results:
        if not isinstance(r, dict):
            continue
        sd = dict(r.get("score_detail")) if isinstance(r.get("score_detail"), dict) else {}
        st = sd.get("structure") if isinstance(sd.get("structure"), dict) else {}
        ns = r.get("nearest_support")
        if ns is None:
            ns = st.get("nearest_support")
        nr = r.get("nearest_resistance")
        if nr is None:
            nr = st.get("nearest_resistance")
        if ns is None and nr is None and not st:
            continue

        row = dict(sd)
        row["nearest_support"] = ns
        row["nearest_resistance"] = nr
        if row.get("d20") is None:
            try:
                d_val = row.get("d")
                inst = row.get("instant_deviation")
                if d_val is not None and inst is not None:
                    row["d20"] = float(d_val) + float(inst)
            except (TypeError, ValueError):
                pass

        deduction, details = engine.apply(row)
        base = sd.get("score_base_total")
        if base is None:
            try:
                old_total = r.get("score_total")
                if old_total is None:
                    old_total = sd.get("score_total")
                old_ded = sd.get("score_penalty_deduction") or 0
                if old_total is None:
                    continue
                base = float(old_total) + float(old_ded)
            except (TypeError, ValueError):
                continue
        try:
            base_f = float(base)
            ded_f = float(deduction)
        except (TypeError, ValueError):
            continue
        final = max(0.0, min(100.0, base_f - ded_f))

        old_ded = sd.get("score_penalty_deduction")
        try:
            old_ded_f = float(old_ded) if old_ded is not None else 0.0
        except (TypeError, ValueError):
            old_ded_f = 0.0
        old_pen = sd.get("penalties") if isinstance(sd.get("penalties"), list) else []
        old_keys = {
            (p.get("id"), round(float(p.get("points") or 0), 4))
            for p in old_pen
            if isinstance(p, dict) and p.get("applied", True)
        }
        new_keys = {
            (p.get("id"), round(float(p.get("points") or 0), 4))
            for p in details
            if isinstance(p, dict)
        }
        if abs(old_ded_f - ded_f) < 1e-9 and old_keys == new_keys:
            continue

        sd["score_base_total"] = base_f
        sd["score_penalty_deduction"] = ded_f
        sd["penalties"] = details
        sd["score_total"] = final
        if st:
            sd["structure"] = st
        r["score_detail"] = sd
        r["score_total"] = final
        r["score_penalty_deduction"] = ded_f
        strength = (final / 100.0) if final > 0 else 0.0
        r["signal_strength"] = strength
        updated += 1

        if persist and config_id is not None:
            code = str(r.get("code") or r.get("symbol") or "").strip()
            end_d = str(r.get("date") or date or "").strip()[:10]
            mt = str(r.get("market_type") or _infer_market_type(code)).strip().upper() or "CN"
            if code and end_d:
                _persist_penalty_score_to_trace(
                    db,
                    code=code,
                    date=end_d,
                    market_type=mt,
                    config_id=int(config_id),
                    score_detail=sd,
                    score_total=final,
                    signal_strength=strength,
                )

    if updated and persist and config_id is not None:
        try:
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning("GMS 减分同步 commit 失败 date=%s config_id=%s", date, config_id)
    if updated:
        logger.info(
            "GMS 结构盈亏比减分同步 updated=%s date=%s config_id=%s",
            updated,
            date,
            config_id,
        )
    return updated


def enrich_results_with_structure(
    db,
    results: List[dict],
    config: Optional[dict],
    *,
    date: Optional[str] = None,
    config_id: Optional[int] = None,
    persist: bool = True,
    max_items: Optional[int] = None,
) -> int:
    """
    对缺 structure 的选股结果增量计算成交量加权 KDE 支撑/阻力，展平到展示字段；
    可选回填 gms_signal_trace.score_detail.structure。
    返回实际补算条数。
    """
    if not results:
        return 0
    from .structure_levels import (
        compute_structure_levels,
        empty_structure,
        flatten_structure_to_result,
        kde_bars_limit,
    )

    need_idx = [i for i, r in enumerate(results) if result_needs_structure(r)]
    if max_items is not None and max_items >= 0 and need_idx:
        need_idx = need_idx[: int(max_items)]

    enriched = 0
    if need_idx:
        loader = GMSDataLoader(db)
        limit = kde_bars_limit(config)
        for i in need_idx:
            r = results[i]
            code = str(r.get("code") or r.get("symbol") or "").strip()
            if not code:
                continue
            mt = str(r.get("market_type") or _infer_market_type(code)).strip().upper() or "CN"
            end_d = str(r.get("date") or date or "").strip()[:10] or None
            try:
                bars = loader.load_bars(code, mt, end_date=end_d, limit=limit)
                px = None
                if bars:
                    try:
                        c0 = float(bars[0].get("close") or 0)
                        if c0 > 0:
                            px = c0
                    except (TypeError, ValueError):
                        px = None
                if px is None:
                    try:
                        d_val = r.get("d")
                        if d_val is not None:
                            px = float(d_val)
                    except (TypeError, ValueError):
                        px = None
                structure = compute_structure_levels(bars, config, price=px)
            except Exception as e:
                logger.warning("GMS structure 补算失败 %s: %s", code, e)
                structure = empty_structure()

            sd = dict(r.get("score_detail")) if isinstance(r.get("score_detail"), dict) else {}
            sd["structure"] = structure
            r["score_detail"] = sd
            flatten_structure_to_result(r, structure)
            enriched += 1
            if persist and config_id is not None and end_d:
                _persist_structure_to_trace(
                    db,
                    code=code,
                    date=end_d,
                    market_type=mt,
                    config_id=int(config_id),
                    structure=structure,
                )

        if enriched and persist and config_id is not None:
            try:
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.warning("GMS structure 回填 commit 失败 date=%s config_id=%s", date, config_id)
        if enriched:
            logger.info(
                "GMS structure 补算完成 enriched=%s/%s date=%s config_id=%s",
                enriched,
                len(need_idx),
                date,
                config_id,
            )

    # 旧 trace：structure 已展示但打分时未注入支撑/阻力 → 同步减分（含 poor_structure_rr）
    sync_penalties_with_structure(
        db,
        results,
        config,
        date=date,
        config_id=config_id,
        persist=persist,
    )
    return enriched


def _save_result_to_trace(db, result: dict, date: str, config_id: int) -> None:
    """
    将 engine.screen 单条结果完整写入 gms_signal_trace，便于后续优先读表。
    回测与选股均依赖此表：优先读 trace，缺失时增量计算并回填。
    使用 PostgreSQL ON CONFLICT UPSERT，避免并发预计算/选股回填时 UniqueViolation。
    单条失败用 SAVEPOINT 回滚，避免污染整批事务（PostgreSQL InFailedSqlTransaction）。
    """
    code = result.get("code") or result.get("symbol") or ""
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from backend_api.models import GMSSignalTrace

        market_type = result.get("market_type") or _infer_market_type(code)
        if not code:
            return
        code = str(code).strip()
        date = str(date).strip()[:10]
        market_type = str(market_type or "").strip()
        # PG JSON 不接受 NaN/Inf（常见于缺失 ma60_d 等浮点字段）
        sd = sanitize_for_pg_json(result.get("score_detail") or {})
        risk_tags = sanitize_for_pg_json(result.get("risk_tags"))
        values = {
            "code": code,
            "date": date,
            "market_type": market_type,
            "config_id": int(config_id),
            "score_total": result.get("score_total"),
            "score_accumulation": result.get("score_accumulation"),
            "score_momentum": result.get("score_momentum"),
            "signal_strength": result.get("signal_strength"),
            "buy_type": result.get("buy_type") or None,
            "left_buy_signal": result.get("left_buy_signal"),
            "right_buy_signal": result.get("right_buy_signal"),
            "sell_signal": result.get("sell_signal"),
            "accumulation_grade": result.get("accumulation_grade") or None,
            "momentum_grade": result.get("momentum_grade") or None,
            "delta": result.get("delta"),
            "d": result.get("d"),
            "ratio_d20": result.get("ratio_d20"),
            "ratio_d1": result.get("ratio_d1"),
            "fz_ratio": result.get("fz_ratio"),
            "volume_ratio": result.get("volume_ratio"),
            "instant_deviation": result.get("instant_deviation"),
            "rising_days": result.get("rising_days"),
            "falling_days": result.get("falling_days"),
            "score_acc_fz": sd.get("score_acc_fz"),
            "score_acc_balance": sd.get("score_acc_balance"),
            "score_acc_volume": sd.get("score_acc_volume"),
            "score_mom_ratio_d1": sd.get("score_mom_ratio_d1"),
            "score_mom_deviation": sd.get("score_mom_deviation"),
            "score_mom_volume": sd.get("score_mom_volume"),
            "acc_fz_judge": sd.get("acc_fz_judge") or None,
            "acc_balance_judge": sd.get("acc_balance_judge") or None,
            "acc_volume_judge": sd.get("acc_volume_judge") or None,
            "mom_ratio_d1_judge": sd.get("mom_ratio_d1_judge") or None,
            "mom_deviation_judge": sd.get("mom_deviation_judge") or None,
            "mom_volume_judge": sd.get("mom_volume_judge") or None,
            "created_at": datetime.now(),
            "risk_tags": risk_tags,
            "score_detail": sd,
        }
        stmt = pg_insert(GMSSignalTrace).values(**values)
        update_cols = {
            k: getattr(stmt.excluded, k)
            for k in values
            if k not in ("code", "date", "market_type", "config_id", "created_at")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "date", "market_type", "config_id"],
            set_=update_cols,
        )
        with db.begin_nested():
            db.execute(stmt)
            db.flush()
    except Exception as e:
        # begin_nested 失败或外层已 aborted：整事务回滚，保证后续股票可继续写
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("回填 gms_signal_trace 失败 %s: %s", code or result.get("code"), e)


class GMSFrontendInterface:
    """GMS 选股前端接口"""

    def __init__(
        self,
        db,
        config: Optional[dict] = None,
        config_id: Optional[int] = None,
    ):
        self.db = db
        self._mgr = GMSConfigManager()
        self.config_id = self._mgr.resolve_config_id(config_id)
        self.config = config or self._mgr.get_config(self.config_id)
        self.use_trace = self._mgr.should_use_trace(self.config_id)
        self.min_score = 0
        self.max_results = 10000

    def set_selection_config(
        self,
        min_score: float = 0,
        max_results: int = 10000,
    ):
        self.min_score = min_score
        self.max_results = max_results

    def _market_types_for_scope(self, market: str) -> List[str]:
        m = (market or "all").strip().lower()
        if m == "cn":
            return ["CN"]
        if m == "hk":
            return ["HK"]
        if m == "etf":
            return ["ETF"]
        return ["CN", "HK", "ETF"]

    def _precompute_succeeded(self, date: str, market: str) -> bool:
        """当日该 market/config 预计算是否已成功（用于跳过全市场建池）。"""
        try:
            from sqlalchemy import bindparam, text

            m = (market or "all").strip().lower()
            # 预计算任务按 cn/hk/all 记录；scope=all 时 cn/hk/all 任一成功且有量即可快读
            if m == "all":
                markets = ["cn", "hk", "all"]
            elif m in ("cn", "hk", "etf"):
                markets = [m]
            else:
                markets = ["all"]
            stmt = text(
                """
                SELECT status, stock_count
                FROM gms_precompute_runs
                WHERE config_id = :cid
                  AND trade_date = :d
                  AND market IN :markets
                  AND status = 'success'
                  AND COALESCE(stock_count, 0) > 0
                ORDER BY finished_at DESC NULLS LAST, started_at DESC
                LIMIT 1
                """
            ).bindparams(bindparam("markets", expanding=True))
            row = self.db.execute(
                stmt, {"cid": int(self.config_id), "d": date, "markets": markets}
            ).first()
            return bool(row)
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            return False

    def _load_traces_for_market(self, date: str, market: str) -> List[dict]:
        """直接按日+配置+市场读 gms_signal_trace，避免先建全市场股票池再巨型 IN。"""
        from backend_api.models import GMSSignalTrace

        mts = self._market_types_for_scope(market)
        rows = (
            self.db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.date == date,
                GMSSignalTrace.config_id == self.config_id,
                GMSSignalTrace.market_type.in_(mts),
                GMSSignalTrace.score_total.isnot(None),
            )
            .all()
        )
        out: List[dict] = []
        seen = set()
        for row in rows:
            key = (str(row.code).strip(), str(row.market_type or "").strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(_trace_row_to_result(row))
        return out

    def get_selection_results(
        self,
        date: Optional[str] = None,
        stock_pool: Optional[List[str]] = None,
        market: str = "all",
        trace_only: bool = False,
        return_meta: bool = False,
        exclude_st: bool = False,
        cn_board_segment: Optional[str] = None,
    ) -> Union[List[dict], Tuple[List[dict], Dict[str, Any]]]:
        """
        获取选股结果。优先从 gms_signal_trace 表读取策略信号记录；
        若不存在或缺失，则增量重新计算，结果回填写入 gms_signal_trace 后返回。

        Args:
            trace_only: 为 True 时只读库内 trace，不对缺失股票做实时计算（用于前端先快速展示缓存）。
            return_meta: 为 True 时返回 (列表, 统计字典)，便于接口返回 trace_complete 等字段。
            exclude_st: 为 True 时剔除 A 股 ST 类股票（名称含 ST）。
            cn_board_segment: A 股板块 MAIN/CYB/SZ_SME/KCB/BJ；仅过滤 A 股代码，港股/ETF 保留。
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        date = str(date).strip()[:10]

        # 快路径：无显式股票池且允许读 trace 时，直接按市场读表。
        # 预计算已成功或 trace_only 时跳过 historical_quotes DISTINCT 建池（全 A 最重）。
        if stock_pool is None and self.use_trace:
            fast_traces = self._load_traces_for_market(date, market)
            if cn_board_segment:
                from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

                allowed = set(
                    filter_stock_codes_by_board_segment(
                        [str(r.get("symbol") or "") for r in fast_traces],
                        cn_board_segment,
                    )
                )
                fast_traces = [
                    r
                    for r in fast_traces
                    if str(r.get("market_type") or "").upper() != "CN"
                    or str(r.get("symbol") or "") in allowed
                ]
            if exclude_st and fast_traces:
                from backend_api.utils.st_stock_filter import filter_codes_exclude_st

                kept = set(
                    filter_codes_exclude_st(
                        self.db, [str(r.get("symbol") or "") for r in fast_traces]
                    )
                )
                fast_traces = [r for r in fast_traces if str(r.get("symbol") or "") in kept]

            precompute_ok = self._precompute_succeeded(date, market)
            # 有足够缓存且（预计算成功 或 仅读缓存）→ 不再建池/补算
            if fast_traces and (trace_only or precompute_ok):
                combined = fast_traces
                if self.min_score > 0:
                    combined = [
                        r for r in combined if (r.get("score_total") or 0) >= self.min_score
                    ]
                if self.max_results and len(combined) > self.max_results:
                    combined = sorted(
                        combined, key=lambda x: -(x.get("score_total") or 0)
                    )[: self.max_results]
                meta: Dict[str, Any] = enrich_trace_meta(
                    {
                        "from_trace_count": len(fast_traces),
                        "computed_count": 0,
                        "requested_count": len(fast_traces),
                        "trace_complete": bool(precompute_ok) or bool(trace_only and fast_traces),
                        "config_id": self.config_id,
                        "use_trace": True,
                        "batch_size": _GMS_BATCH_SIZE,
                        "fast_path": "trace_market",
                        "precompute_ok": precompute_ok,
                    }
                )
                # trace_only 且预计算未确认时：不谎称 complete，便于前端决定是否二次请求
                if trace_only and not precompute_ok:
                    meta["trace_complete"] = False
                    meta = enrich_trace_meta(meta)
                logger.info(
                    "GMS 快路径读 trace date=%s market=%s rows=%s precompute_ok=%s trace_only=%s",
                    date,
                    market,
                    len(fast_traces),
                    precompute_ok,
                    trace_only,
                )
                # 旧 trace 无 structure：增量补算（全市场有上限，避免拖垮超时；单股/小池在调用方再兜底）
                _max_st = None
                if len(combined) > 300:
                    _max_st = int(os.getenv("GMS_STRUCTURE_ENRICH_MAX", "300"))
                enrich_results_with_structure(
                    self.db,
                    combined,
                    self.config,
                    date=date,
                    config_id=self.config_id,
                    persist=bool(self.use_trace),
                    max_items=_max_st,
                )
                return (combined, meta) if return_meta else combined

        if stock_pool is None:
            stock_pool = self._get_stock_pool(date, market)
        else:
            stock_pool = list(dict.fromkeys(stock_pool))

        if cn_board_segment:
            from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

            stock_pool = filter_stock_codes_by_board_segment(stock_pool, cn_board_segment)

        if exclude_st and stock_pool:
            from backend_api.utils.st_stock_filter import filter_codes_exclude_st

            before = len(stock_pool)
            stock_pool = filter_codes_exclude_st(self.db, stock_pool)
            if before != len(stock_pool):
                logger.info(
                    "GMS 剔除 ST 相关股: %s -> %s 只",
                    before,
                    len(stock_pool),
                )

        if not stock_pool:
            empty_meta = {
                "from_trace_count": 0,
                "computed_count": 0,
                "requested_count": 0,
                "trace_complete": True,
            }
            return ([], empty_meta) if return_meta else []

        # 按市场过滤：只保留当前 market 下的代码
        requested: List[Tuple[str, str]] = []
        for code in stock_pool:
            mt = _infer_market_type(code)
            if market == "all":
                requested.append((code, mt))
            elif market == "cn" and mt == "CN":
                requested.append((code, mt))
            elif market == "hk" and mt == "HK":
                requested.append((code, mt))
            elif market == "etf" and mt == "ETF":
                requested.append((code, mt))

        if not requested:
            empty_meta = {
                "from_trace_count": 0,
                "computed_count": 0,
                "requested_count": 0,
                "trace_complete": True,
            }
            return ([], empty_meta) if return_meta else []

        # 1) 先从 gms_signal_trace 读取已有记录（单次查询）
        from backend_api.models import GMSSignalTrace

        uniq_requested = list(dict.fromkeys(requested))
        codes_in = [str(c).strip() for c, _ in uniq_requested]
        mts_in = list({str(mt or "").strip() for _, mt in uniq_requested})
        from_trace: List[dict] = []
        have_keys = set()
        if self.use_trace:
            rows = (
                self.db.query(GMSSignalTrace)
                .filter(
                    GMSSignalTrace.date == date,
                    GMSSignalTrace.code.in_(codes_in),
                    GMSSignalTrace.market_type.in_(mts_in),
                    GMSSignalTrace.config_id == self.config_id,
                )
                .all()
            )
            # 统一用字符串 (code, market_type) 做 key，避免 DB 返回 int 导致 603667 与 "603667" 对不上
            def _key(c, mt):
                return (str(c).strip(), str(mt or "").strip())
            for row in rows:
                if row.score_total is None:
                    continue
                key = _key(row.code, row.market_type)
                if key in have_keys:
                    continue
                have_keys.add(key)
                from_trace.append(_trace_row_to_result(row))
        else:
            def _key(c, mt):
                return (str(c).strip(), str(mt or "").strip())

        missing = [(code, mt) for code, mt in uniq_requested if _key(code, mt) not in have_keys]
        computed: List[dict] = []
        if missing and not trace_only:
            loader = GMSDataLoader(self.db)
            engine = GMSStrategyEngine(loader, self.config)
            missing_cn = [c for c, mt in missing if mt == "CN"]
            missing_etf = [c for c, mt in missing if mt == "ETF"]
            missing_hk = [c for c, mt in missing if mt == "HK"]
            # 大批量股票池时每 100 只一批计算并打印进度，避免长时间无日志
            batch_size = _GMS_BATCH_SIZE
            pool_label = {"CN": "全部A股", "ETF": "全部ETF", "HK": "全部港股"}
            for codes_sub, mt in [(missing_cn, "CN"), (missing_etf, "ETF"), (missing_hk, "HK")]:
                if not codes_sub:
                    continue
                total_missing = len(codes_sub)
                label = pool_label.get(mt, mt)
                for start in range(0, total_missing, batch_size):
                    chunk = codes_sub[start : start + batch_size]
                    done = min(start + len(chunk), total_missing)
                    try:
                        sub = engine.screen(
                            codes=chunk,
                            date=date,
                            market=mt,
                            config=self.config,
                            min_score=0,
                            max_results=self.max_results,
                        )
                        for r in sub:
                            computed.append(r)
                            if self.use_trace:
                                _save_result_to_trace(self.db, r, date, self.config_id)
                        logger.info(
                            "GMS 策略信号计算进度 %s(%s) %s：已完成 %d/%d 只",
                            label,
                            mt,
                            date,
                            done,
                            total_missing,
                        )
                    except Exception as e:
                        logger.warning(
                            "GMS 选股计算失败 %s %s 批次 %d-%d: %s",
                            date,
                            mt,
                            start + 1,
                            done,
                            e,
                        )
                        # 发生 DB 异常后当前事务会进入 failed 状态，需回滚后再继续后续批次
                        try:
                            self.db.rollback()
                        except Exception:
                            pass
            if computed:
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()

        # 3) 合并结果，按 min_score 过滤
        combined = from_trace + computed
        if self.min_score > 0:
            combined = [r for r in combined if (r.get("score_total") or 0) >= self.min_score]
        if self.max_results and len(combined) > self.max_results:
            combined = sorted(combined, key=lambda x: -(x.get("score_total") or 0))[: self.max_results]

        # 4) 旧 trace 缺 structure 时补算 KDE（显式股票池不设上限；全市场有上限）
        _max_st = None
        if len(uniq_requested) > 300 and len(combined) > 300:
            _max_st = int(os.getenv("GMS_STRUCTURE_ENRICH_MAX", "300"))
        enrich_results_with_structure(
            self.db,
            combined,
            self.config,
            date=date,
            config_id=self.config_id,
            persist=bool(self.use_trace),
            max_items=_max_st,
        )

        meta: Dict[str, Any] = enrich_trace_meta(
            {
                "from_trace_count": len(from_trace),
                "computed_count": len(computed),
                "requested_count": len(uniq_requested),
                "trace_complete": len(missing) == 0,
                "config_id": self.config_id,
                "use_trace": self.use_trace,
                "batch_size": _GMS_BATCH_SIZE,
            }
        )
        if return_meta:
            return combined, meta
        return combined

    def _get_stock_pool(self, date: str, market: str) -> List[str]:
        """
        按当日采集行情获取股票池（非基本信息表全量）：
        - cn：historical_quotes 在基准日的 DISTINCT code
        - hk：historical_quotes_hk
        - etf：fund_historical_quotes
        - all：三者并集
        基准日优先使用请求 date；若该日尚无采集则回退至对应行情表最新有数据交易日。
        """
        try:
            from backend_api.models import FundHistoricalQuotes, HistoricalQuotes, HistoricalQuotesHK

            req_date = str(date).strip()[:10]

            if market == "cn":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotes)
                codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotes, eff, _normalize_cn_pool_code
                )
                logger.info("GMS 股票池(全部A股, %s): %s 只", eff, len(codes))
                return codes

            if market == "hk":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotesHK)
                codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotesHK, eff, _normalize_hk_pool_code
                )
                logger.info("GMS 股票池(全部港股, %s): %s 只", eff, len(codes))
                return codes

            if market == "etf":
                eff = _resolve_pool_date_for_quotes(self.db, req_date, FundHistoricalQuotes)
                codes = _distinct_codes_from_quotes(
                    self.db, FundHistoricalQuotes, eff, _normalize_etf_pool_code
                )
                logger.info("GMS 股票池(全部ETF, %s): %s 只", eff, len(codes))
                return codes

            if market == "all":
                eff_cn = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotes)
                cn_codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotes, eff_cn, _normalize_cn_pool_code
                )
                eff_hk = _resolve_pool_date_for_quotes(self.db, req_date, HistoricalQuotesHK)
                hk_codes = _distinct_codes_from_quotes(
                    self.db, HistoricalQuotesHK, eff_hk, _normalize_hk_pool_code
                )
                eff_etf = _resolve_pool_date_for_quotes(self.db, req_date, FundHistoricalQuotes)
                etf_codes = _distinct_codes_from_quotes(
                    self.db, FundHistoricalQuotes, eff_etf, _normalize_etf_pool_code
                )
                codes = cn_codes + etf_codes + hk_codes
                logger.info(
                    "GMS 股票池(全部A+ETF+港股, 请求日=%s): %s 只 [A股 %s@%s, ETF %s@%s, 港股 %s@%s]",
                    req_date,
                    len(codes),
                    len(cn_codes),
                    eff_cn,
                    len(etf_codes),
                    eff_etf,
                    len(hk_codes),
                    eff_hk,
                )
                return codes

            return []
        except Exception as e:
            logger.error(f"GMS 获取股票池失败: {e}", exc_info=True)
            return []
