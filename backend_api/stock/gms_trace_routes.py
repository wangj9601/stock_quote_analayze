"""
GMS 信号追溯 API 路由
提供单只股票从指标表首日到最新日的 GMS 策略信号追溯记录
"""

import logging
import threading
import uuid
from copy import deepcopy
from typing import Optional, List, Dict, Callable
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend_api.database import get_db
from backend_api.models import GMSSignalTrace, MeanFrequencyResonanceIndicators

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["GMS信号追溯"])

# 强制重新计算：内存任务状态（单进程内有效）
_trace_recompute_lock = threading.Lock()
_trace_recompute_tasks: Dict[str, dict] = {}


def _find_running_trace_recompute(code: str, config_id: int) -> Optional[str]:
    with _trace_recompute_lock:
        for tid, task in _trace_recompute_tasks.items():
            if (
                task.get("status") == "running"
                and task.get("code") == code
                and int(task.get("config_id") or 0) == int(config_id)
            ):
                return tid
    return None


def _update_trace_recompute_task(task_id: str, **fields) -> None:
    with _trace_recompute_lock:
        if task_id in _trace_recompute_tasks:
            _trace_recompute_tasks[task_id].update(fields)


def _get_trace_recompute_task(task_id: str) -> Optional[dict]:
    with _trace_recompute_lock:
        task = _trace_recompute_tasks.get(task_id)
        return dict(task) if task else None


class GmsTraceRecomputeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    config_id: Optional[int] = Field(None, ge=1, description="GMS 策略参数版本 ID")


def _run_trace_recompute_background(
    task_id: str,
    code: str,
    market_type: str,
    config_id: int,
    config: dict,
    config_display: str,
) -> None:
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        _update_trace_recompute_task(task_id, status="running", message="正在清除旧记录…", progress=0)

        db.query(GMSSignalTrace).filter(
            GMSSignalTrace.code == code,
            GMSSignalTrace.market_type == market_type,
            GMSSignalTrace.config_id == config_id,
        ).delete(synchronize_session=False)
        db.commit()

        def progress_cb(current: int, total: int, msg: str) -> None:
            pct = int(round(current * 100 / total)) if total else 0
            _update_trace_recompute_task(
                task_id,
                progress=min(99, pct),
                message=msg,
                current=current,
                total=total,
            )

        count = _compute_gms_trace_for_stock(
            db, code, market_type, config, config_id, progress_cb=progress_cb
        )
        _update_trace_recompute_task(
            task_id,
            status="completed",
            progress=100,
            saved_count=count,
            message=f"已按「{config_display}」重新计算，写入 {count} 条",
        )
        logger.info("GMS 追溯异步重算完成: %s config_id=%s, 写入 %s 条", code, config_id, count)
    except Exception as e:
        logger.exception("GMS 追溯异步重算失败 task_id=%s", task_id)
        _update_trace_recompute_task(
            task_id,
            status="failed",
            error=str(e),
            message=f"计算失败: {e}",
        )
    finally:
        db.close()


def _merge_mfr_d1_d20_into_trace_dict(db: Session, row_dict: dict) -> dict:
    """从 mean_frequency_resonance_indicators 合并 d1、d20、成交量及 bias(均线乖离 Δ₂₀/d) 等，供前端「计算指标细项」展示。

    trace 表与 to_dict 不含 avg_volume_20d / current_volume / ratio_d，必须与筛选页一致从指标行带出。
    """
    code = row_dict.get("code")
    date_str = str(row_dict.get("date", ""))[:10]
    market_type = row_dict.get("market_type", "CN")
    if not code or not date_str:
        return row_dict
    row = (
        db.query(MeanFrequencyResonanceIndicators)
        .filter(
            MeanFrequencyResonanceIndicators.code == code,
            MeanFrequencyResonanceIndicators.market_type == market_type,
            MeanFrequencyResonanceIndicators.date == date_str,
        )
        .first()
    )
    if not row:
        return row_dict

    out = dict(row_dict)

    def _norm_date(v):
        if v is None:
            return None
        s = str(v).strip()
        return s[:10] if len(s) >= 10 else s

    if getattr(row, "d1", None) is not None:
        try:
            out["d1"] = float(row.d1)
        except (TypeError, ValueError):
            pass
    if getattr(row, "d20", None) is not None:
        try:
            out["d20"] = float(row.d20)
        except (TypeError, ValueError):
            pass
    vd = getattr(row, "d1_date", None)
    if vd is not None:
        out["d1_date"] = _norm_date(vd)
    vd = getattr(row, "d20_date", None)
    if vd is not None:
        out["d20_date"] = _norm_date(vd)

    mavol20_m = getattr(row, "mavol20_m", None)
    eff_m20_m = getattr(row, "efficiency_m20_minus_m", None)
    if mavol20_m is not None:
        try:
            out["avg_volume_20d"] = float(mavol20_m)
            out["current_volume"] = float(mavol20_m or 0) + float(eff_m20_m or 0)
        except (TypeError, ValueError):
            pass
    bias = getattr(row, "bias", None)
    if bias is not None:
        try:
            out["ratio_d"] = float(bias)
        except (TypeError, ValueError):
            pass
    ma60_d = getattr(row, "ma60_d", None)
    if ma60_d is not None:
        try:
            out["ma60_d"] = float(ma60_d)
        except (TypeError, ValueError):
            pass
    return out


