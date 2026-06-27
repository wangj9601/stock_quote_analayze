"""东财板块代码规则：概念板块 BK+数字；行业板块另支持中文/英文业务编码。"""


def is_concept_board_code(board_code: str) -> bool:
    return str(board_code or "").strip().upper().startswith("BK")


def is_industry_board_code(board_code: str) -> bool:
    from backend_api.utils.bk_board_code import is_valid_industry_board_code

    return is_valid_industry_board_code(board_code)
