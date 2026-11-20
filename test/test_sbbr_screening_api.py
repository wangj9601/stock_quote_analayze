"""SBBR API 结构冒烟：配置默认值与路由模块可导入。"""

def test_default_config_shape():
    from backend_core.strategies.sbbr.config import get_default_sbbr_config

    cfg = get_default_sbbr_config()
    assert "size" in cfg and "entry" in cfg and "position" in cfg
    assert cfg["position"]["probe_pct"] == 50.0
    assert cfg["position"]["add_pct"] == 30.0
    assert cfg["position"]["reserve_cash_pct"] == 20.0


def test_import_routes():
    from backend_api.sbbr_routes import router as user_router
    from backend_api.admin.sbbr_admin_routes import router as admin_router

    paths = {getattr(r, "path", None) for r in user_router.routes}
    assert any(p and "formal-trades" in p for p in paths)
    admin_paths = {getattr(r, "path", None) for r in admin_router.routes}
    assert any(p and "backtests" in p for p in admin_paths)
    assert any(p and str(p).endswith("/scope-users") for p in admin_paths)


def test_import_engine():
    from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

    eng = SBBRStrategyEngine(config=__import__("backend_core.strategies.sbbr.config", fromlist=["get_default_sbbr_config"]).get_default_sbbr_config())
    assert eng is not None


def test_sbbr_strategy_route_accepts_board_params():
    """选股路由签名含行业/概念/板型参数，与 GMS/RPE 对齐。"""
    import inspect
    from backend_api.stock import stock_screening_routes as routes

    sig = inspect.signature(routes.get_sbbr_strategy)
    params = set(sig.parameters)
    assert "cn_board_segment" in params
    assert "industry_board_code" in params
    assert "concept_board_code" in params
    assert "scope" in params
    assert "stock_code" in params
    assert "watchlist_user_id" in params


def test_board_segment_filter_reuse():
    from backend_api.utils.cn_listed_board_filter import (
        filter_stock_codes_by_board_segment,
        filter_stock_codes_by_board_segments,
    )

    codes = ["600000", "000001", "300001", "688001", "002001"]
    main = filter_stock_codes_by_board_segment(codes, "MAIN")
    assert "600000" in main and "000001" in main
    assert "300001" not in main and "688001" not in main

    multi = filter_stock_codes_by_board_segments(codes, ["MAIN", "CYB"])
    assert "600000" in multi and "300001" in multi
    assert "688001" not in multi
    cyb = filter_stock_codes_by_board_segment(codes, "CYB")
    assert cyb == ["300001"]
    kcb = filter_stock_codes_by_board_segment(codes, "KCB")
    assert kcb == ["688001"]
    sme = filter_stock_codes_by_board_segment(codes, "SZ_SME")
    assert sme == ["002001"]


def test_sbbr_attach_industry_names_tonghuashun(monkeypatch):
    from backend_api.stock import stock_screening_routes as routes

    rows = [{"code": "603609", "name": "禾丰股份"}, {"code": "300674", "name": "宇信科技"}]

    def _fake_batch(db, codes, board_code_source=None):
        assert board_code_source == "tonghuashun"
        return {"603609": "饲料", "300674": "软件开发"}

    monkeypatch.setattr(
        "backend_api.utils.industry_board_query.batch_industry_board_names_by_stock_codes",
        _fake_batch,
    )
    routes._sbbr_attach_industry_names(db=None, rows=rows)
    assert rows[0]["industry_board_name"] == "饲料"
    assert rows[0]["sector_name"] == "饲料"
    assert rows[0]["sector_name_source"] == "tonghuashun"
    assert rows[1]["industry_board_name"] == "软件开发"