def _calculator_score_detail_meta(config: dict) -> dict:
    """从 GMSIndicatorsCalculator 提取权重/阈值等，供得分明细展示。"""
    from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator

    calc = GMSIndicatorsCalculator(config)
    return {
        "accumulation_fz_min": calc.accumulation_fz_min,
        "balance_ratio_max": calc.balance_ratio_max,
        "momentum_volume_ratio_min": calc.momentum_volume_ratio_min,
        "accumulation_s_threshold": calc.acc_s_threshold,
        "accumulation_a_threshold": calc.acc_a_threshold,
        "momentum_full_threshold": calc.mom_full_threshold,
        "momentum_batch_threshold": calc.mom_batch_threshold,
        "acc_fz_tiers": calc.acc_fz_tiers,
        "balance_tiers": calc.balance_tiers,
        "vol_shrink_tiers": calc.vol_shrink_tiers,
        "ratio_d1_tiers": calc.ratio_d1_tiers,
        "vol_attack_tiers": calc.vol_attack_tiers,
        "weight_acc_fz": calc.weight_acc_fz,
        "weight_acc_balance": calc.weight_acc_balance,
        "weight_acc_volume": calc.weight_acc_volume,
        "weight_mom_ratio_d1": calc.weight_mom_ratio_d1,
        "weight_mom_deviation": calc.weight_mom_deviation,
        "weight_mom_volume": calc.weight_mom_volume,
    }


def _row_dict_to_score_detail(row_dict: dict, calc_meta: dict, config: dict) -> dict:
    """将 trace 扁平行 + 计算器参数组装为与选股页一致的 score_detail。"""
    mechanism = (config.get("scoring") or {}).get("mechanism") or "tiered_dual_max"
    acc = row_dict.get("score_accumulation")
    mom = row_dict.get("score_momentum")
    base_total = max(float(acc or 0), float(mom or 0)) if acc is not None or mom is not None else None
    sd = {
        "score_accumulation": row_dict.get("score_accumulation"),
        "score_momentum": row_dict.get("score_momentum"),
        "score_total": row_dict.get("score_total"),
        "accumulation_grade": row_dict.get("accumulation_grade") or "",
        "momentum_grade": row_dict.get("momentum_grade") or "",
        "score_acc_fz": row_dict.get("score_acc_fz"),
        "score_acc_balance": row_dict.get("score_acc_balance"),
        "score_acc_volume": row_dict.get("score_acc_volume"),
        "score_mom_ratio_d1": row_dict.get("score_mom_ratio_d1"),
        "score_mom_deviation": row_dict.get("score_mom_deviation"),
        "score_mom_volume": row_dict.get("score_mom_volume"),
        "acc_fz_judge": row_dict.get("acc_fz_judge") or "",
        "acc_balance_judge": row_dict.get("acc_balance_judge") or "",
        "acc_volume_judge": row_dict.get("acc_volume_judge") or "",
        "mom_ratio_d1_judge": row_dict.get("mom_ratio_d1_judge") or "",
        "mom_deviation_judge": row_dict.get("mom_deviation_judge") or "",
        "mom_volume_judge": row_dict.get("mom_volume_judge") or "",
        "delta": row_dict.get("delta"),
        "d": row_dict.get("d"),
        "d1": row_dict.get("d1"),
        "d20": row_dict.get("d20"),
        "d1_date": row_dict.get("d1_date"),
        "d20_date": row_dict.get("d20_date"),
        "ratio_d20": row_dict.get("ratio_d20"),
        "ratio_d1": row_dict.get("ratio_d1"),
        "ratio_d": row_dict.get("ratio_d"),
        "rising_days": row_dict.get("rising_days"),
        "falling_days": row_dict.get("falling_days"),
        "avg_volume_20d": row_dict.get("avg_volume_20d"),
        "current_volume": row_dict.get("current_volume"),
        "volume_ratio": row_dict.get("volume_ratio"),
        "fz_ratio": row_dict.get("fz_ratio"),
        "instant_deviation": row_dict.get("instant_deviation"),
        "ma60_d": row_dict.get("ma60_d"),
        "scoring_mechanism": mechanism,
        "score_base_total": base_total,
        "score_penalty_deduction": row_dict.get("score_penalty_deduction"),
        "penalties": row_dict.get("penalties") if isinstance(row_dict.get("penalties"), list) else [],
    }
    sd.update(calc_meta)
    return sd


