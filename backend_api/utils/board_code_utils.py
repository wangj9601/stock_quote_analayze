"""东财板块代码规则：BK+数字；行业/概念分表存储且编码全局唯一。"""


def is_concept_board_code(board_code: str) -> bool:
    return str(board_code or "").strip().upper().startswith("BK")


def is_industry_board_code(board_code: str) -> bool:
    from backend_api.utils.bk_board_code import is_valid_bk_board_code

    return is_valid_bk_board_code(board_code)
