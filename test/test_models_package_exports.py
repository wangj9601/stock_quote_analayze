# -*- coding: utf-8 -*-
"""确保热路径模型已静态导出，避免启动时反复 force_reload models.py。"""

from __future__ import annotations


REQUIRED_EXPORTS = (
    "CSBStrategyConfig",
    "CSBSignalTrace",
    "EnvSyncJob",
    "StockAdjFactor",
    "StockFinaIndicator",
    "StockFundFlowEmDaily",
    "StockMarginDaily",
    "RSRatings",
    "BoardFundFlowDaily",
    "ZhabStrategyConfig",
    "ZhabSignalTrace",
)


def test_hot_path_models_are_statically_exported():
    import backend_api.models as models_pkg

    for name in REQUIRED_EXPORTS:
        assert name in models_pkg.__dict__, f"{name} 未静态导出到 backend_api.models"
        assert getattr(models_pkg, name) is not None, f"{name} 导出为 None"


def test_getattr_does_not_force_reload_by_default(monkeypatch):
    import backend_api.models as models_pkg

    calls = {"force": 0}
    orig = models_pkg._load_models_py_module

    def wrapped(force_reload: bool = False):
        if force_reload:
            calls["force"] += 1
        return orig(force_reload=force_reload)

    monkeypatch.setattr(models_pkg, "_load_models_py_module", wrapped)
    # 临时移出已导出符号，强制走 __getattr__
    name = "StockAdjFactor"
    held = models_pkg.__dict__.pop(name)
    try:
        got = getattr(models_pkg, name)
        assert got is held
    finally:
        models_pkg.__dict__[name] = held
    assert calls["force"] == 0
