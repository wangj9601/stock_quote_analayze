# -*- coding: utf-8 -*-
"""板块斜率入库辅助 / 全成分不截断 / GMS 读库优先 / 仅同花顺来源。"""

from datetime import date
from unittest.mock import MagicMock, patch

from backend_core.board_metrics.sector_slope_store import (
    ALLOWED_SLOPE_BOARD_CODE_SOURCE,
    compute_board_sector_slope_detail,
    ensure_board_sector_slope,
    filter_board_codes_by_source,
    list_concept_board_codes,
    list_industry_board_codes,
    load_board_sector_slopes,
    normalize_member_limit,
    refresh_board_sector_slopes,
    upsert_board_sector_slopes,
)
from backend_core.strategies.gms.board_resonance import (
    compute_board_sector_slope,
    resolve_board_resonance_config,
    _resolve_slopes_for_boards,
)
from backend_core.strategies.rpe.data_loader import RPEDataLoader


def _make_rising_panel(codes, n_days=60):
    panel = {}
    for code in codes:
        bars = []
        for i in range(n_days):
            month = 1 + i // 28
            day = 1 + (i % 28)
            bars.append(
                {
                    "date": f"2024-{month:02d}-{day:02d}",
                    "close": 10.0 + i * 0.05,
                    "volume": 1000.0,
                }
            )
        panel[code] = bars
    return panel


def test_normalize_member_limit_full_by_default():
    assert normalize_member_limit(None) is None
    assert normalize_member_limit(0) is None
    assert normalize_member_limit(-1) is None
    assert normalize_member_limit(40) == 40
    assert normalize_member_limit("60") == 60


def test_resolve_board_resonance_config_default_full_members():
    c = resolve_board_resonance_config({})
    assert c["panel_member_limit"] is None
    assert c["prefer_db_slope"] is True

    c2 = resolve_board_resonance_config({"board_resonance": {"board_panel_member_limit": 0}})
    assert c2["panel_member_limit"] is None

    c3 = resolve_board_resonance_config({"board_resonance": {"board_panel_member_limit": 25}})
    assert c3["panel_member_limit"] == 25


def test_compute_detail_uses_all_members_when_limit_none():
    loader = MagicMock()
    members = [{"code": f"{i:06d}", "name": f"s{i}"} for i in range(50)]
    loader.load_board_members.return_value = members
    codes_all = [m["code"] for m in members]
    loader.load_sector_panel.return_value = _make_rising_panel(codes_all)
    real = RPEDataLoader.__new__(RPEDataLoader)
    loader.build_date_members.side_effect = real.build_date_members

    detail = compute_board_sector_slope_detail(
        loader, "BK0001", member_limit=None, window=20, lookback=80
    )
    assert detail["member_count_used"] == 50
    assert detail["sector_slope"] is not None
    assert detail["sector_slope"] > 0
    assert detail["slope_asof_date"] is not None

    detail2 = compute_board_sector_slope_detail(
        loader, "BK0001", member_limit=10, window=20, lookback=80
    )
    assert detail2["member_count_used"] == 10
    # 第二次调用传入截断后的 codes
    called_codes = loader.load_sector_panel.call_args_list[-1].args[0]
    assert len(called_codes) == 10


def test_compute_board_sector_slope_wrapper_full_default():
    loader = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.compute_board_sector_slope_detail",
        return_value={"sector_slope": 0.123},
    ) as mock_detail:
        v = compute_board_sector_slope(loader, "BK1", member_limit=None)
        assert v == 0.123
        assert mock_detail.call_args.kwargs.get("member_limit") is None


def test_upsert_and_gms_prefer_db_slope():
    db = MagicMock()
    db.execute.return_value = MagicMock()

    n = upsert_board_sector_slopes(
        db,
        [
            {
                "board_code": "BK0001",
                "slope_asof_date": date(2024, 6, 1),
                "sector_slope": -0.05,
                "sector_slope_window": 60,
                "member_count_used": 80,
            }
        ],
        board_kind="industry",
    )
    assert n == 1
    assert db.execute.call_count >= 2

    with patch(
        "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
        side_effect=lambda _db, codes, **_kw: list(codes),
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
            return_value={"BK0001": {"sector_slope": -0.05, "sector_slope_window": 60}},
        ) as mock_load:
            with patch(
                "backend_core.strategies.gms.board_resonance.compute_board_sector_slope"
            ) as mock_compute:
                cache = _resolve_slopes_for_boards(
                    db,
                    ["BK0001", "BK0002"],
                    end_date="2024-06-01",
                    window=60,
                    lookback=120,
                    member_limit=None,
                    prefer_db=True,
                )
                mock_load.assert_called_once()
                assert cache["BK0001"] == -0.05
                assert mock_compute.call_count == 1
                assert mock_compute.call_args.args[1] == "BK0002"


