# -*- coding: utf-8 -*-
"""URT 回测因子扁平化、分桶与命中率对照。"""

from backend_core.strategies.urt.backtest_factor_report import (
    assign_score_buckets,
    attach_horizon_metrics,
    build_factor_buckets,
    build_hit_rate_compare,
    flatten_score_factors,
)
from backend_core.strategies.urt.backtest_pdf import build_backtest_detail_html
from backend_core.strategies.urt.backtest_storage import _build_urt_details_csv_bytes


def test_flatten_score_factors_from_score_detail():
    sig = {
        "score": 78,
        "score_detail": {
            "parts": {
                "volume": {"score": 18.5, "volume_multiple": 4.2},
                "yang": {"score": 14.4, "yang_count_5": 4},
                "structure_position": {
                    "score": 12.0,
                    "structure_rr": 2.4,
                    "close": 10.0,
                    "nearest_support": 9.7,
                    "proximity_reason": "near_support",
                },
                "overheat_penalty": {"score": -2.0, "intensity": 0.2, "ret_from_low_n": 0.12},
                "turnover": {"score": 6.0, "turnover_rate": 5.5, "relative": 1.4},
                "ma_bull": {"score": 6.0, "depth": 4},
            }
        },
    }
    out = flatten_score_factors(sig)
    assert out["f_volume"] == 18.5
    assert out["volume_multiple"] == 4.2
    assert out["yang_count_5"] == 4
    assert out["structure_rr"] == 2.4
    assert out["dist_to_support_pct"] == 3.0
    assert out["proximity_reason"] == "near_support"
    assert out["ma_bull_depth"] == 4
    assert out["f_overheat_penalty"] == -2.0


def test_assign_score_buckets_includes_pnl():
    details = [
        {"score": 72, "hit_target": True, "pnl_pct": 4.0, "max_gain_pct": 12.0},
        {"score": 75, "hit_target": False, "pnl_pct": -3.0, "max_gain_pct": 2.0},
        {"score": 82, "hit_target": True, "pnl_pct": 8.0, "max_gain_pct": 20.0},
    ]
    buckets = assign_score_buckets(details)
    low = buckets["[70,80)"]
    assert low["total"] == 2
    assert low["hit"] == 1
    assert low["hit_rate"] == 0.5
    assert low["avg_pnl_pct"] == 0.5
    assert buckets["[80,90)"]["total"] == 1


def test_factor_buckets_volume_multiple():
    details = [
        {"volume_multiple": 3.1, "hit_target": False, "pnl_pct": -2, "max_gain_pct": 1},
        {"volume_multiple": 4.0, "hit_target": True, "pnl_pct": 5, "max_gain_pct": 12},
        {"volume_multiple": 6.0, "hit_target": True, "pnl_pct": 9, "max_gain_pct": 22},
        {"volume_multiple": 5.5, "hit_target": True, "pnl_pct": 7, "max_gain_pct": 18},
    ]
    fac = build_factor_buckets(details)
    vol = fac["volume_multiple"]
    labels = [b["bucket"] for b in vol["bins"]]
    assert "<3.5" in labels
    assert "≥5" in labels
    hi = next(b for b in vol["bins"] if b["bucket"] == "≥5")
    assert hi["total"] == 2
    assert hi["hit_rate"] == 1.0


def test_hit_rate_compare_same_trades():
    details = [
        {
            "hit_target": True,
            "pnl_pct": 3.0,
            "max_gain_pct": 18.0,
            "bars_held": 5,
            "horizon_pnl_pct": 11.0,
        },
        {
            "hit_target": False,
            "pnl_pct": -4.0,
            "max_gain_pct": 2.0,
            "bars_held": 3,
            "horizon_pnl_pct": -1.0,
        },
    ]
    cmpd = build_hit_rate_compare(details, "structure_exit")
    assert cmpd["hit_rate"] == 0.5
    assert cmpd["avg_max_gain_pct"] == 10.0
    assert cmpd["actual"]["avg_pnl_pct"] == -0.5
    assert cmpd["horizon_hold"]["avg_pnl_pct"] == 5.0
    assert cmpd["max_gain_vs_actual_pnl_gap"] == 10.5
    assert cmpd["horizon_vs_actual_pnl_gap"] == 5.5


