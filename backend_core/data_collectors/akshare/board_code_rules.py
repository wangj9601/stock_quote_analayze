"""东财板块代码规则：BK 前缀为概念板块，其余为行业板块。"""

from __future__ import annotations


def is_concept_board_code(board_code: str | None) -> bool:
    return str(board_code or "").strip().upper().startswith("BK")


def is_industry_board_code(board_code: str | None) -> bool:
    code = str(board_code or "").strip()
    if not code:
        return False
    return not is_concept_board_code(code)