def _attach_trace_score_detail(
    db: Session,
    row_dict: dict,
    config: dict,
    gms_config_meta: dict,
    calc_meta: dict,
) -> dict:
    """为追溯行附加完整 score_detail（与 GMS 选股页一致）。"""
    from backend_api.stock.stock_screening_routes import (
        _fill_gms_score_fallback,
        _inject_gms_score_detail_meta,
    )

    out = dict(row_dict)
    mechanism = (config.get("scoring") or {}).get("mechanism") or "tiered_dual_max"
    code = out.get("code")
    date_str = str(out.get("date", ""))[:10]
    market_type = out.get("market_type", "CN")

    need_fallback = (
        out.get("ma60_d") is None
        or out.get("ratio_d") is None
        or out.get("avg_volume_20d") is None
        or out.get("current_volume") is None
        or (mechanism == "tiered_dual_penalty" and out.get("score_penalty_deduction") is None)
    )
    score_detail = _row_dict_to_score_detail(out, calc_meta, config)
    if need_fallback and code and date_str:
        fb = _fill_gms_score_fallback(db, code, date_str, market_type, config)
        if fb and isinstance(fb.get("score_detail"), dict):
            fb_sd = fb["score_detail"]
            for k, v in fb_sd.items():
                if score_detail.get(k) in (None, "") and v is not None:
                    score_detail[k] = v
            if score_detail.get("score_penalty_deduction") is None:
                score_detail["score_penalty_deduction"] = fb_sd.get("score_penalty_deduction", 0.0)
            if not score_detail.get("penalties") and fb_sd.get("penalties"):
                score_detail["penalties"] = fb_sd["penalties"]
            if score_detail.get("score_base_total") is None and fb_sd.get("score_base_total") is not None:
                score_detail["score_base_total"] = fb_sd["score_base_total"]

    score_detail = _inject_gms_score_detail_meta(score_detail, gms_config_meta)
    out["score_detail"] = score_detail
    return out

try:
    from backend_core.strategies.gms.data_loader import GMSDataLoader
    from backend_core.strategies.gms.strategy_engine import GMSStrategyEngine
    from backend_core.strategies.gms.config import GMSConfigManager
    GMS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GMS 模块导入失败: {e}")
    GMS_AVAILABLE = False


