"""概念板块：无成分编码回退到同名同来源有成分板。"""

from unittest.mock import MagicMock

from backend_api.utils.bk_board_code import (
    prefer_concept_board_with_constituents,
    resolve_concept_board_codes,
)


def test_prefer_keeps_code_when_has_members():
    db = MagicMock()
    db.execute.return_value.scalar.return_value = 12
    assert prefer_concept_board_with_constituents(db, "885887") == "885887"


def test_prefer_switches_empty_to_sibling_with_members():
    db = MagicMock()

    def execute(sql, params=None):
        q = str(sql)
        res = MagicMock()
        if "COUNT(*) FROM concept_board_constituents" in q and "WHERE board_code" in q:
            # first call for 881329 -> 0
            res.scalar.return_value = 0
            return res
        if "FROM concept_board_basic_info" in q and "WHERE board_code = :code" in q:
            res.fetchone.return_value = ("数据中心（AIDC）", "tonghuashun")
            return res
        if "HAVING COUNT" in q or "ORDER BY COUNT" in q:
            res.fetchone.return_value = ("885887", 649)
            return res
        res.scalar.return_value = 0
        res.fetchone.return_value = None
        return res

    db.execute.side_effect = execute
    assert prefer_concept_board_with_constituents(db, "881329") == "885887"


def test_resolve_concept_board_codes_uses_prefer():
    db = MagicMock()

    def execute(sql, params=None):
        q = str(sql)
        res = MagicMock()
        if "UNION" in q and "concept_board_constituents" in q and "LIMIT 1" in q:
            res.fetchone.return_value = ("881329",)
            return res
        if "COUNT(*) FROM concept_board_constituents" in q:
            code = (params or {}).get("code")
            res.scalar.return_value = 0 if code == "881329" else 10
            return res
        if "WHERE board_code = :code" in q and "board_name" in q:
            res.fetchone.return_value = ("数据中心（AIDC）", "tonghuashun")
            return res
        if "HAVING COUNT" in q or "ORDER BY COUNT" in q:
            res.fetchone.return_value = ("885887", 649)
            return res
        res.fetchone.return_value = None
        res.scalar.return_value = 0
        return res

    db.execute.side_effect = execute
    out = resolve_concept_board_codes(db, ["881329"])
    assert out == ["885887"]
