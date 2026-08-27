# -*- coding: utf-8 -*-
"""URT 生效配置解析与回测任务参数固化。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend_api.admin.urt_admin_routes import BacktestCreateBody, _build_backtest_config
from backend_core.strategies.urt.config import URTConfigManager


def test_resolve_effective_config_id_returns_default_row():
    mgr = URTConfigManager()
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = SimpleNamespace(id=7)
    assert mgr.resolve_effective_config_id(db) == 7


def test_build_backtest_config_pins_effective_id_without_min_score_override():
    body = BacktestCreateBody(
        start_date="2025-01-01",
        end_date="2025-02-01",
        stock_pool_mode="custom",
        stock_pool=["000001"],
        exit_mode="hit_rate",
        min_score=None,
        strategy_config_id=None,
    )
    db = MagicMock()
    with patch("backend_api.admin.urt_admin_routes.URTConfigManager") as Mgr:
        inst = Mgr.return_value
        inst.ensure_default_row = MagicMock()
        inst.resolve_effective_config_id = MagicMock(return_value=3)
        inst.get_config_meta = MagicMock(
            return_value={
                "config_id": 3,
                "effective_config_id": 3,
                "is_effective": True,
                "name": "默认",
                "version_label": "v1",
                "min_score": 72,
                "volume_multiple": 3.0,
                "config_params": {"min_score": 72, "volume_multiple": 3.0, "risk": {}},
            }
        )
        with patch(
            "backend_api.admin.urt_admin_routes._attach_urt_trade_meta",
            side_effect=lambda _db, cfg: cfg,
        ):
            cfg = _build_backtest_config(db, body)

    assert cfg["strategy_config_id"] == 3
    assert cfg["effective_config_id"] == 3
    assert cfg["is_effective_config"] is True
    assert cfg["min_score"] is None
    assert cfg["min_score_override"] is False
    assert cfg["params_diverged"] is False
    assert cfg["package_min_score"] == 72.0


def test_build_backtest_config_marks_diverge_on_min_score_override():
    body = BacktestCreateBody(
        start_date="2025-01-01",
        end_date="2025-02-01",
        stock_pool_mode="custom",
        stock_pool=["000001"],
        exit_mode="hit_rate",
        min_score=70,
        strategy_config_id=3,
    )
    db = MagicMock()
    with patch("backend_api.admin.urt_admin_routes.URTConfigManager") as Mgr:
        inst = Mgr.return_value
        inst.ensure_default_row = MagicMock()
        inst.resolve_effective_config_id = MagicMock(return_value=3)
        inst.get_config_meta = MagicMock(
            return_value={
                "config_id": 3,
                "effective_config_id": 3,
                "is_effective": True,
                "name": "默认",
                "version_label": None,
                "min_score": 72,
                "volume_multiple": 3.0,
                "config_params": {"min_score": 72, "risk": {}},
            }
        )
        with patch(
            "backend_api.admin.urt_admin_routes._attach_urt_trade_meta",
            side_effect=lambda _db, cfg: cfg,
        ):
            cfg = _build_backtest_config(db, body)

    assert cfg["min_score"] == 70.0
    assert cfg["min_score_override"] is True
    assert cfg["params_diverged"] is True
    assert "min_score_override" in cfg["diverge_reasons"]


def test_build_backtest_config_marks_non_effective_version():
    body = BacktestCreateBody(
        start_date="2025-01-01",
        end_date="2025-02-01",
        stock_pool_mode="custom",
        stock_pool=["000001"],
        strategy_config_id=9,
        min_score=None,
    )
    db = MagicMock()
    with patch("backend_api.admin.urt_admin_routes.URTConfigManager") as Mgr:
        inst = Mgr.return_value
        inst.ensure_default_row = MagicMock()
        inst.resolve_effective_config_id = MagicMock(return_value=3)
        inst.get_config_meta = MagicMock(
            return_value={
                "config_id": 9,
                "effective_config_id": 3,
                "is_effective": False,
                "name": "实验",
                "version_label": None,
                "min_score": 70,
                "volume_multiple": 3.0,
                "config_params": {"min_score": 70, "risk": {}},
            }
        )
        with patch(
            "backend_api.admin.urt_admin_routes._attach_urt_trade_meta",
            side_effect=lambda _db, cfg: cfg,
        ):
            cfg = _build_backtest_config(db, body)

    assert cfg["strategy_config_id"] == 9
    assert cfg["params_diverged"] is True
    assert "strategy_config_id_not_effective" in cfg["diverge_reasons"]


def test_frontend_resolve_config_id_defaults_to_effective():
    from backend_api.stock.urt_frontend_routes import _resolve_config_id

    cm = MagicMock()
    cm.ensure_default_row = MagicMock()
    cm.resolve_effective_config_id = MagicMock(return_value=5)
    cm.list_configs = MagicMock(return_value=[{"id": 1}, {"id": 5}])
    db = MagicMock()
    assert _resolve_config_id(db, None, cm) == 5
    assert _resolve_config_id(db, 9, cm) == 9


def test_frontend_config_alignment_meta_marks_non_effective():
    from backend_api.stock.urt_frontend_routes import _config_alignment_meta

    cm = MagicMock()
    cm.resolve_effective_config_id = MagicMock(return_value=3)
    cm.list_configs = MagicMock(
        return_value=[
            {"id": 3, "name": "默认", "is_default": True},
            {"id": 9, "name": "实验", "is_default": False},
        ]
    )
    meta = _config_alignment_meta(cm, MagicMock(), 9)
    assert meta["config_id"] == 9
    assert meta["effective_config_id"] == 3
    assert meta["is_effective_config"] is False
    assert "实验" in meta["config_name"]


def test_frontend_config_alignment_meta_marks_effective():
    from backend_api.stock.urt_frontend_routes import _config_alignment_meta

    cm = MagicMock()
    cm.resolve_effective_config_id = MagicMock(return_value=3)
    cm.list_configs = MagicMock(
        return_value=[{"id": 3, "name": "默认", "is_default": True}]
    )
    meta = _config_alignment_meta(cm, MagicMock(), 3)
    assert meta["is_effective_config"] is True
    assert "默认" in meta["config_name"]


def test_build_backtest_config_gms_watchlist_pool():
    body = BacktestCreateBody(
        start_date="2025-01-01",
        end_date="2025-02-01",
        stock_pool_mode="gms_watchlist",
        exit_mode="hit_rate",
    )
    db = MagicMock()
    with patch("backend_api.admin.urt_admin_routes.URTConfigManager") as Mgr:
        inst = Mgr.return_value
        inst.ensure_default_row = MagicMock()
        inst.resolve_effective_config_id = MagicMock(return_value=3)
        inst.get_config_meta = MagicMock(
            return_value={
                "config_id": 3,
                "effective_config_id": 3,
                "is_effective": True,
                "name": "默认",
                "version_label": "v1",
                "min_score": 72,
                "volume_multiple": 3.0,
                "config_params": {"min_score": 72, "risk": {}},
            }
        )
        with patch(
            "backend_api.admin.urt_admin_routes._distinct_gms_strategy_stock_codes",
            return_value=["000001", "600000"],
        ):
            with patch(
                "backend_api.admin.urt_admin_routes._attach_urt_trade_meta",
                side_effect=lambda _db, cfg: cfg,
            ):
                cfg = _build_backtest_config(db, body)

    assert cfg["stock_pool_mode"] == "gms_watchlist"
    assert cfg["stock_pool"] == ["000001", "600000"]


def test_get_trace_freshness_marks_stale_when_config_newer():
    from datetime import datetime, timedelta

    from backend_core.strategies.urt.trace_store import get_trace_freshness

    older = datetime(2026, 8, 1, 10, 0, 0)
    newer = older + timedelta(hours=2)
    db = MagicMock()

    # first query: URTStrategyConfig.updated_at via scalar chain is not used when we pass updated_at
    # get_trace_freshness queries max(created_at)
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.scalar.return_value = older

    meta = get_trace_freshness(
        db, config_id=3, config_updated_at=newer, code="000001"
    )
    assert meta["stale"] is True
    assert meta["need_recompute"] is True
    assert meta["config_updated_at"] is not None
    assert meta["trace_computed_at"] is not None


def test_get_trace_freshness_fresh_when_trace_after_config():
    from datetime import datetime, timedelta

    from backend_core.strategies.urt.trace_store import get_trace_freshness

    cfg_t = datetime(2026, 8, 1, 10, 0, 0)
    trace_t = cfg_t + timedelta(hours=1)
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.scalar.return_value = trace_t

    meta = get_trace_freshness(db, config_id=3, config_updated_at=cfg_t)
    assert meta["stale"] is False
    assert meta["need_recompute"] is False
