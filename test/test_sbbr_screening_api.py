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