def test_horizon_metrics_from_future_bars():
    row = {}
    future = [{"date": "2026-01-02", "open": 10, "close": 10}, {"date": "2026-01-03", "open": 11, "close": 12}]
    attach_horizon_metrics(row, future, 10.0)
    assert row["horizon_exit_price"] == 12.0
    assert row["horizon_pnl_pct"] == 20.0


def test_details_csv_includes_factor_headers():
    rows = [
        {
            "code": "000676",
            "name": "智度股份",
            "score": 80,
            "hit_target": True,
            "f_volume": 18.0,
            "volume_multiple": 4.2,
            "horizon_pnl_pct": 9.5,
        }
    ]
    text = _build_urt_details_csv_bytes(rows).decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "量能分" in header
    assert "量能倍数" in header
    assert "满观察期盈亏(%)" in header
    assert "18.0" in text


def test_pdf_html_contains_factor_and_compare_sections():
    html = build_backtest_detail_html(
        {
            "task_id": "abc",
            "name": "t",
            "status": "completed",
            "progress": 100,
            "config": {"exit_mode": "structure_exit"},
            "summary": {
                "total_signals": 2,
                "target_hits": 1,
                "hit_rate": 0.5,
                "win_rate": 0.5,
                "avg_pnl_pct": 3.0,
                "avg_max_gain_pct": 12.0,
                "target_pct": 0.1,
                "exit_mode": "structure_exit",
                "hit_rate_compare": {
                    "note": "同一批成交信号对照",
                    "hit_rate": 0.5,
                    "avg_max_gain_pct": 12.0,
                    "actual": {"avg_pnl_pct": 3.0, "win_rate": 0.5},
                    "horizon_hold": {"avg_pnl_pct": 8.0, "win_rate": 0.5},
                    "max_gain_vs_actual_pnl_gap": 9.0,
                    "horizon_vs_actual_pnl_gap": 5.0,
                },
                "by_factor_bucket": {
                    "volume_multiple": {
                        "label": "量能倍数",
                        "bins": [
                            {
                                "bucket": "≥5",
                                "total": 1,
                                "hit": 1,
                                "hit_rate": 1.0,
                                "win_rate": 1.0,
                                "avg_pnl_pct": 8.0,
                                "avg_max_gain_pct": 20.0,
                            }
                        ],
                    }
                },
            },
        }
    )
    assert "命中率对照" in html
    assert "按信号因子分桶" in html
    assert "量能倍数" in html
    assert "同一批成交信号对照" in html


def test_maybe_start_hit_rate_compare_skips_hit_rate_mode(monkeypatch):
    from backend_core.strategies.urt import backtest_worker

    monkeypatch.setattr(
        backtest_worker.backtest_storage,
        "get_task",
        lambda _tid: {"config": {"exit_mode": "hit_rate"}},
    )
    assert backtest_worker._maybe_start_hit_rate_compare("parent") is None


def test_maybe_start_hit_rate_compare_creates_child(monkeypatch):
    from backend_core.strategies.urt import backtest_worker

    started = []
    monkeypatch.setattr(
        backtest_worker.backtest_storage,
        "get_task",
        lambda _tid: {
            "name": "URT回测_aa",
            "config": {"exit_mode": "structure_exit", "start_date": "2025-01-01"},
        },
    )
    monkeypatch.setattr(
        backtest_worker.backtest_storage,
        "create_task",
        lambda _cfg, name=None: "child-uuid",
    )
    monkeypatch.setattr(backtest_worker.backtest_storage, "patch_task_config", lambda *a, **k: None)
    monkeypatch.setattr(backtest_worker.backtest_storage, "patch_task_summary", lambda *a, **k: None)
    monkeypatch.setattr(backtest_worker, "start_backtest_task", lambda tid: started.append(tid))
    assert backtest_worker._maybe_start_hit_rate_compare("parent-uuid") == "child-uuid"
    assert started == ["child-uuid"]
