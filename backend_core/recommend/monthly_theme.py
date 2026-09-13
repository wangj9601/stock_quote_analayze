"""Monthly Theme：120 日主题板 + 中军核心。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.board_roles.service import (
    extract_leader_mid_from_payload,
    fetch_board_roles_payload,
)
from backend_core.recommend.config import MONTHLY_CORE_PER_THEME, MONTHLY_THEME_BOARDS
from backend_core.recommend.env import resolve_asof_date
from backend_core.recommend.store import upsert_brief

logger = logging.getLogger(__name__)


def _next_month_label(asof: str) -> str:
    try:
        d0 = date.fromisoformat(asof[:10])
    except ValueError:
        return "next_month"
    if d0.month == 12:
        return f"{d0.year + 1}-01"
    return f"{d0.year}-{d0.month + 1:02d}"


def _rank_theme_boards(db: Session, asof: str, limit: int) -> List[Dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (board_code)
                       board_code, sector_slope, slope_r2, slope_asof_date, member_count_used
                FROM industry_board_daily_metrics
                WHERE sector_slope_window = 120
                  AND slope_asof_date <= CAST(:asof AS date)
                  AND sector_slope IS NOT NULL
                ORDER BY board_code, slope_asof_date DESC
                """
            ),
            {"asof": asof},
        ).fetchall()
    except Exception as e:
        logger.warning("monthly theme rank failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return []

    ranked = []
    for r in rows:
        try:
            slope = float(r[1])
        except (TypeError, ValueError):
            continue
        if slope <= 0:
            continue
        r2 = float(r[2]) if r[2] is not None else None
        ranked.append(
            {
                "board_code": str(r[0]),
                "sector_slope": slope,
                "slope_r2": r2,
                "slope_asof_date": str(r[3])[:10] if r[3] else None,
                "rank_score": slope + (0.1 * (r2 or 0.0)),
            }
        )
    ranked.sort(key=lambda x: -float(x["rank_score"]))
    top = ranked[:limit]
    codes = [x["board_code"] for x in top]
    names: Dict[str, str] = {}
    if codes:
        try:
            nr = db.execute(
                text(
                    """
                    SELECT board_code, board_name
                    FROM industry_board_realtime_quotes
                    WHERE board_code IN :codes
                    """
                ).bindparams(bindparam("codes", expanding=True)),
                {"codes": codes},
            ).fetchall()
            for row in nr:
                names[str(row[0])] = str(row[1] or row[0])
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    for x in top:
        x["board_name"] = names.get(x["board_code"], x["board_code"])
        x["board_kind"] = "industry"
    return top


def generate_monthly_theme(
    db: Session,
    *,
    asof_date: Optional[str] = None,
    late_run: bool = False,
    persist: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    asof = resolve_asof_date(db, asof_date)
    from backend_core.recommend.env import is_month_last_trading_day

    if not force and not is_month_last_trading_day(db, asof):
        return {
            "skipped": True,
            "reason": "not_month_last_trading_day",
            "asof_date": asof,
        }

    themes = _rank_theme_boards(db, asof, MONTHLY_THEME_BOARDS)
    items: List[Dict[str, Any]] = []
    theme_payloads: List[Dict[str, Any]] = []

    for t in themes:
        bc = t["board_code"]
        payload = None
        try:
            payload = fetch_board_roles_payload(
                db, board_type="industry", board_code=bc, limit=None
            )
        except Exception as e:
            logger.debug("monthly roles %s failed: %s", bc, e)
            try:
                db.rollback()
            except Exception:
                pass
        roles = extract_leader_mid_from_payload(payload)
        mids = roles.get("mids") or []
        leaders = roles.get("leaders") or []
        cores = []
        for row in mids[:MONTHLY_CORE_PER_THEME]:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            code_n = code.zfill(6) if code.isdigit() and len(code) < 6 else code
            item = {
                "code": code_n,
                "name": row.get("name") or row.get("stock_name"),
                "action": "watch",
                "stance": "核心观察",
                "role": "mid",
                "role_label": "中军",
                "board_code": bc,
                "board_name": t.get("board_name"),
                "slot": "core",
                "recommend_score": 30.0,
                "position_hint": "主题核心底仓优先中军，单票上限从严",
                "summary": "月主题核心：中军优先",
            }
            cores.append(item)
            items.append(item)
        satellites = []
        for row in leaders[:2]:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            code_n = code.zfill(6) if code.isdigit() and len(code) < 6 else code
            item = {
                "code": code_n,
                "name": row.get("name") or row.get("stock_name"),
                "action": "watch",
                "stance": "卫星观察",
                "role": "leader",
                "role_label": "龙头",
                "board_code": bc,
                "board_name": t.get("board_name"),
                "slot": "satellite",
                "recommend_score": 18.0,
                "position_hint": "卫星/择机，非默认核心底仓",
                "summary": "月主题卫星：龙头择机",
            }
            satellites.append(item)
            items.append(item)
        theme_payloads.append(
            {
                **t,
                "cores": cores,
                "satellites": satellites,
                "mids": mids,
                "leaders": leaders,
            }
        )

    plan_for = _next_month_label(asof)
    summary = {
        "theme_boards": theme_payloads,
        "plan_for": plan_for,
        "publish_window": "自然月最后交易日收盘后～下月开盘前",
        "position_framework": {
            "total_cap_hint": "总仓按风险偏好自定，主题内分散",
            "per_name_cap_hint": "单票严格上限，中军可略高于龙头",
        },
        "disclaimer": "规则合成参考，非投资建议",
        "counts": {
            "themes": len(theme_payloads),
            "items": len(items),
        },
    }
    if persist:
        return upsert_brief(
            db,
            horizon="monthly",
            asof_date=asof,
            items=items,
            summary=summary,
            risk_observe=[],
            kpi={"themes": len(theme_payloads)},
            market_stance=None,
            plan_for=plan_for,
            late_run=late_run,
        )
    return {
        "horizon": "monthly",
        "asof_date": asof,
        "plan_for": plan_for,
        "summary": summary,
        "items": items,
        "late_run": late_run,
    }
