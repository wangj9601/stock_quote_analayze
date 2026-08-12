"""板块龙头/中军分类与来源解析单测。"""

from __future__ import annotations

from backend_core.board_roles.classify import (
    LEADER_ABS_MV_MIN,
    MID_ABS_MV_MIN,
    ROLE_LEADER,
    ROLE_MID,
    classify_board_roles,
    is_limit_up,
    is_st_name,
    leader_top_k,
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


def _pad(rows, n=12, base_mv=5e10):
    """补足有效样本，默认市值远高于绝对门槛。"""
    exist = {r["code"] for r in rows}
    i = 1
    while len(rows) < n:
        code = f"{i:06d}"
        if code not in exist:
            # 递减涨幅，市值略降
            rows.append(_row(code, max(0.1, 5 - i * 0.3), 1e8, base_mv - i * 1e9))
            exist.add(code)
        i += 1
    return rows


class TestHelpers:
    def test_is_st_name(self):
        assert is_st_name("ST华微")
        assert is_st_name("*ST华微")
        assert is_st_name("S*ST华微")
        assert not is_st_name("贵州茅台")

    def test_is_limit_up_by_board(self):
        assert is_limit_up("600519", 9.8)
        assert not is_limit_up("600519", 9.7)
        assert is_limit_up("300001", 19.8)
        assert not is_limit_up("300001", 9.9)
        assert is_limit_up("688001", 20.0)

    def test_leader_top_k_formula(self):
        assert leader_top_k(10) == 2  # max(2, ceil(0.5))=2
        assert leader_top_k(100) == 5  # ceil(5)=5
        assert leader_top_k(300) == 10  # min(10, 15)=10


class TestClassifyBoardRoles:
    def test_tiny_mv_high_chg_not_leader(self):
        # 极小市值高涨幅不得龙头（绝对市值门槛）
        rows = [
            _row("000001", 9.9, 1e8, 1e8),  # 1 亿，低于 30 亿
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
        assert all(
            float(r["circulating_market_value"]) >= LEADER_ABS_MV_MIN for r in leaders
        )

    def test_limit_up_bonus_beats_higher_amount_non_limit(self):
        """涨停加分应压过尾盘接近涨停但成交额更大的非涨停票。"""
        rows = [
            _row("600001", 9.9, 1.2e8, 5e10, name="早盘涨停"),  # 涨停，额略小
            _row("600002", 9.5, 3.0e8, 5.2e10, name="尾盘冲高"),  # 非涨停，额更大
        ]
        _pad(rows, n=10)
        classify_board_roles(rows)
        by_code = {r["code"]: r for r in rows}
        assert by_code["600001"]["is_limit_up"] is True
        assert by_code["600002"]["is_limit_up"] is False
        assert by_code["600001"]["board_role"] == ROLE_LEADER
        assert float(by_code["600001"]["board_role_score"]) >= float(
            by_code["600002"]["board_role_score"]
        )

    def test_negative_change_no_role(self):
        rows = [
            _row(f"{i:06d}", -1.0 - i * 0.1, 1e8, 5e10)
            for i in range(1, 12)
        ]
        classify_board_roles(rows)
        assert not any(r.get("board_role") for r in rows)

    def test_st_excluded(self):
        rows = [
            _row("600001", 9.9, 3e8, 5e10, name="ST伪龙头"),
            _row("600002", 8.0, 2e8, 4e10, name="正常票"),
        ]
        _pad(rows, n=10)
        classify_board_roles(rows)
        by_code = {r["code"]: r for r in rows}
        assert by_code["600001"]["board_role"] is None
        assert by_code["600001"]["board_role_score"] is None

    def test_small_n_no_role(self):
        rows = [
            _row("000001", 9.9, 1e8, 5e10),
            _row("000002", 8.0, 1e8, 4e10),
        ]
        classify_board_roles(rows)
        assert not any(r.get("board_role") for r in rows)

    def test_small_n_at_most_one_leader(self):
        # N=7 → 小样本，最多 1 龙头
        rows = [
            _row(f"{i:06d}", 10 - i * 0.5, 1e8 + i * 1e6, 5e10 - i * 1e9)
            for i in range(1, 8)
        ]
        classify_board_roles(rows)
        leaders = [r for r in rows if r.get("board_role") == ROLE_LEADER]
        mids = [r for r in rows if r.get("board_role") == ROLE_MID]
        assert len(leaders) <= 1
        assert len(mids) <= 1

    def test_dual_leader_requires_tight_gap_or_limit(self):
        # 两只分数差较大且非涨停、涨幅差>=1 → 不应双龙头
        rows = [
            _row("600001", 9.9, 3e8, 8e10),  # 涨停龙头
            _row("600002", 5.0, 2e8, 7e10),  # 跟涨但差距大
        ]
        _pad(rows, n=12)
        classify_board_roles(rows)
        leaders = [r for r in rows if r.get("board_role") == ROLE_LEADER]
        assert len(leaders) == 1
        assert leaders[0]["code"] == "600001"

    def test_mid_allows_mega_cap(self):
        """取消 mv<=95 后，超大市值跟涨可进中军。"""
        rows = [
            _row("600001", 9.9, 3e8, 9e10),  # 龙头
            _row("600002", 7.0, 2e8, 2e12),  # 超大市值跟涨
        ]
        # 再补一堆中小市值，抬高 600002 的 mv 分位到接近 100
        for i in range(3, 15):
            rows.append(_row(f"{i:06d}", 3.0 - i * 0.1, 5e7, 1e10 + i * 1e8))
        classify_board_roles(rows)
        by_code = {r["code"]: r for r in rows}
        assert by_code["600001"]["board_role"] == ROLE_LEADER
        # 超大市值票若涨幅分位够应可为中军
        mega = by_code["600002"]
        assert float(mega["mv_pctile"]) >= 50
        if float(mega["chg_pctile"]) >= 60 and float(mega["circulating_market_value"]) >= MID_ABS_MV_MIN:
            assert mega["board_role"] == ROLE_MID

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
                    (4, 1e8, 3.5e10),
                    (3, 0.8e8, 3.2e10),
                    (2, 0.5e8, 3.1e10),
                    (1, 0.3e8, 3.05e10),
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
            assert float(r["mv_pctile"]) >= 50
            assert float(r["chg_pctile"]) >= 60
            assert float(r["circulating_market_value"]) >= MID_ABS_MV_MIN

    def test_role_tag_shape(self):
        rows = [_row("000001", 9.9, 1e8, 5e10), _row("000002", 1, 1e7, 4e10)]
        _pad(rows, n=12)
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
