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


def test_board_segment_filter_reuse():
    from backend_api.utils.cn_listed_board_filter import filter_stock_codes_by_board_segment

    codes = ["600000", "000001", "300001", "688001", "002001"]
    main = filter_stock_codes_by_board_segment(codes, "MAIN")
    assert "600000" in main and "000001" in main
    assert "300001" not in main and "688001" not in main
    cyb = filter_stock_codes_by_board_segment(codes, "CYB")
    assert cyb == ["300001"]
    kcb = filter_stock_codes_by_board_segment(codes, "KCB")
    assert kcb == ["688001"]
    sme = filter_stock_codes_by_board_segment(codes, "SZ_SME")
    assert sme == ["002001"]


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
