"""板块龙头/中军分类与来源解析单测。"""

from __future__ import annotations

from backend_core.board_roles.classify import (
    ROLE_LEADER,
    ROLE_MID,
    classify_board_roles,
    role_tag_from_row,
)


def _row(code, chg, amt, mv, name=None):
    return {
        "code": code,
        "name": name or code,
        "change_percent": chg,
        "amount": amt,
        "circulating_market_value": mv,
    }


class TestClassifyBoardRoles:
    def test_tiny_mv_high_chg_not_leader(self):
        # 构造：小市值高涨幅 vs 中高市值中高涨幅
        rows = [
            _row("000001", 9.9, 1e8, 1e8),  # 极小市值，涨幅最高
            _row("000002", 8.5, 2e8, 5e10),
            _row("000003", 7.0, 1.5e8, 4e10),
            _row("000004", 6.0, 1.2e8, 3.5e10),
            _row("000005", 5.0, 1e8, 3e10),
            _row("000006", 4.0, 0.8e8, 2.5e10),
            _row("000007", 3.0, 0.7e8, 2e10),
            _row("000008", 2.0, 0.6e8, 1.5e10),
            _row("000009", 1.0, 0.5e8, 1.2e10),
            _row("000010", 0.5, 0.4e8, 1e10),
        ]
        classify_board_roles(rows)
        by_code = {r["code"]: r for r in rows}
        assert by_code["000001"]["board_role"] != ROLE_LEADER
        leaders = [r for r in rows if r.get("board_role") == ROLE_LEADER]
        assert leaders
        assert all(float(r["mv_pctile"]) >= 40 for r in leaders)

    def test_mid_follows_leader(self):
        rows = [
            _row(f"{i:06d}", chg, amt, mv)
            for i, (chg, amt, mv) in enumerate(
                [
                    (10, 3e8, 8e10),
                    (8, 2.5e8, 6e10),
                    (7, 2e8, 5.5e10),
                    (6.5, 1.8e8, 5e10),
                    (6, 1.5e8, 4.5e10),
                    (5, 1.2e8, 4e10),
                    (4, 1e8, 3e10),
                    (3, 0.8e8, 2e10),
                    (2, 0.5e8, 1e10),
                    (1, 0.3e8, 5e9),
                ],
                start=1,
            )
        ]
        classify_board_roles(rows)
        leaders = [r for r in rows if r.get("board_role") == ROLE_LEADER]
        mids = [r for r in rows if r.get("board_role") == ROLE_MID]
        assert leaders
        assert mids
        leader_codes = {r["code"] for r in leaders}
        assert not leader_codes.intersection({r["code"] for r in mids})
        for r in mids:
            assert 50 <= float(r["mv_pctile"]) <= 95
            assert float(r["chg_pctile"]) >= 60

    def test_role_tag_shape(self):
        rows = [_row("000001", 9, 1e8, 5e10), _row("000002", 1, 1e7, 1e10)]
        # pad to get percentiles meaningful
        for i in range(3, 12):
            rows.append(_row(f"{i:06d}", 5 - i * 0.2, 1e7, 2e10 + i * 1e9))
        classify_board_roles(rows)
        leader = next(r for r in rows if r.get("board_role") == ROLE_LEADER)
        tag = role_tag_from_row(leader)
        assert tag["id"] == "board_leader"
        assert tag["label"] == "龙头"
        assert tag["level"] == "info"


class TestResolveBoardForRoles:
    def test_no_silent_fallback_to_eastmoney(self):
        """同花顺精确匹配失败且无同名映射时返回 None（不混东财）。"""
        from unittest.mock import MagicMock

        from backend_api.utils.industry_board_query import resolve_board_for_roles

        db = MagicMock()
        # 第一次 exact 空；名称查询空；映射空
        db.execute.return_value.fetchone.return_value = None
        out = resolve_board_for_roles(
            db, "industry", "BK9999", board_code_source="tonghuashun"
        )
        assert out is None

    def test_map_by_name_to_tonghuashun(self):
        from unittest.mock import MagicMock

        from backend_api.utils.industry_board_query import resolve_board_for_roles

        db = MagicMock()
        calls = {"n": 0}

        def _execute(sql, params=None):
            calls["n"] += 1
            result = MagicMock()
            if calls["n"] == 1:
                result.fetchone.return_value = None  # exact miss
            else:
                result.fetchone.return_value = ("881101", "半导体", "tonghuashun")
            return result

        db.execute.side_effect = _execute
        out = resolve_board_for_roles(
            db,
            "industry",
            "BK0481",
            board_code_source="tonghuashun",
            board_name="半导体",
        )
        assert out is not None
        assert out["board_code"] == "881101"
        assert out["board_code_source"] == "tonghuashun"
