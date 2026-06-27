"""东财板块代码规则（采集器侧）：BK+数字为合法板块编码格式。"""
from __future__ import annotations

import re

_BK = re.compile(r"^BK(\d+)$", re.IGNORECASE)


def is_concept_board_code(board_code: str | None) -> bool:
    return bool(_BK.match(str(board_code or "").strip()))


def is_industry_board_code(board_code: str | None) -> bool:
    return is_concept_board_code(board_code)
