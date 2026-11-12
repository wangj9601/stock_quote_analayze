# -*- coding: utf-8 -*-
"""闸门用板块目录加载。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text

from backend_core.board_gates.config import DEFAULT_BOARD_CODE_SOURCE

logger = logging.getLogger(__name__)


def list_boards(
    db,
    *,
    board_kind: str = "industry",
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
    observe_only: bool = False,
) -> List[Dict[str, Any]]:
    kind = (board_kind or "industry").strip().lower()
    table = (
        "industry_board_basic_info"
        if kind == "industry"
        else "concept_board_basic_info"
    )
    extra = "AND COALESCE(trade_observe_flag, FALSE) = TRUE" if observe_only else ""
    try:
        rows = db.execute(
            text(
                f"""
                SELECT board_code, board_name,
                       COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag
                FROM {table}
                WHERE COALESCE(board_code_source, :src) = :src
                  {extra}
                ORDER BY board_code
                """
            ),
            {"src": board_code_source},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("list_boards %s failed: %s", kind, e)
        try:
            db.rollback()
        except Exception:
            pass
        return []
