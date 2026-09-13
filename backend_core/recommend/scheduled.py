"""日终推荐简报任务入口（workflow / 管理端重跑）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def run_recommend_brief_job(
    *,
    asof_date: Optional[str] = None,
    late_run: bool = False,
    force_weekly: bool = False,
    force_monthly: bool = False,
    horizons: Optional[list] = None,
) -> Dict[str, Any]:
    """生成推荐简报。

    默认：每日必跑；周/月仅在日历触发日（或 force_*）生成。
    """
    from backend_api.database import SessionLocal
    from backend_core.recommend.daily_brief import generate_daily_brief
    from backend_core.recommend.monthly_theme import generate_monthly_theme
    from backend_core.recommend.weekly_watch import generate_weekly_watch

    want = set(horizons or ["daily", "weekly", "monthly"])
    db = SessionLocal()
    result: Dict[str, Any] = {"ok": True, "asof_date": asof_date}
    try:
        if "daily" in want:
            daily = generate_daily_brief(
                db, asof_date=asof_date, late_run=late_run, persist=True
            )
            result["daily"] = {
                "asof_date": daily.get("asof_date"),
                "counts": (daily.get("summary") or {}).get("counts"),
                "item_count": len(daily.get("items") or []),
            }
            if not asof_date:
                asof_date = daily.get("asof_date")
                result["asof_date"] = asof_date

        if "weekly" in want:
            weekly = generate_weekly_watch(
                db,
                asof_date=asof_date,
                late_run=late_run,
                persist=True,
                force=force_weekly,
            )
            result["weekly"] = weekly if weekly.get("skipped") else {
                "asof_date": weekly.get("asof_date"),
                "plan_for": weekly.get("plan_for"),
                "item_count": len(weekly.get("items") or []),
                "skipped": False,
            }

        if "monthly" in want:
            monthly = generate_monthly_theme(
                db,
                asof_date=asof_date,
                late_run=late_run,
                persist=True,
                force=force_monthly,
            )
            result["monthly"] = monthly if monthly.get("skipped") else {
                "asof_date": monthly.get("asof_date"),
                "plan_for": monthly.get("plan_for"),
                "item_count": len(monthly.get("items") or []),
                "skipped": False,
            }
        return result
    except Exception as e:
        logger.exception("run_recommend_brief_job failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "error": str(e), "asof_date": asof_date}
    finally:
        db.close()
