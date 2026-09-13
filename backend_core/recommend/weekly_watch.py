"""Weekly Watch：60 日主线板 + 角色优先观察池。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.board_metrics.sector_slope_store import load_board_sector_slopes
from backend_core.board_roles.service import (
    extract_leader_mid_from_payload,
    fetch_board_roles_payload,
)
from backend_core.recommend.config import WEEKLY_MAIN_BOARDS, WEEKLY_WATCH_POOL
from backend_core.recommend.env import resolve_asof_date
from backend_core.recommend.store import get_brief, upsert_brief

logger = logging.getLogger(__name__)


def _next_week_label(asof: str) -> str:
    try:
        d0 = date.fromisoformat(asof[:10])
    except ValueError:
        return "next_week"
    # 下一自然周的周一
    days_ahead = 7 - d0.weekday()
    nxt_mon = d0 + timedelta(days=days_ahead)
    nxt_fri = nxt_mon + timedelta(days=4)
    return f"{nxt_mon.isoformat()}~{nxt_fri.isoformat()}"


def _rank_boards_by_slope60(db: Session, asof: str, limit: int) -> List[Dict[str, Any]]:
    """从 industry_board_daily_metrics 取 60 日斜率排名。"""
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (board_code)
                       board_code, sector_slope, slope_r2, slope_asof_date, member_count_used
                FROM industry_board_daily_metrics
                WHERE sector_slope_window = 60
                  AND slope_asof_date <= CAST(:asof AS date)
                  AND sector_slope IS NOT NULL
                ORDER BY board_code, slope_asof_date DESC
                """
            ),
            {"asof": asof},
        ).fetchall()
    except Exception as e:
        logger.warning("weekly slope rank failed: %s", e)
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
        r2 = float(r[2]) if r[2] is not None else None
        # 走强：斜率 > 0；有 R² 则偏好更高
        if slope <= 0:
            continue
        ranked.append(
            {
                "board_code": str(r[0]),
                "sector_slope": slope,
                "slope_r2": r2,
                "slope_asof_date": str(r[3])[:10] if r[3] else None,
                "member_count_used": r[4],
                "rank_score": slope + (0.1 * (r2 or 0.0)),
            }
        )
    ranked.sort(key=lambda x: -float(x["rank_score"]))
    top = ranked[:limit]

    # 补板名
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


def _recent_strategy_hit_codes(db: Session, asof: str, lookback: int = 5) -> set:
    """近 N 日四策略买点代码并集。"""
    from backend_core.recommend.candidates import collect_strategy_buy_candidates

    codes: set = set()
    try:
        d0 = date.fromisoformat(asof[:10])
    except ValueError:
        return codes
    for i in range(lookback):
        d = (d0 - timedelta(days=i)).isoformat()
        try:
            by = collect_strategy_buy_candidates(db, d, limit_per_strategy=200)
        except Exception:
            continue
        for rows in by.values():
            for r in rows:
                c = str(r.get("code") or "").strip()
                if c:
                    codes.add(c)
    return codes


def generate_weekly_watch(
    db: Session,
    *,
    asof_date: Optional[str] = None,
    late_run: bool = False,
    persist: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    asof = resolve_asof_date(db, asof_date)
    from backend_core.recommend.env import is_week_last_trading_day

    if not force and not is_week_last_trading_day(db, asof):
        return {
            "skipped": True,
            "reason": "not_week_last_trading_day",
            "asof_date": asof,
        }

    main_boards = _rank_boards_by_slope60(db, asof, WEEKLY_MAIN_BOARDS)
    hit_codes = _recent_strategy_hit_codes(db, asof, lookback=5)

    monthly = get_brief(db, horizon="monthly", asof_date=None)
    monthly_asof = monthly.get("asof_date") if monthly else None

    watch_items: List[Dict[str, Any]] = []
    board_payloads: List[Dict[str, Any]] = []

    for b in main_boards:
        bc = b["board_code"]
        payload = None
        try:
            payload = fetch_board_roles_payload(
                db, board_type="industry", board_code=bc, limit=None
            )
        except Exception as e:
            logger.debug("weekly roles %s failed: %s", bc, e)
            try:
                db.rollback()
            except Exception:
                pass
        roles = extract_leader_mid_from_payload(payload)
        leaders = roles.get("leaders") or []
        mids = roles.get("mids") or []
        board_payloads.append(
            {
                **b,
                "leaders": leaders,
                "mids": mids,
            }
        )
        # 观察池：优先中军与龙头，且近 5 日有策略命中者优先
        for role_name, lst in (("mid", mids), ("leader", leaders)):
            for row in lst:
                code = str(row.get("code") or "").strip()
                if not code:
                    continue
                code_n = code.zfill(6) if code.isdigit() and len(code) < 6 else code
                watch_items.append(
                    {
                        "code": code_n,
                        "name": row.get("name") or row.get("stock_name"),
                        "action": "watch",
                        "stance": "观察",
                        "role": role_name,
                        "role_label": "中军" if role_name == "mid" else "龙头",
                        "board_code": bc,
                        "board_name": b.get("board_name"),
                        "recent_strategy_hit": code_n in hit_codes,
                        "primary_strategy": None,
                        "recommend_score": (
                            20.0
                            + (10.0 if code_n in hit_codes else 0.0)
                            + (5.0 if role_name == "mid" else 3.0)
                        ),
                        "summary": "周观察池：主线板角色优先",
                        "trigger_hint": "日线策略买点确认且板环境未否决时可升级执行",
                        "degrade_hint": "周一跳空/板环境翻转则降级，不追高",
                    }
                )

    # 去重保最高分
    by_code: Dict[str, Dict[str, Any]] = {}
    for it in watch_items:
        c = it["code"]
        prev = by_code.get(c)
        if prev is None or float(it["recommend_score"]) > float(prev["recommend_score"]):
            by_code[c] = it
    items = sorted(by_code.values(), key=lambda x: -float(x["recommend_score"]))[
        :WEEKLY_WATCH_POOL
    ]

    plan_for = _next_week_label(asof)
    summary = {
        "main_boards": board_payloads,
        "plan_for": plan_for,
        "monthly_asof_ref": monthly_asof,
        "publish_window": "周五收盘后～周一开盘前（本周最后交易日 EOD）",
        "degrade_clause": "周一开盘若跳空或板环境翻转则降级执行",
        "disclaimer": "规则合成参考，非投资建议",
        "counts": {"main_boards": len(board_payloads), "watch_pool": len(items)},
    }
    if persist:
        return upsert_brief(
            db,
            horizon="weekly",
            asof_date=asof,
            items=items,
            summary=summary,
            risk_observe=[],
            kpi={"watch_pool": len(items)},
            market_stance=None,
            plan_for=plan_for,
            late_run=late_run,
        )
    return {
        "horizon": "weekly",
        "asof_date": asof,
        "plan_for": plan_for,
        "summary": summary,
        "items": items,
        "late_run": late_run,
    }
