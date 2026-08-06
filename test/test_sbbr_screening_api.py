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
