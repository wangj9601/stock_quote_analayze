"""用户 GMS 选股偏好（仅保存筛选范围/版本等，不保存策略参数本体）。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user/preferences", tags=["user-preferences"])


class GmsScreeningPreferences(BaseModel):
    config_id: Optional[int] = None
    scope: Optional[str] = None
    cn_board_segment: Optional[str] = None
    page_size: Optional[int] = Field(None, ge=1, le=500)
    use_pagination: Optional[bool] = None
    exclude_st: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None


def _load_prefs(db: Session, user_id: int) -> Dict[str, Any]:
    try:
        row = db.execute(
            text("SELECT preferences_json FROM user_gms_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
        if row is None:
            return {}
        if isinstance(row, dict):
            return row
        if isinstance(row, str):
            return json.loads(row)
        return dict(row)
    except Exception as e:
        logger.warning("读取 user_gms_preferences 失败: %s", e)
        return {}


def _save_prefs(db: Session, user_id: int, prefs: Dict[str, Any]) -> None:
    db.execute(
        text(
            """
            INSERT INTO user_gms_preferences (user_id, preferences_json, updated_at)
            VALUES (:uid, CAST(:pj AS JSONB), NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET preferences_json = EXCLUDED.preferences_json, updated_at = NOW()
            """
        ),
        {"uid": user_id, "pj": json.dumps(prefs, ensure_ascii=False)},
    )
    db.commit()


@router.get("/gms-screening")
async def get_gms_screening_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prefs = _load_prefs(db, int(current_user.id))
    return {"success": True, "data": prefs.get("gms_screening") or {}}


@router.put("/gms-screening")
async def put_gms_screening_preferences(
    body: GmsScreeningPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prefs = _load_prefs(db, int(current_user.id))
    gms = prefs.get("gms_screening") or {}
    payload = body.model_dump(exclude_none=True)
    gms.update(payload)
    prefs["gms_screening"] = gms
    try:
        _save_prefs(db, int(current_user.id), prefs)
    except Exception as e:
        logger.exception("保存 GMS 偏好失败")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": gms}