def _enrich_trace_row_score_detail(db: Session, row_dict: dict, config: dict) -> dict:
    """
    当 trace 记录的得分明细或计算指标为空时，从指标表重新计算并补全。
    用于兼容迁移前写入的历史数据。
    """
    code = row_dict.get("code")
    date_str = str(row_dict.get("date", ""))[:10]
    market_type = row_dict.get("market_type", "CN")
    if not code or not date_str:
        return row_dict
    # 若已有完整得分明细则跳过
    if row_dict.get("score_acc_fz") is not None and row_dict.get("d") is not None:
        return row_dict
    try:
        from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator

        row = (
            db.query(MeanFrequencyResonanceIndicators)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date == date_str,
            )
            .first()
        )
        if not row:
            return row_dict

        delta = getattr(row, "macro_displacement_delta", None)
        d = getattr(row, "ma20_d", None)
        mavol20_m = getattr(row, "mavol20_m", None)
        eff_m20_m = getattr(row, "efficiency_m20_minus_m", None)
        current_volume = (float(mavol20_m or 0) + float(eff_m20_m or 0)) if mavol20_m is not None else 0.0
        volume_ratio = (current_volume / float(mavol20_m)) if mavol20_m not in (None, 0) else None
        calc_row = {
            "code": code,
            "date": date_str,
            "market_type": market_type,
            "macro_displacement_delta": delta,
            "ma20_d": d,
            "ratio_d20": getattr(row, "ratio_d20", None),
            "ratio_d1": getattr(row, "ratio_d1", None),
            "instant_deviation": getattr(row, "instant_deviation", None),
            "rising_days_z": getattr(row, "rising_days_z", 0),
            "falling_days_f": getattr(row, "falling_days_f", 0),
            "mavol20_m": mavol20_m,
            "efficiency_m20_minus_m": eff_m20_m,
            "ratio_d": getattr(row, "bias", None),
            "current_volume": current_volume,
            "volume_ratio": volume_ratio,
            "d1": getattr(row, "d1", None),
            "d1_date": getattr(row, "d1_date", None),
            "d20": getattr(row, "d20", None),
            "d20_date": getattr(row, "d20_date", None),
        }
        stable_days = int(config.get("scoring", {}).get("instant_deviation_stable_days", 3) or 3)
        series_rows = (
            db.query(MeanFrequencyResonanceIndicators.instant_deviation)
            .filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date <= date_str,
            )
            .order_by(MeanFrequencyResonanceIndicators.date.desc())
            .limit(max(1, stable_days))
            .all()
        )
        series = [float(r[0]) for r in reversed(series_rows) if r and r[0] is not None]
        ind = GMSIndicatorsCalculator(config).calculate(calc_row, instant_deviation_series=series if series else None)
        if not ind:
            return row_dict

        # 补全得分明细与计算指标
        out = dict(row_dict)
        if out.get("score_acc_fz") is None:
            out["score_acc_fz"] = getattr(ind, "score_acc_fz", None)
            out["score_acc_balance"] = getattr(ind, "score_acc_balance", None)
            out["score_acc_volume"] = getattr(ind, "score_acc_volume", None)
            out["acc_fz_judge"] = getattr(ind, "acc_fz_judge", None) or ""
            out["acc_balance_judge"] = getattr(ind, "acc_balance_judge", None) or ""
            out["acc_volume_judge"] = getattr(ind, "acc_volume_judge", None) or ""
        if out.get("score_mom_ratio_d1") is None:
            out["score_mom_ratio_d1"] = getattr(ind, "score_mom_ratio_d1", None)
            out["score_mom_deviation"] = getattr(ind, "score_mom_deviation", None)
            out["score_mom_volume"] = getattr(ind, "score_mom_volume", None)
            out["mom_ratio_d1_judge"] = getattr(ind, "mom_ratio_d1_judge", None) or ""
            out["mom_deviation_judge"] = getattr(ind, "mom_deviation_judge", None) or ""
            out["mom_volume_judge"] = getattr(ind, "mom_volume_judge", None) or ""
        if out.get("delta") is None:
            out["delta"] = ind.delta
            out["d"] = ind.d
            out["ratio_d20"] = ind.ratio_d20
            out["ratio_d1"] = ind.ratio_d1
            out["fz_ratio"] = ind.fz_ratio
            out["volume_ratio"] = ind.volume_ratio
            out["instant_deviation"] = ind.instant_deviation
            out["rising_days"] = ind.rising_days
            out["falling_days"] = ind.falling_days
        if out.get("score_accumulation") is None:
            out["score_accumulation"] = ind.score_accumulation
        if out.get("score_momentum") is None:
            out["score_momentum"] = ind.score_momentum
        if out.get("score_total") is None:
            out["score_total"] = ind.score_total
        if out.get("accumulation_grade") in (None, ""):
            out["accumulation_grade"] = getattr(ind, "accumulation_grade", "") or ""
        if out.get("momentum_grade") in (None, ""):
            out["momentum_grade"] = getattr(ind, "momentum_grade", "") or ""
        if (out.get("signal_strength") is None or out.get("signal_strength") == 0) and ind.score_total and ind.score_total > 0:
            out["signal_strength"] = ind.score_total / 100.0
        return out
    except Exception as e:
        logger.debug("GMS 追溯 enrichment 失败 %s %s: %s", code, date_str, e)
        return row_dict


def _normalize_code(code: str, market_type: str) -> str:
    """港股代码 5 位补零"""
    s = str(code).strip()
    if market_type == "HK" and len(s) < 5 and s.isdigit():
        return s.zfill(5)
    return s


def _infer_market_type(code: str) -> str:
    """按代码规则推断市场：A股/CN、ETF、港股/HK。"""
    s = str(code).strip()
    if len(s) >= 6 and s.isdigit() and s[0] in "6039":
        return "CN"
    if len(s) >= 6 and s.isdigit() and s[0] in "518":
        return "ETF"
    return "HK"


def _config_display_name(row) -> str:
    if not row:
        return "未知版本"
    label = (getattr(row, "version_label", None) or "").strip()
    name = (getattr(row, "name", None) or "").strip()
    if label and name and label != name:
        return f"{name} · {label}"
    return label or name or f"配置#{getattr(row, 'id', '?')}"


def _list_stock_trace_config_options(db: Session, code: str, market_type: str) -> List[dict]:
    """策略版本标签：canonical 版本始终展示；record_count 来自该股票 trace 表。"""
    count_rows = (
        db.query(GMSSignalTrace.config_id, func.count(GMSSignalTrace.date))
        .filter(
            GMSSignalTrace.code == code,
            GMSSignalTrace.market_type == market_type,
        )
        .group_by(GMSSignalTrace.config_id)
        .all()
    )
    counts: Dict[int, int] = {int(cid): int(cnt or 0) for cid, cnt in count_rows}
    mgr = GMSConfigManager()
    merged: Dict[int, dict] = {}

    def _append_option(cid: int, row, *, is_default: bool = False, mechanism_label: str = "") -> None:
        merged[cid] = {
            "config_id": cid,
            "name": getattr(row, "name", None) or str(cid),
            "version_label": getattr(row, "version_label", None) or "",
            "display_name": _config_display_name(row),
            "is_default": is_default or bool(getattr(row, "is_default", False)),
            "record_count": counts.get(cid, 0),
            "scoring_mechanism_label": mechanism_label or "",
        }

    for meta in mgr.list_canonical_configs(active_only=True):
        cid = int(meta["id"])
        row = mgr.get_config_row(cid)
        _append_option(
            cid,
            row,
            is_default=bool(meta.get("is_default")),
            mechanism_label=str(meta.get("scoring_mechanism_label") or ""),
        )

    for cid, cnt in counts.items():
        if cid in merged:
            merged[cid]["record_count"] = cnt
            continue
        row = mgr.get_config_row(cid)
        _append_option(cid, row)

    options = list(merged.values())
    options.sort(key=lambda x: (0 if x.get("is_default") else 1, x["config_id"]))
    return options


