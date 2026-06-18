"""东财板块代码：BK 前缀为概念板块，其余为行业板块。"""


def is_concept_board_code(board_code: str) -> bool:
    return str(board_code or "").strip().upper().startswith("BK")


def is_industry_board_code(board_code: str) -> bool:
    code = str(board_code or "").strip()
    return bool(code) and not is_concept_board_code(code)
