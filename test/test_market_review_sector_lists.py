"""每日复盘：领涨/领跌全量上涨下跌列表与主线角色切分。"""

from unittest.mock import MagicMock, patch

from backend_core.market_review.compute import (
    SECTOR_LIST_UI_TOP_N,
    _hydrate_legacy_sector_lists,
    _sector_lists_look_legacy_truncated,
    build_sector_pack,
    split_industry_roles,
)


def test_split_industry_roles_keeps_top10_for_mainline():
    rows = [
        {
            "board_code": f"I{i:03d}",
            "board_name": f"行业{i}",
            "change_percent": 10 - i * 0.1,
            "net_inflow": 1e8 if i < 5 else -1e8,
        }
        for i in range(25)
    ]
    roles = split_industry_roles(rows)
    assert len(roles["leaders"]) == SECTOR_LIST_UI_TOP_N
    assert roles["main"] is not None
    assert roles["main"]["board_code"] in {r["board_code"] for r in roles["leaders"]}


def test_build_sector_pack_returns_all_up_and_down_boards():
    db = MagicMock()

    # 模拟 SQL：上涨 DESC、下跌 ASC（跌幅最深在前）
    gain = [(f"U{i}", f"涨{i}", 5.0 - i * 0.1, 1e8) for i in range(15)]
    loss = [(f"D{i}", f"跌{i}", -2.1 + i * 0.1, -1e8) for i in range(12)]

    def fake_execute(sql, params=None):
        s = str(sql)
        result = MagicMock()
        if "board_fund_flow_daily" in s and "change_percent" in s:
            if "change_percent > 0" in s:
                result.fetchall.return_value = gain
            elif "change_percent < 0" in s:
                result.fetchall.return_value = loss
            else:
                result.fetchall.return_value = []
            return result
        if "industry_board_constituents" in s:
            result.fetchall.return_value = []
            return result
        if "board_kind = 'industry'" in s and "main_net_inflow" in s:
            # capital_in / capital_out / ths tops
            result.fetchall.return_value = []
            return result
        result.fetchall.return_value = []
        return result

    db.execute.side_effect = fake_execute

    import backend_core.market_review.compute as compute_mod

    orig_dates = compute_mod._trading_dates_on_or_before
    orig_tops = compute_mod._fetch_ths_board_tops
    compute_mod._trading_dates_on_or_before = lambda *_a, **_k: ["2026-10-08", "2026-10-09"]
    compute_mod._fetch_ths_board_tops = lambda *_a, **_k: {}
    try:
        pack = build_sector_pack(db, "2026-10-09")
    finally:
        compute_mod._trading_dates_on_or_before = orig_dates
        compute_mod._fetch_ths_board_tops = orig_tops

    assert len(pack["leaders"]) == 15
    assert len(pack["laggards"]) == 12
    assert pack["leaders"][0]["change_percent"] >= pack["leaders"][-1]["change_percent"]
    assert pack["laggards"][0]["change_percent"] <= pack["laggards"][-1]["change_percent"]
    # 主线仍从涨幅前 10 中按净流入挑选
    assert pack["main"] is not None
    assert pack["main"]["board_code"] in {r["board_code"] for r in pack["leaders"][:10]}


def test_sector_lists_look_legacy_truncated_only_exact_10_and_3():
    assert _sector_lists_look_legacy_truncated(
        {"leaders": [{}] * 10, "laggards": [{}] * 3}
    )
    assert not _sector_lists_look_legacy_truncated(
        {"leaders": [{}] * 10, "laggards": [{}] * 4}
    )
    assert not _sector_lists_look_legacy_truncated(
        {"leaders": [{}] * 60, "laggards": [{}] * 3}
    )


def test_hydrate_legacy_sector_lists_expands_and_persists():
    db = MagicMock()
    data = {
        "mainline_json": {
            "sector": {
                "leaders": [{"board_code": f"U{i}", "board_name": f"涨{i}"} for i in range(10)],
                "laggards": [{"board_code": f"D{i}", "board_name": f"跌{i}"} for i in range(3)],
                "ladder": {"b2": 1},
            }
        }
    }
    fresh = {
        "leaders": [{"board_code": f"U{i}"} for i in range(15)],
        "laggards": [{"board_code": f"D{i}"} for i in range(12)],
        "main": {"board_code": "U0"},
        "sidelines": [],
        "rotation": {"dropped": [], "new_inflow": []},
        "capital_in": [],
        "capital_out": [],
    }
    with patch(
        "backend_core.market_review.compute.build_sector_pack", return_value=fresh
    ):
        out = _hydrate_legacy_sector_lists(db, "2026-10-09", data)
    sector = out["mainline_json"]["sector"]
    assert len(sector["leaders"]) == 15
    assert len(sector["laggards"]) == 12
    assert sector["ladder"] == {"b2": 1}  # 非列表字段保留
    assert db.execute.called
    assert db.commit.called