def _resolve_trace_config_id(
    db: Session,
    code: str,
    market_type: str,
    requested_config_id: Optional[int],
) -> int:
    mgr = GMSConfigManager()
    if requested_config_id is not None:
        cid = mgr.resolve_config_id(requested_config_id)
        row = mgr.get_config_row(cid)
        if not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        if not row.is_active:
            raise HTTPException(status_code=400, detail="策略参数版本已禁用")
        return cid
    options = _list_stock_trace_config_options(db, code, market_type)
    if options:
        for opt in options:
            if opt.get("is_default"):
                return int(opt["config_id"])
        return int(options[0]["config_id"])
    return mgr.resolve_config_id(None)


def _compute_gms_trace_for_stock(
    db: Session,
    code: str,
    market_type: str,
    config: dict,
    config_id: int,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    """
    对单只股票从 mean_frequency_resonance_indicators 的首日到最新日执行 GMS 追溯计算，
    并写入 gms_signal_trace 表（指定 config_id）。
    返回写入条数。
    """
    if not GMS_AVAILABLE:
        raise RuntimeError("GMS 策略模块不可用")

    # 查询该股票所有日期（升序）
    rows = (
        db.query(MeanFrequencyResonanceIndicators.date)
        .filter(
            MeanFrequencyResonanceIndicators.code == code,
            MeanFrequencyResonanceIndicators.market_type == market_type,
        )
        .order_by(MeanFrequencyResonanceIndicators.date.asc())
        .all()
    )
    dates = [str(r.date)[:10] for r in rows if r.date]
    if not dates:
        return 0

    total_dates = len(dates)
    loader = GMSDataLoader(db)
    engine = GMSStrategyEngine(loader, config)
    stable_days = int(config.get("scoring", {}).get("instant_deviation_stable_days", 3))
    codes = [code]
    saved = 0

    for i, target_date in enumerate(dates):
        if progress_cb:
            progress_cb(i + 1, total_dates, f"正在计算 {target_date}（{i + 1}/{total_dates}）")
        try:
            # 加载当日指标（精确日期，不用 use_latest）
            rows_data = loader.load_indicators(codes, target_date, market_type, use_latest_per_stock=False)
            if not rows_data:
                continue

            # 加载多日序列（用于站稳3日）
            dev_series_by_code = {}
            if stable_days > 1:
                multi_rows = loader.load_indicators_multi_day(codes, target_date, market_type, days=stable_days)
                by_code = defaultdict(list)
                for r in multi_rows:
                    by_code[r["code"]].append(r)
                for c, code_rows in by_code.items():
                    code_rows.sort(key=lambda x: x["date"])
                    recent = code_rows[-stable_days:]
                    dev_series_by_code[c] = [float(r.get("instant_deviation", 0) or 0) for r in recent]

            row = rows_data[0]
            dev_series = dev_series_by_code.get(code)
            ind = engine.calculator.calculate(row, instant_deviation_series=dev_series)
            if ind is None:
                continue

            left = engine.detector.detect_left_buy(ind)
            right = engine.detector.detect_right_buy(ind)
            sell = engine.detector.detect_sell(ind)
            buy_type = "左侧" if left else ("右侧" if right else "")
            signal_strength = (ind.score_total / 100.0) if ind.score_total and ind.score_total > 0 else 0.0

            rec = GMSSignalTrace(
                code=code,
                date=target_date,
                market_type=market_type,
                config_id=int(config_id),
                score_total=ind.score_total,
                score_accumulation=ind.score_accumulation,
                score_momentum=ind.score_momentum,
                signal_strength=signal_strength,
                buy_type=buy_type or None,
                left_buy_signal=left,
                right_buy_signal=right,
                sell_signal=sell,
                accumulation_grade=getattr(ind, "accumulation_grade", "") or None,
                momentum_grade=getattr(ind, "momentum_grade", "") or None,
                delta=ind.delta,
                d=ind.d,
                ratio_d20=ind.ratio_d20,
                ratio_d1=ind.ratio_d1,
                fz_ratio=ind.fz_ratio,
                volume_ratio=ind.volume_ratio,
                instant_deviation=ind.instant_deviation,
                rising_days=ind.rising_days,
                falling_days=ind.falling_days,
                score_acc_fz=getattr(ind, "score_acc_fz", None),
                score_acc_balance=getattr(ind, "score_acc_balance", None),
                score_acc_volume=getattr(ind, "score_acc_volume", None),
                score_mom_ratio_d1=getattr(ind, "score_mom_ratio_d1", None),
                score_mom_deviation=getattr(ind, "score_mom_deviation", None),
                score_mom_volume=getattr(ind, "score_mom_volume", None),
                acc_fz_judge=getattr(ind, "acc_fz_judge", None) or None,
                acc_balance_judge=getattr(ind, "acc_balance_judge", None) or None,
                acc_volume_judge=getattr(ind, "acc_volume_judge", None) or None,
                mom_ratio_d1_judge=getattr(ind, "mom_ratio_d1_judge", None) or None,
                mom_deviation_judge=getattr(ind, "mom_deviation_judge", None) or None,
                mom_volume_judge=getattr(ind, "mom_volume_judge", None) or None,
            )
            db.merge(rec)
            saved += 1
        except Exception as e:
            logger.warning(f"GMS 追溯 {code} {target_date} 失败: {e}")
            continue

    db.commit()
    return saved


@router.post("/gms-signal-trace/recompute")
async def start_gms_signal_trace_recompute(
    body: GmsTraceRecomputeRequest,
    db: Session = Depends(get_db),
):
    """
    异步强制重新计算单股 GMS 信号追溯（当前 config_id）。
    返回 task_id，前端轮询 GET /gms-signal-trace/recompute/{task_id} 获取进度。
    """
    if not GMS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "GMS 策略暂不可用"},
        )

    code = str(body.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    market_type = _infer_market_type(code)
    code_norm = _normalize_code(code, market_type)

    mgr = GMSConfigManager()
    resolved_config_id = _resolve_trace_config_id(db, code_norm, market_type, body.config_id)
    config = mgr.get_config(resolved_config_id)
    config_row = mgr.get_config_row(resolved_config_id)
    config_display = _config_display_name(config_row)

    existing = _find_running_trace_recompute(code_norm, resolved_config_id)
    if existing:
        return JSONResponse({
            "success": True,
            "data": {"task_id": existing, "already_running": True},
            "message": "该股票当前策略版本正在重新计算，请稍候",
        })

    task_id = f"gms_trace_recompute_{uuid.uuid4().hex[:12]}"
    with _trace_recompute_lock:
        _trace_recompute_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "任务已创建，等待执行…",
            "code": code_norm,
            "market_type": market_type,
            "config_id": resolved_config_id,
            "config_name": config_display,
            "current": 0,
            "total": 0,
            "saved_count": None,
            "error": None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    thread = threading.Thread(
        target=_run_trace_recompute_background,
        args=(task_id, code_norm, market_type, resolved_config_id, config, config_display),
        daemon=True,
    )
    thread.start()

    return JSONResponse({
        "success": True,
        "data": {
            "task_id": task_id,
            "config_id": resolved_config_id,
            "config_name": config_display,
        },
    })


@router.get("/gms-signal-trace/recompute/{task_id}")
async def get_gms_signal_trace_recompute_status(task_id: str):
    """查询 GMS 信号追溯强制重算任务进度。"""
    task = _get_trace_recompute_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return JSONResponse({"success": True, "data": task})


@router.get("/gms-signal-trace")
async def get_gms_signal_trace(
    code: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    config_id: Optional[int] = Query(None, ge=1, description="GMS 策略参数版本 ID"),
    force_compute: Optional[int] = Query(None, description="1 时强制重新计算"),
    db: Session = Depends(get_db),
):
    """
    查询某股票的 GMS 信号追溯记录（按 config_id 隔离，避免多版本混显重复）。
    若该版本无记录且未传 force_compute：先执行追溯计算并入库，再返回。
    force_compute=1：仅重算当前 config_id 对应版本。
    """
    if not GMS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "GMS 策略暂不可用", "data": [], "total": 0},
        )

    code = str(code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    market_type = _infer_market_type(code)
    code_norm = _normalize_code(code, market_type)

    try:
        mgr = GMSConfigManager()
        resolved_config_id = _resolve_trace_config_id(db, code_norm, market_type, config_id)
        config = mgr.get_config(resolved_config_id)
        config_row = mgr.get_config_row(resolved_config_id)
        config_options = _list_stock_trace_config_options(db, code_norm, market_type)
        recompute_message: Optional[str] = None

        if force_compute == 1:
            db.query(GMSSignalTrace).filter(
                GMSSignalTrace.code == code_norm,
                GMSSignalTrace.market_type == market_type,
                GMSSignalTrace.config_id == resolved_config_id,
            ).delete(synchronize_session=False)
            db.commit()
            logger.info("GMS 追溯 强制重新计算: %s config_id=%s", code_norm, resolved_config_id)
            count = _compute_gms_trace_for_stock(
                db, code_norm, market_type, config, resolved_config_id
            )
            logger.info("GMS 追溯 计算完成: %s config_id=%s, 写入 %s 条", code_norm, resolved_config_id, count)
            config_options = _list_stock_trace_config_options(db, code_norm, market_type)
            recompute_message = (
                f"已按「{_config_display_name(config_row)}」重新计算，写入 {count} 条"
            )

        else:
            exists = (
                db.query(GMSSignalTrace)
                .filter(
                    GMSSignalTrace.code == code_norm,
                    GMSSignalTrace.market_type == market_type,
                    GMSSignalTrace.config_id == resolved_config_id,
                )
                .first()
            )
            if not exists:
                has_mfr = (
                    db.query(MeanFrequencyResonanceIndicators)
                    .filter(
                        MeanFrequencyResonanceIndicators.code == code_norm,
                        MeanFrequencyResonanceIndicators.market_type == market_type,
                    )
                    .first()
                )
                if not has_mfr:
                    return JSONResponse({
                        "success": True,
                        "data": [],
                        "total": 0,
                        "config_id": resolved_config_id,
                        "config_name": _config_display_name(config_row),
                        "configs": config_options,
                        "message": "该股票暂无 GMS 指标数据",
                    })
                logger.info("GMS 追溯 首次计算: %s config_id=%s", code_norm, resolved_config_id)
                count = _compute_gms_trace_for_stock(
                    db, code_norm, market_type, config, resolved_config_id
                )
                logger.info("GMS 追溯 计算完成: %s config_id=%s, 写入 %s 条", code_norm, resolved_config_id, count)
                config_options = _list_stock_trace_config_options(db, code_norm, market_type)

        q = (
            db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.code == code_norm,
                GMSSignalTrace.market_type == market_type,
                GMSSignalTrace.config_id == resolved_config_id,
            )
        )
        if start_date:
            q = q.filter(GMSSignalTrace.date >= str(start_date)[:10])
        if end_date:
            q = q.filter(GMSSignalTrace.date <= str(end_date)[:10])
        q = q.order_by(GMSSignalTrace.date.desc())
        rows = q.all()

        def to_dict(r):
            return {
                "code": r.code,
                "date": r.date,
                "market_type": r.market_type,
                "config_id": getattr(r, "config_id", resolved_config_id),
                "score_total": r.score_total,
                "score_accumulation": r.score_accumulation,
                "score_momentum": r.score_momentum,
                "signal_strength": r.signal_strength,
                "buy_type": r.buy_type or "",
                "left_buy_signal": r.left_buy_signal,
                "right_buy_signal": r.right_buy_signal,
                "sell_signal": r.sell_signal,
                "accumulation_grade": r.accumulation_grade or "",
                "momentum_grade": r.momentum_grade or "",
                "delta": r.delta,
                "d": r.d,
                "ratio_d20": r.ratio_d20,
                "ratio_d1": r.ratio_d1,
                "fz_ratio": r.fz_ratio,
                "volume_ratio": r.volume_ratio,
                "instant_deviation": r.instant_deviation,
                "rising_days": r.rising_days,
                "falling_days": r.falling_days,
                "score_acc_fz": getattr(r, "score_acc_fz", None),
                "score_acc_balance": getattr(r, "score_acc_balance", None),
                "score_acc_volume": getattr(r, "score_acc_volume", None),
                "score_mom_ratio_d1": getattr(r, "score_mom_ratio_d1", None),
                "score_mom_deviation": getattr(r, "score_mom_deviation", None),
                "score_mom_volume": getattr(r, "score_mom_volume", None),
                "acc_fz_judge": getattr(r, "acc_fz_judge", None) or "",
                "acc_balance_judge": getattr(r, "acc_balance_judge", None) or "",
                "acc_volume_judge": getattr(r, "acc_volume_judge", None) or "",
                "mom_ratio_d1_judge": getattr(r, "mom_ratio_d1_judge", None) or "",
                "mom_deviation_judge": getattr(r, "mom_deviation_judge", None) or "",
                "mom_volume_judge": getattr(r, "mom_volume_judge", None) or "",
            }

        from backend_api.stock.stock_screening_routes import _gms_strategy_config_meta

        gms_config_meta = _gms_strategy_config_meta(mgr, resolved_config_id, config)
        calc_meta = _calculator_score_detail_meta(config)

        data = [to_dict(r) for r in rows]
        # 合并指标表中的 d1/d20/ma60 等；补全得分；附加与选股页一致的 score_detail
        for i, item in enumerate(data):
            merged = _merge_mfr_d1_d20_into_trace_dict(db, item)
            enriched = _enrich_trace_row_score_detail(db, merged, config)
            data[i] = _attach_trace_score_detail(db, enriched, config, gms_config_meta, calc_meta)
        return JSONResponse({
            "success": True,
            "data": data,
            "total": len(data),
            "config_id": resolved_config_id,
            "config_name": _config_display_name(config_row),
            "gms_config_meta": gms_config_meta,
            "configs": config_options,
            "message": recompute_message,
        })
    except Exception as e:
        logger.exception("GMS 信号追溯查询失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e), "data": [], "total": 0},
        )