def test_prefer_db_false_always_compute():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
        side_effect=lambda _db, codes, **_kw: list(codes),
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes"
        ) as mock_load:
            with patch(
                "backend_core.strategies.gms.board_resonance.compute_board_sector_slope",
                return_value=0.01,
            ) as mock_compute:
                cache = _resolve_slopes_for_boards(
                    db,
                    ["BK0001"],
                    end_date=None,
                    window=60,
                    lookback=120,
                    member_limit=None,
                    prefer_db=False,
                )
                mock_load.assert_not_called()
                assert mock_compute.call_count == 1
                assert cache["BK0001"] == 0.01


def test_filter_board_codes_by_source_keeps_tonghuashun_only():
    db = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = [("881101",)]
    db.execute.return_value = result

    kept = filter_board_codes_by_source(
        db,
        ["881101", "BK0477", "HT001"],
        board_kind="industry",
        board_code_source="tonghuashun",
    )
    assert kept == ["881101"]
    params = db.execute.call_args[0][1]
    assert params["src"] == ALLOWED_SLOPE_BOARD_CODE_SOURCE
    assert set(params["codes"]) == {"881101", "BK0477", "HT001"}

    # 请求非同花顺来源：直接空
    assert (
        filter_board_codes_by_source(
            db, ["881101"], board_code_source="eastmoney"
        )
        == []
    )


def test_list_industry_board_codes_filters_source():
    db = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = [("881101",), ("881102",)]
    db.execute.return_value = result

    codes = list_industry_board_codes(db)
    assert codes == ["881101", "881102"]
    sql = str(db.execute.call_args[0][0])
    assert "board_code_source" in sql
    assert db.execute.call_args[0][1]["src"] == "tonghuashun"

    assert list_industry_board_codes(db, board_code_source="eastmoney") == []


def test_refresh_skips_non_tonghuashun_boards():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.ensure_board_daily_metrics_table"
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
            return_value=["881101"],
        ) as mock_filter:
            with patch(
                "backend_core.board_metrics.sector_slope_store.compute_board_sector_slope_detail",
                return_value={
                    "board_code": "881101",
                    "sector_slope": 0.01,
                    "slope_asof_date": date(2024, 6, 1),
                    "sector_slope_window": 60,
                    "member_count_used": 10,
                },
            ) as mock_detail:
                with patch(
                    "backend_core.board_metrics.sector_slope_store.upsert_board_sector_slopes",
                    return_value=1,
                ) as mock_upsert:
                    with patch(
                        "backend_core.strategies.rpe.data_loader.RPEDataLoader"
                    ):
                        n, total = refresh_board_sector_slopes(
                            db,
                            board_kind="industry",
                            board_codes=["881101", "BK0477"],
                            commit=False,
                        )
    mock_filter.assert_called_once()
    assert mock_detail.call_count == 1
    assert mock_detail.call_args.args[1] == "881101"
    mock_upsert.assert_called_once()
    assert n == 1
    assert total == 1  # 过滤后仅同花顺板进入尝试


def test_gms_resolve_skips_non_tonghuashun_no_compute():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
        return_value=["881101"],
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
            return_value={"881101": {"sector_slope": 0.02}},
        ) as mock_load:
            with patch(
                "backend_core.strategies.gms.board_resonance.compute_board_sector_slope"
            ) as mock_compute:
                cache = _resolve_slopes_for_boards(
                    db,
                    ["881101", "BK0477"],
                    end_date=None,
                    window=60,
                    lookback=120,
                    member_limit=None,
                    prefer_db=True,
                    board_code_source="tonghuashun",
                )
    assert cache["881101"] == 0.02
    assert cache["BK0477"] is None
    mock_load.assert_called_once()
    assert mock_load.call_args.args[1] == ["881101"]
    mock_compute.assert_not_called()


def test_list_concept_board_codes_tonghuashun_only():
    db = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = [("BK0428",), ("BK0888",)]
    db.execute.return_value = result

    codes = list_concept_board_codes(db)
    assert codes == ["BK0428", "BK0888"]
    sql = str(db.execute.call_args[0][0])
    assert "concept_board_basic_info" in sql
    assert "board_code_source" in sql
    assert db.execute.call_args[0][1]["src"] == "tonghuashun"
    assert list_concept_board_codes(db, board_code_source="eastmoney") == []


