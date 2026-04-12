"""GMS 回测：交易回测分支与默认命中率回归。"""

import os
import sys

import pytest
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms import backtest_runner as br


def test_trade_simulation_stop_loss_priority(monkeypatch):
    """同一根K线止盈止损同时触发时，按约定先止损。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02"])
    monkeypatch.setattr(br, "_get_entry_open_next_day_cn", lambda _db, _c, _d: 100.0)
    monkeypatch.setattr(
        br,
        "_get_future_ohlc_cn",
        lambda _db, _c, _d, _n: [
            {"date": "2024-01-03", "open": 100.0, "high": 110.0, "low": 95.0, "close": 106.0},
            {"date": "2024-01-04", "open": 106.0, "high": 108.0, "low": 101.0, "close": 107.0},
        ],
    )
    monkeypatch.setattr(br, "_get_observation_window_end_cn", lambda _db, _c, _d, _n: "2024-01-04")

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        return [
            {
                "code": "000001",
                "left_buy_signal": True,
                "right_buy_signal": False,
                "buy_type": "左侧",
                "score_total": 88,
            }
        ]

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    result = br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="cn",
        backtest_type="trade_simulation",
        target_pct=0.05,
        stop_loss_pct=0.02,
        commission_bps=10,
        slippage_bps=5,
        trail_stop_mode="percent",
        trail_pct=1.0,
        breakeven_trigger_r=999,
        profit_lock_trigger_r=999,
        partial_take_profit_r=999,
        partial_take_ratio=0,
    )

    assert result["summary"]["backtest_type"] == "trade_simulation"
    assert result["summary"]["total_trades"] == 1
    assert len(result["details"]) == 1
    row = result["details"][0]
    assert row["exit_reason"] == "止损"
    assert row["exit_date"] == "2024-01-03"
    assert row["hit"] is True
    assert row["pnl_pct"] < 0


def test_trade_simulation_trailing_stop_and_partial_take(monkeypatch):
    """利润奔跑：先触发分批止盈，后由回撤触发移动止损。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02"])
    monkeypatch.setattr(br, "_get_entry_open_next_day_cn", lambda _db, _c, _d: 100.0)
    monkeypatch.setattr(
        br,
        "_get_future_ohlc_cn",
        lambda _db, _c, _d, _n: [
            {"date": "2024-01-03", "open": 100.0, "high": 108.0, "low": 99.0, "close": 107.0},
            {"date": "2024-01-04", "open": 107.0, "high": 113.0, "low": 108.0, "close": 112.0},
            {"date": "2024-01-05", "open": 112.0, "high": 112.5, "low": 103.0, "close": 104.0},
        ],
    )
    monkeypatch.setattr(br, "_get_observation_window_end_cn", lambda _db, _c, _d, _n: "2024-01-05")

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        return [{"code": "000001", "left_buy_signal": True, "score_total": 90}]

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    result = br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="cn",
        backtest_type="trade_simulation",
        target_pct=0.08,
        stop_loss_pct=0.02,
        trail_stop_mode="percent",
        trail_pct=0.06,
        partial_take_profit_r=1.0,
        partial_take_ratio=0.4,
    )
    row = result["details"][0]
    assert row["partial_take_profit_applied"] is True
    assert row["exit_reason"] in ("止损", "时间出场")
    assert row["pnl_pct"] > 0
    assert result["summary"]["pnl_p80"] >= result["summary"]["pnl_p50"]


def test_default_backtest_type_keeps_hit_rate_logic(monkeypatch):
    """不传 backtest_type 时仍走原命中率逻辑。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02"])
    monkeypatch.setattr(br, "_get_entry_open_next_day_cn", lambda _db, _c, _d: 100.0)
    monkeypatch.setattr(
        br,
        "_get_future_ohlc_cn",
        lambda _db, _c, _d, _n: [{"date": "2024-01-03", "open": 100.0, "high": 106.0, "low": 99.0, "close": 104.0}],
    )
    monkeypatch.setattr(br, "_get_observation_window_end_cn", lambda _db, _c, _d, _n: "2024-01-03")

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        return [{"code": "000001", "left_buy_signal": True, "score_total": 75}]

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    result = br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="cn",
        target_pct=0.05,
    )

    summary = result["summary"]
    assert "hit_rate" in summary
    assert "total_trades" not in summary
    assert summary["hit_count"] == 1
    assert summary["hit_rate"] == 1.0


def test_trade_simulation_position_fraction(monkeypatch):
    """单笔仓位：明细 portfolio_pnl_pct = 仓位 × 单笔收益率；summary 记录仓位比例。"""
    db = MagicMock()
    monkeypatch.setattr(br, "_get_trading_dates_cn", lambda _db, _s, _e: ["2024-01-02"])
    monkeypatch.setattr(br, "_get_entry_open_next_day_cn", lambda _db, _c, _d: 100.0)
    monkeypatch.setattr(
        br,
        "_get_future_ohlc_cn",
        lambda _db, _c, _d, _n: [
            {"date": "2024-01-03", "open": 100.0, "high": 106.0, "low": 99.0, "close": 104.0},
        ],
    )
    monkeypatch.setattr(br, "_get_observation_window_end_cn", lambda _db, _c, _d, _n: "2024-01-03")

    def fake_get_selection_results(self, date=None, stock_pool=None, market=None, **kwargs):
        return [{"code": "000001", "left_buy_signal": True, "score_total": 75}]

    monkeypatch.setattr(br.GMSFrontendInterface, "get_selection_results", fake_get_selection_results)

    r = br.run_gms_backtest(
        db,
        "2024-01-01",
        "2024-01-31",
        market="cn",
        backtest_type="trade_simulation",
        position_fraction=0.4,
        target_pct=0.05,
        trail_stop_mode="percent",
        trail_pct=1.0,
        breakeven_trigger_r=999,
        profit_lock_trigger_r=999,
        partial_take_profit_r=999,
        partial_take_ratio=0,
    )
    row = r["details"][0]
    assert row["position_fraction"] == 0.4
    assert row["portfolio_pnl_pct"] == pytest.approx(0.4 * row["pnl_pct"], rel=1e-5)
    assert r["summary"]["position_fraction"] == 0.4
    s = r["summary"]
    assert "approx_annual_return_simple" in s
    assert "avg_portfolio_pnl_per_trade" in s
    assert "backtest_calendar_days" in s
    assert s["avg_portfolio_pnl_per_trade"] == pytest.approx(s["total_return_arithmetic"], rel=1e-6)
    assert s["approx_annual_return_simple"] == pytest.approx(
        s["total_return_arithmetic"] * (365.0 / float(s["backtest_calendar_days"])), rel=1e-5
    )