# ---------- 用户端：单股 GMS 策略回测（复用 admin_interface 任务队列） ----------
try:
    from backend_core.strategies.gms import admin_interface as _gms_admin_if
    from backend_api.admin.gms_admin_routes import _build_task_name_with_stocks as _gms_build_task_name

    _GMS_BACKTEST_AVAILABLE = True
except Exception as _e:
    logger.warning("GMS 回测接口依赖导入失败: %s", _e)
    _gms_admin_if = None  # type: ignore
    _gms_build_task_name = None  # type: ignore
    _GMS_BACKTEST_AVAILABLE = False


class GMSStockBacktestBody(BaseModel):
    """信号追溯页发起的单股回测参数（与管理端 GMS 回测一致，仅允许 single）"""

    code: str = Field(..., description="股票代码")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    market: str = Field("all", description="市场: cn / etf / hk / all")
    target_pct: float = Field(0.05, description="目标涨幅，如 0.05 表示 5%")
    horizon_days: int = Field(20, ge=10, le=30, description="持有窗口交易日数")
    min_score: float = Field(0, ge=0, le=100, description="最低总分（与 GMSFrontendInterface 一致，管理端回测相同）")
    strategy_config_id: Optional[int] = Field(None, ge=1, description="GMS 策略参数版本 ID，不传则用默认版本")