def test_sbbr_screen_single_bypasses_size_filter():
    """个股传入 codes 且 require_size=False 时，未过做小仍应返回结果行。"""
    from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

    eng = SBBRStrategyEngine(
        config=__import__(
            "backend_core.strategies.sbbr.config", fromlist=["get_default_sbbr_config"]
        ).get_default_sbbr_config()
    )
    fake_row = {
        "code": "600519",
        "size_ok": False,
        "bottom_matched": False,
        "entry_signal": False,
        "volume_ratio": 1.0,
    }

    def _fake_eval(code, **kwargs):
        return dict(fake_row, code=code)

    eng.evaluate_code = _fake_eval  # type: ignore[method-assign]
    eng.loader.resolve_effective_trade_date = lambda d=None: "2026-01-05"  # type: ignore
    eng.loader.load_bars_batch = lambda codes, **kwargs: {}  # type: ignore[method-assign]
    eng.loader.load_market_returns = lambda end_date=None: []  # type: ignore
    eng.loader.load_share_map = lambda codes, as_of_date=None: {  # type: ignore
        "600519": {"name": "贵州茅台", "total_shares": 1e10, "free_float_shares": 1e10}
    }

    with_size = eng.screen(codes=["600519"], require_size=True, require_bottom=False, require_entry=False)
    assert with_size == []

    no_size = eng.screen(codes=["600519"], require_size=False, require_bottom=False, require_entry=False)
    assert len(no_size) == 1
    assert no_size[0]["size_ok"] is False
    assert no_size[0]["code"] == "600519"


def test_sbbr_strategy_scope_doc_mentions_single():
    """路由 docstring / 错误文案应声明 single 范围。"""
    import inspect
    from backend_api.stock import stock_screening_routes as routes

    doc = inspect.getdoc(routes.get_sbbr_strategy) or ""
    assert "single" in doc
    assert "个股" in doc or "stock_code" in doc
    assert "trace_only" in doc
    assert "不调用策略现算" in doc


def test_sbbr_resolve_trace_asof_dates_uses_trace_max(monkeypatch):
    """只读路径按 sbbr_signal_trace 对齐日期，不扫行情全表。"""
    from datetime import date

    from backend_api.stock import stock_screening_routes as routes

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *args, **kwargs):
            return self

        def scalar(self):
            return self.value

    class _DB:
        def query(self, *args, **kwargs):
            return _Q(date(2026, 11, 19))

    trade_date, data_max = routes._sbbr_resolve_trace_asof_dates(
        _DB(), config_id=1, requested_date=None
    )
    assert trade_date == "2026-11-19"
    assert data_max == "2026-11-19"

    trade_date2, data_max2 = routes._sbbr_resolve_trace_asof_dates(
        _DB(), config_id=1, requested_date="2026-11-20"
    )
    assert trade_date2 == "2026-11-19"
    assert data_max2 == "2026-11-19"


def test_sbbr_filter_trace_rows_keeps_pool_and_skips_others():
    """已采集信号按股票池、板型、做小/筑底过滤，不依赖现算。"""
    from backend_api.stock import stock_screening_routes as routes

    rows = [
        {"code": "600000", "bottom_matched": True, "size_ok": True, "entry_signal": True},
        {"code": "300001", "bottom_matched": True, "size_ok": True, "entry_signal": False},
        {"code": "688001", "bottom_matched": False, "size_ok": True, "entry_signal": False},
        {"code": "000001", "bottom_matched": True, "size_ok": False, "entry_signal": False},
    ]
    pooled = routes._sbbr_filter_trace_rows(
        rows,
        stock_codes=["300001", "000001"],
        seg_list=[],
        require_bottom=True,
        require_size=True,
        effective_max=200,
    )
    assert [r["code"] for r in pooled] == ["300001"]

    by_board = routes._sbbr_filter_trace_rows(
        rows,
        stock_codes=None,
        seg_list=["KCB"],
        require_bottom=False,
        require_size=False,
        effective_max=200,
    )
    assert [r["code"] for r in by_board] == ["688001"]

    assert "没有已采集" in routes._sbbr_trace_empty_message(
        "market", entry_only=False, narrowed=False
    )
    assert "仅入场" in routes._sbbr_trace_empty_message(
        "single", entry_only=True, narrowed=True
    )
