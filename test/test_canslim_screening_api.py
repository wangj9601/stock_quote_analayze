"""CAN SLIM 选股 API 冒烟：路由可导入、签名与配置接口。"""

import inspect


def test_import_canslim_package():
    from backend_core.strategies.canslim import (
        CanSlimEngine,
        CanSlimFrontendInterface,
        get_default_canslim_config,
    )

    assert get_default_canslim_config()["L"]["rs_rating_min"] == 80
    assert CanSlimEngine is not None
    assert CanSlimFrontendInterface is not None


def test_canslim_route_signature():
    from backend_api.stock import stock_screening_routes as routes

    sig = inspect.signature(routes.get_canslim_strategy)
    params = set(sig.parameters)
    assert "asof" in params
    assert "market_filter" in params
    assert "rs_min" in params
    assert "stock_code" in params
    assert "db" in params


def test_canslim_routes_registered():
    from backend_api.stock.stock_screening_routes import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert any(p and p.endswith("/canslim") for p in paths)
    assert any(p and "canslim/config" in (p or "") for p in paths)


def test_workflow_nodes_registered():
    from backend_core.data_collectors.workflow.node_registry import NODE_DEFS

    keys = {n.key for n in NODE_DEFS}
    assert "fina_indicator_cn" in keys
    assert "index_daily_cn" in keys


def test_permission_registry_has_canslim():
    from backend_api.permission_registry_data import PERMISSION_REGISTRY

    codes = {p["code"] for p in PERMISSION_REGISTRY}
    assert "channel.screening.tab.canslim" in codes
    assert "channel.screening.tab.canslim.btn.refresh" in codes