@router.post("/gms-backtest")
async def create_gms_stock_backtest(body: GMSStockBacktestBody, db: Session = Depends(get_db)):
    """
    创建单股 GMS 回测任务，返回 task_id。
    与 POST /api/admin/gms/backtests（stock_pool_mode=single）等价，供前端信号追溯页使用。
    """
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    code = str(body.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        config = {
            "task_name": None,
            "market": body.market,
            "start_date": str(body.start_date).strip()[:10],
            "end_date": str(body.end_date).strip()[:10],
            "target_pct": float(body.target_pct),
            "horizon_days": int(body.horizon_days),
            "min_score": float(body.min_score),
            "backtest_type": "signal_hit_rate",
            "stop_loss_pct": 0,
            "commission_bps": 0,
            "slippage_bps": 0,
            "stock_pool_mode": "single",
            "stock_code": code,
        }
        from backend_core.strategies.gms.config import GMSConfigManager

        mgr = GMSConfigManager()
        cid = mgr.resolve_config_id(body.strategy_config_id)
        row = mgr.get_config_row(cid)
        if body.strategy_config_id is not None and not row:
            raise HTTPException(status_code=404, detail="策略参数版本不存在")
        if row and not row.is_active:
            raise HTTPException(status_code=400, detail="策略参数版本已禁用")
        cfg = mgr.get_config(cid)
        config["strategy_config_id"] = cid
        config["strategy_config_name"] = row.name if row else "default"
        config["config_params_snapshot"] = deepcopy(cfg)
        task_name = _gms_build_task_name(db, config) if _gms_build_task_name else None
        task_id = _gms_admin_if.create_backtest(config, name=task_name or None)
        return {"success": True, "data": {"task_id": task_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建 GMS 单股回测任务失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gms-backtest/{task_id}")
async def get_gms_stock_backtest(task_id: str):
    """查询回测任务状态与结果（与 admin 任务详情一致）。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    task = _gms_admin_if.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True, "data": task}


@router.post("/gms-backtest/{task_id}/cancel")
async def cancel_gms_stock_backtest(task_id: str):
    """取消回测任务。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    ok = _gms_admin_if.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在或无法取消")
    return {"success": True}


@router.get("/gms-backtest/{task_id}/export")
async def export_gms_stock_backtest_csv(task_id: str):
    """导出该回测任务明细（新任务为带列宽的 Excel；旧任务可能仍为 CSV）。"""
    if not _GMS_BACKTEST_AVAILABLE or _gms_admin_if is None:
        raise HTTPException(status_code=503, detail="GMS 回测服务暂不可用")
    payload = _gms_admin_if.download_report(task_id)
    if not payload:
        raise HTTPException(status_code=404, detail="明细不存在或任务未完成")
    data, filename, media_type = payload
    from urllib.parse import quote

    disp = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": disp})
