"""东财板块代码规则（采集器侧）：概念 BK+数字或纯数字；行业另支持中文/英文业务编码。"""
from __future__ import annotations

import re

_BK = re.compile(r"^BK(\d+)$", re.IGNORECASE)
_NUMERIC = re.compile(r"^\d{1,20}$")
_INDUSTRY_TEXT = re.compile(r"^[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9._\-·]{0,19}$")


def is_concept_board_code(board_code: str | None) -> bool:
    s = str(board_code or "").strip()
    if not s:
        return False
    return bool(_BK.match(s.upper()) or _NUMERIC.fullmatch(s))


def is_industry_board_code(board_code: str | None) -> bool:
    s = str(board_code or "").strip()
    if not s:
        return False
    if _BK.match(s.upper()):
        return True
    if _NUMERIC.fullmatch(s):
        return True
    return bool(_INDUSTRY_TEXT.fullmatch(s))
