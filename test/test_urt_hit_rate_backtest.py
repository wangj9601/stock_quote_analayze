# -*- coding: utf-8 -*-
"""URT 命中率回测：对齐 GMS signal_hit_rate，仅统计观察期是否触达目标。"""

import os
import sys
from unittest.mock import MagicMock

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.urt import backtest_runner as br


@pytest.fixture
def mock_db():
    return MagicMock()


def _patch_hit_rate_backtest(monkeypatch, *, future_bars, signal_date="2024-01-02"):
    monkeypatch.setattr(br, "_trading_dates", lambda _db, _s, _e: [signal_date])
    monkeypatch.setattr(br, "_future_bars", lambda _db, _c, _d, _n: list(future_bars))
    monkeypatch.setattr(
        br,
        "query_buy_signals_for_date",
        lambda _db, trade_date, config_id, min_score: [
            {
                "code": "000001",
                "name": "测试",
                "signal_date": trade_date,
                "score": 80,
            }
        ],
    )
    monkeypatch.setattr(br, "_ensure_trace_for_backtest_range", lambda *a, **k: {})
    monkeypatch.setattr(br.URTConfigManager, "ensure_default_row", lambda self, db: None)
    monkeypatch.setattr(
        br.URTConfigManager,
        "get_config",
        lambda self, sid, db=None: {"min_score": 70, "risk": {}},
    )
    monkeypatch.setattr(
        br.URTConfigManager,
        "merge_overrides",
        lambda self, cfg, **k: cfg,
    )


def test_hit_rate_mode_only_records_target_hit(mock_db, monkeypatch):
    """命中率模式不输出出场/盈亏字段，summary 不含 win_rate。"""
    future = [
        {"date": "2024-01-03", "open": 100.0, "high": 106.0, "low": 99.0, "close": 104.0},
    ]
    _patch_hit_rate_backtest(monkeypatch, future_bars=future)

    result = br.run_urt_backtest(
        mock_db,
        start_date="2024-01-01",
        end_date="2024-01-31",
        target_pct=0.05,
        horizon_days=1,
        use_trace=True,
        exit_mode="hit_rate",
    )
    summary = result["summary"]
    assert summary["backtest_mode"] == "signal_hit_rate"
    assert summary["hit_count"] == 1
    assert summary["hit_rate"] == 1.0
    assert "win_rate" not in summary
    assert "avg_pnl_pct" not in summary
    assert summary["avg_max_gain_pct"] == pytest.approx(6.0, rel=1e-3)

    row = result["details"][0]
    assert row["hit_target"] is True
    assert row["max_high"] == pytest.approx(106.0)
    assert "exit_date" not in row
    assert "pnl_pct" not in row
    assert "horizon_pnl_pct" not in row
    assert row["observation_end_date"] == "2024-01-03"


def test_hit_rate_mode_miss_target(mock_db, monkeypatch):
    future = [
        {"date": "2024-01-03", "open": 100.0, "high": 103.0, "low": 99.0, "close": 101.0},
    ]
    _patch_hit_rate_backtest(monkeypatch, future_bars=future)

    result = br.run_urt_backtest(
        mock_db,
        start_date="2024-01-01",
        end_date="2024-01-31",
        target_pct=0.05,
        horizon_days=1,
        use_trace=True,
        exit_mode="hit_rate",
    )
    assert result["summary"]["hit_count"] == 0
    assert result["details"][0]["hit_target"] is False