def test_refresh_concept_tonghuashun_writes_and_skips_others():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.ensure_board_daily_metrics_table"
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
            return_value=["BK0428"],
        ) as mock_filter:
            with patch(
                "backend_core.board_metrics.sector_slope_store.compute_board_sector_slope_detail",
                return_value={
                    "board_code": "BK0428",
                    "board_kind": "concept",
                    "sector_slope": 0.03,
                    "slope_asof_date": date(2024, 6, 1),
                    "sector_slope_window": 60,
                    "member_count_used": 20,
                },
            ) as mock_detail:
                with patch(
                    "backend_core.board_metrics.sector_slope_store.upsert_board_sector_slopes",
                    return_value=1,
                ) as mock_upsert:
                    with patch(
                        "backend_core.strategies.rpe.data_loader.RPEDataLoader"
                    ):
                        n, total = refresh_board_sector_slopes(
                            db,
                            board_kind="concept",
                            board_codes=["BK0428", "BK0999"],
                            board_code_source="tonghuashun",
                            commit=False,
                        )
    mock_filter.assert_called_once()
    assert mock_filter.call_args.kwargs.get("board_kind") == "concept"
    assert mock_detail.call_count == 1
    assert mock_detail.call_args.kwargs.get("board_kind") == "concept"
    mock_upsert.assert_called_once()
    assert mock_upsert.call_args.kwargs.get("board_kind") == "concept"
    assert n == 1
    assert total == 1

    # 非同花顺来源：直接跳过
    n2, total2 = refresh_board_sector_slopes(
        db,
        board_kind="concept",
        board_codes=["BK0428"],
        board_code_source="eastmoney",
        commit=False,
    )
    assert n2 == 0 and total2 == 0


def test_upsert_and_load_concept_board_slopes():
    db = MagicMock()
    db.execute.return_value = MagicMock()
    n = upsert_board_sector_slopes(
        db,
        [
            {
                "board_code": "BK0428",
                "slope_asof_date": date(2024, 6, 1),
                "sector_slope": 0.04,
                "sector_slope_window": 60,
                "member_count_used": 55,
            }
        ],
        board_kind="concept",
    )
    assert n == 1
    sql = str(db.execute.call_args_list[-1][0][0])
    assert "concept_board_daily_metrics" in sql

    result = MagicMock()
    result.fetchall.return_value = [
        ("BK0428", 0.04, 60, date(2024, 6, 1), 55, None),
    ]
    db.execute.return_value = result
    loaded = load_board_sector_slopes(db, ["BK0428"], board_kind="concept")
    assert loaded["BK0428"]["sector_slope"] == 0.04
    assert loaded["BK0428"]["member_count_used"] == 55
    assert "concept_board_daily_metrics" in str(db.execute.call_args[0][0])


def test_load_board_sector_slopes_ensures_table_and_rollbacks_on_error():
    """读库失败时 rollback，避免 PG 事务中止拖垮后续现算。"""
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.ensure_board_daily_metrics_table"
    ) as mock_ensure:
        db.execute.side_effect = RuntimeError("relation does not exist")
        loaded = load_board_sector_slopes(db, ["881101"], board_kind="industry")
    assert loaded == {}
    mock_ensure.assert_called_once()
    db.rollback.assert_called()


def test_resolve_slopes_computes_after_db_load_failure():
    """模拟未建表/读库炸事务：仍应回退现算并得到斜率。"""
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.filter_board_codes_by_source",
        side_effect=lambda _db, codes, **_kw: list(codes),
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
            side_effect=RuntimeError("InFailedSqlTransaction"),
        ):
            with patch(
                "backend_core.strategies.gms.board_resonance.compute_board_sector_slope",
                return_value=-0.0123,
            ) as mock_compute:
                cache = _resolve_slopes_for_boards(
                    db,
                    ["881101"],
                    end_date="2024-06-01",
                    window=60,
                    lookback=120,
                    member_limit=None,
                    prefer_db=True,
                    board_code_source="tonghuashun",
                )
    assert cache["881101"] == -0.0123
    mock_compute.assert_called_once()
    db.rollback.assert_called()


def test_ensure_board_sector_slope_skips_when_present():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        return_value={"881101": {"sector_slope": 0.05, "slope_asof_date": date(2024, 6, 1)}},
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.refresh_board_sector_slopes"
        ) as mock_refresh:
            row = ensure_board_sector_slope(db, "881101", board_kind="industry")
    assert row["sector_slope"] == 0.05
    mock_refresh.assert_not_called()


