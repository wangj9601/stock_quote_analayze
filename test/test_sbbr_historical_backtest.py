"""SBBR 历史回测：范围校验、summary 字段、列表摘要兼容。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend_api.admin.sbbr_admin_routes import BacktestCreateReq, _build_backtest_config, _validate_backtest_scope
from backend_core.strategies.sbbr.backtest_runner import _hit_rate, _simulate_trades
from backend_core.strategies.sbbr.backtest_storage import SBBRBacktestStorage
from backend_core.strategies.sbbr.config import get_default_sbbr_config


class _FakeLoader:
    def load_bars(self, code, end_date=None, limit=120):
        bars = []
        p = 10.0
        for i in range(80):
            if i > 40:
                p *= 1.02
            bars.append(
                {
                    "date": f"2024-06-{min(i + 1, 28):02d}" if i < 28 else f"2024-07-{(i - 27):02d}",
                    "open": p,
                    "high": p * 1.03,
                    "low": p * 0.98,
                    "close": p,
                    "volume": 100,
                    "turnover_rate": 5,
                }
            )
        bars[40]["date"] = "2024-06-15"
        return bars


def test_validate_scope_rejects_industry_without_codes():
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="industry_board",
        industry_board_codes=[],
    )
    with pytest.raises(HTTPException) as ei:
        _validate_backtest_scope(body)
    assert ei.value.status_code == 400
    assert "行业" in str(ei.value.detail)


def test_validate_scope_rejects_stocks_without_codes():
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="stocks",
        stock_codes=[],
    )
    with pytest.raises(HTTPException) as ei:
        _validate_backtest_scope(body)
    assert ei.value.status_code == 400


def test_validate_scope_market_ok():
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="market",
    )
    assert _validate_backtest_scope(body) == "market"


def test_validate_scope_explicit_stock_pool_skips_board_required():
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="industry_board",
        stock_pool=["000001"],
    )
    assert _validate_backtest_scope(body) == "industry_board"


def test_build_market_config_no_codes(monkeypatch):
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="market",
        universe_limit=40,
    )

    class _DummyDb:
        pass

    cfg = _build_backtest_config(_DummyDb(), body)
    assert cfg["stock_pool_mode"] == "market"
    assert cfg["stock_pool"] is None
    assert cfg["scope_meta"]["source"] == "build_size_universe"
    assert cfg["scope_meta"]["universe_limit"] == 40


def test_build_stocks_config_resolves_pool(monkeypatch):
    body = BacktestCreateReq(
        start_date="2024-01-01",
        end_date="2024-06-01",
        stock_pool_mode="stocks",
        stock_codes=["000001", "600519"],
    )

    def _fake_resolve(db, **kwargs):
        return {
            "codes": ["000001", "600519"],
            "board_codes": [],
            "boards_by_code": {},
            "mode": "stocks",
            "scope_meta": {
                "stock_pool_mode": "stocks",
                "board_codes": [],
                "stock_count": 2,
                "universe_limit": None,
            },
        }

    monkeypatch.setattr(
        "backend_core.strategies.double_bottom.universe.resolve_stock_pool",
        _fake_resolve,
    )
    cfg = _build_backtest_config(object(), body)
    assert cfg["stock_pool"] == ["000001", "600519"]
    assert cfg["scope_meta"]["stock_count"] == 2
    assert cfg["scope_meta"]["source"] == "resolve_stock_pool"


def test_hit_rate_summary_has_entry_count():
    samples = [
        {"code": "000001", "date": "2024-06-15", "close": 10.0, "defense_low": 9.0},
        {"code": "000002", "date": "2024-06-15", "close": 10.0, "defense_low": 9.0},
    ]
    summary = _hit_rate(_FakeLoader(), samples, horizon=30, target_pct=0.2, cfg=get_default_sbbr_config())
    assert summary["entry_count"] == 2
    assert "hit_count" in summary
    assert "hit_rate" in summary


def test_simulate_trades_summary_has_entry_count():
    samples = [
        {"code": "000001", "date": "2024-06-15", "close": 10.0, "defense_low": 9.0},
    ]
    summary = _simulate_trades(
        _FakeLoader(), samples, horizon=30, target_pct=0.2, cfg=get_default_sbbr_config()
    )
    assert summary["entry_count"] == 1
    assert "total_trades" in summary
    assert "win_rate" in summary


def test_summary_list_fields_compat_old_total_samples():
    fields = SBBRBacktestStorage._summary_list_fields(
        {"total_samples": 12, "hit_count": 5, "hit_rate": 0.4}
    )
    assert fields["entry_count"] == 12
    assert fields["hit_count"] == 5
    assert fields["hit_rate"] == 0.4


def test_summary_list_fields_prefers_entry_count():
    fields = SBBRBacktestStorage._summary_list_fields(
        {"entry_count": 20, "total_samples": 18, "hit_count": 7, "hit_rate": 0.35}
    )
    assert fields["entry_count"] == 20
    assert fields["total_samples"] == 18
