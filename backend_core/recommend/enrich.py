"""读取简报时补齐名称 / 同花顺行业 / 推荐分明细（兼容历史快照）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _norm_code(code: Any) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _is_usable_detail(detail: Any) -> bool:
    if not isinstance(detail, dict) or not detail:
        return False
    # 至少要有分项数值，避免空 dict / 残缺结构被当成已有明细
    return any(k in detail for k in ("resonance", "quality", "action_bonus", "total"))


def _lookup_strategy_scores(
    db: Session, asof_date: Optional[str], codes: List[str]
) -> Dict[str, float]:
    """尽量从当日 signal_trace 取主策略原始分，供历史简报补算质量项。"""
    if not asof_date or not codes:
        return {}
    d = str(asof_date).strip()[:10]
    out: Dict[str, float] = {}
    try:
        from backend_api.models import GMSSignalTrace, RPESignalTrace, URTSignalTrace
        from backend_core.recommend.candidates import _default_config_id
        from backend_api.models import (
            GMSStrategyConfig,
            RPEStrategyConfig,
            URTStrategyConfig,
        )

        code_set = list(set(codes))
        gms_cid = _default_config_id(db, GMSStrategyConfig)
        urt_cid = _default_config_id(db, URTStrategyConfig)
        rpe_cid = _default_config_id(db, RPEStrategyConfig)

        if gms_cid is not None:
            rows = (
                db.query(GMSSignalTrace.code, GMSSignalTrace.score_total)
                .filter(
                    GMSSignalTrace.date == d,
                    GMSSignalTrace.config_id == int(gms_cid),
                    GMSSignalTrace.code.in_(code_set),
                )
                .all()
            )
            for code, score in rows:
                if score is None:
                    continue
                c = _norm_code(code)
                f = float(score)
                if c not in out or f > out[c]:
                    out[c] = f

        if urt_cid is not None:
            rows = (
                db.query(URTSignalTrace.code, URTSignalTrace.score)
                .filter(
                    URTSignalTrace.date == d,
                    URTSignalTrace.config_id == int(urt_cid),
                    URTSignalTrace.code.in_(code_set),
                    URTSignalTrace.buy_signal.is_(True),
                )
                .all()
            )
            for code, score in rows:
                if score is None:
                    continue
                c = _norm_code(code)
                f = float(score)
                if c not in out or f > out[c]:
                    out[c] = f

        if rpe_cid is not None:
            try:
                from datetime import date as _date

                td = _date.fromisoformat(d)
            except ValueError:
                td = None
            if td is not None:
                rows = (
                    db.query(RPESignalTrace.code, RPESignalTrace.z_score)
                    .filter(
                        RPESignalTrace.trade_date == td,
                        RPESignalTrace.config_id == int(rpe_cid),
                        RPESignalTrace.code.in_(code_set),
                    )
                    .all()
                )
                for code, score in rows:
                    if score is None:
                        continue
                    # RPE z_score 尺度不同：映射到 0~100 近似，避免质量项爆炸
                    c = _norm_code(code)
                    z = float(score)
                    mapped = max(0.0, min(100.0, 50.0 + z * 10.0))
                    if c not in out or mapped > out[c]:
                        out[c] = mapped
    except Exception as e:
        logger.debug("lookup strategy scores failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return out


def _backfill_quality_from_total(detail: Dict[str, Any], total: Any) -> Dict[str, Any]:
    """历史快照缺 best_score 时，用总分反推质量分，保证分项可加总。"""
    try:
        t = float(total)
    except (TypeError, ValueError):
        return detail
    resonance = float(detail.get("resonance") or 0)
    action = float(detail.get("action_bonus") or 0)
    role = float(detail.get("role_bonus") or 0)
    quality = round(t - resonance - action - role, 2)
    if quality < 0:
        quality = 0.0
    detail = dict(detail)
    detail["quality"] = quality
    if detail.get("quality_raw") is None and quality > 0:
        # 反推原始分：quality = min(raw,100)*0.3
        detail["quality_raw"] = round(quality / 0.3, 2)
        detail["quality_note"] = (
            f"主策略质量≈{detail['quality_raw']:g}×0.3（由总分反推）"
        )
    detail["total"] = t
    return detail


def enrich_brief_items_for_display(
    db: Session,
    items: List[Dict[str, Any]],
    *,
    asof_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not items:
        return items
    codes = []
    for it in items:
        if not isinstance(it, dict):
            continue
        c = _norm_code(it.get("code"))
        if c:
            codes.append(c)
    if not codes:
        return items

    from backend_core.recommend.env import load_stock_names, map_stocks_to_ths_industry
    from backend_core.recommend.scoring import compute_recommend_score

    name_map = load_stock_names(db, codes)
    board_map = map_stocks_to_ths_industry(db, codes)
    score_map = _lookup_strategy_scores(db, asof_date, codes)

    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            out.append(it)
            continue
        row = dict(it)
        code = _norm_code(row.get("code"))
        if code:
            row["code"] = code
        bm = board_map.get(code) or {}
        raw_name = (row.get("name") or "").strip()
        if raw_name in ("-", "--", "None", "null"):
            raw_name = ""
        filled_name = raw_name or bm.get("stock_name") or name_map.get(code) or ""
        if filled_name:
            row["name"] = filled_name
        industry = bm.get("industry") or bm.get("board_name")
        if industry:
            row["industry"] = industry
            row["board_name"] = industry
            if not row.get("board_code") and bm.get("board_code"):
                row["board_code"] = bm.get("board_code")

        detail = row.get("score_detail")
        need_rebuild = not _is_usable_detail(detail)
        if need_rebuild:
            best_score = None
            ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            if ev.get("best_score") is not None:
                try:
                    best_score = float(ev.get("best_score"))
                except (TypeError, ValueError):
                    best_score = None
            if best_score is None and code in score_map:
                best_score = score_map[code]
            role = row.get("role")
            if role == "normal":
                role = None
            try:
                score, rebuilt = compute_recommend_score(
                    strategies=list(row.get("strategies") or []),
                    best_score=best_score,
                    advice_action=str(row.get("action") or "watch"),
                    role=role,
                    board_weak=bool(row.get("board_weak")),
                )
                stored_total = row.get("recommend_score")
                if stored_total is not None:
                    rebuilt["total"] = stored_total
                    # 若追溯不到质量分，用总分反推，保证展示一致
                    if best_score is None:
                        rebuilt = _backfill_quality_from_total(rebuilt, stored_total)
                        rebuilt["note"] = "历史快照补算明细（质量项由总分反推）"
                    else:
                        # 用存储总分覆盖，分项仍按追溯质量展示；若偏差大则反推对齐
                        try:
                            if abs(float(score) - float(stored_total)) > 0.51:
                                rebuilt = _backfill_quality_from_total(
                                    rebuilt, stored_total
                                )
                                rebuilt["note"] = "历史快照补算明细（已与落库总分对齐）"
                        except (TypeError, ValueError):
                            pass
                else:
                    row["recommend_score"] = score
                row["score_detail"] = rebuilt
            except Exception as e:
                logger.debug("rebuild score_detail failed code=%s: %s", code, e)
        else:
            # 已有明细但质量为 0 且总分更高：补齐质量
            d = dict(detail)
            try:
                total = float(row.get("recommend_score") if row.get("recommend_score") is not None else d.get("total") or 0)
                parts = (
                    float(d.get("resonance") or 0)
                    + float(d.get("quality") or 0)
                    + float(d.get("action_bonus") or 0)
                    + float(d.get("role_bonus") or 0)
                )
                if abs(parts - total) > 0.51 and float(d.get("quality") or 0) == 0:
                    row["score_detail"] = _backfill_quality_from_total(d, total)
            except (TypeError, ValueError):
                row["score_detail"] = d

        out.append(row)
    return out