def test_ensure_board_sector_slope_refreshes_when_missing():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        side_effect=[
            {},
            {
                "881101": {
                    "sector_slope": 0.07,
                    "sector_slope_window": 60,
                    "slope_asof_date": date(2024, 6, 2),
                    "member_count_used": 12,
                }
            },
        ],
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.refresh_board_sector_slopes",
            return_value=(1, 1),
        ) as mock_refresh:
            row = ensure_board_sector_slope(
                db, "881101", board_kind="industry", commit=True
            )
    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs.get("board_codes") == ["881101"]
    assert mock_refresh.call_args.kwargs.get("commit") is True
    assert row["sector_slope"] == 0.07


def test_ensure_board_sector_slope_rejects_non_tonghuashun():
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.refresh_board_sector_slopes"
    ) as mock_refresh:
        row = ensure_board_sector_slope(
            db, "BK0477", board_code_source="eastmoney"
        )
    assert row is None
    mock_refresh.assert_not_called()


def test_refresh_api_parse_board_codes_csv():
    from backend_api.market_routes import _parse_board_codes_csv

    assert _parse_board_codes_csv(None) is None
    assert _parse_board_codes_csv("") is None
    assert _parse_board_codes_csv("881101, 881102") == ["881101", "881102"]


def test_refresh_board_sector_slopes_reraises_catastrophic_failure():
    """整批失败不得吞成 (0,0)，否则采集会误记 success。"""
    db = MagicMock()
    with patch(
        "backend_core.board_metrics.sector_slope_store.ensure_board_daily_metrics_table",
        side_effect=RuntimeError("boom-table"),
    ):
        try:
            refresh_board_sector_slopes(db, board_kind="industry", commit=True)
            raised = False
        except RuntimeError as e:
            raised = True
            assert "boom-table" in str(e)
    assert raised is True
    db.rollback.assert_called()


def test_collector_run_calls_slope_refresh_after_save_success():
    """行情 save 成功后必须调用斜率挂载；失败不得跳过。"""
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    collector = RealtimeStockIndustryBoardCollector.__new__(
        RealtimeStockIndustryBoardCollector
    )
    collector.table_name = "industry_board_realtime_quotes"
    collector.log_table = "realtime_collect_operation_logs"
    collector.write_log = MagicMock()
    collector.fetch_data = MagicMock(return_value=MagicMock(__len__=lambda _self: 2))
    collector.save_to_db = MagicMock(return_value=(True, None))
    collector._refresh_sector_slopes_after_quotes = MagicMock()

    collector.run()

    collector._refresh_sector_slopes_after_quotes.assert_called_once()
    success_ops = [
        c.kwargs.get("operation_type")
        for c in collector.write_log.call_args_list
        if c.kwargs.get("status") == "success"
    ]
    assert "industry_board_realtime" in success_ops


def test_collector_run_skips_slope_refresh_when_save_fails():
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    collector = RealtimeStockIndustryBoardCollector.__new__(
        RealtimeStockIndustryBoardCollector
    )
    collector.write_log = MagicMock()
    collector.fetch_data = MagicMock(return_value=MagicMock(__len__=lambda _self: 1))
    collector.save_to_db = MagicMock(return_value=(False, "db down"))
    collector._refresh_sector_slopes_after_quotes = MagicMock()

    collector.run()

    collector._refresh_sector_slopes_after_quotes.assert_not_called()


def test_collector_slope_refresh_logs_fail_when_refresh_raises():
    """斜率异常必须写入 industry_board_sector_slope fail，不得静默。"""
    from backend_core.data_collectors.akshare.realtime_stock_industry_board_ak import (
        RealtimeStockIndustryBoardCollector,
    )

    collector = RealtimeStockIndustryBoardCollector.__new__(
        RealtimeStockIndustryBoardCollector
    )
    collector.write_log = MagicMock()
    fake_session = MagicMock()

    with patch(
        "backend_core.data_collectors.akshare.realtime_stock_industry_board_ak.SessionLocal",
        return_value=fake_session,
    ):
        with patch(
            "backend_core.board_metrics.sector_slope_store.refresh_board_sector_slopes",
            side_effect=RuntimeError("slope-broken"),
        ):
            collector._refresh_sector_slopes_after_quotes()

    ops = [(c.kwargs.get("operation_type"), c.kwargs.get("status")) for c in collector.write_log.call_args_list]
    assert ("industry_board_sector_slope", "start") in ops
    assert any(
        t == "industry_board_sector_slope" and s == "fail" for t, s in ops
    )
    fail_calls = [
        c
        for c in collector.write_log.call_args_list
        if c.kwargs.get("operation_type") == "industry_board_sector_slope"
        and c.kwargs.get("status") == "fail"
    ]
    assert fail_calls
    assert "slope-broken" in (fail_calls[0].kwargs.get("error_message") or "")
