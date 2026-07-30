# -*- coding: utf-8 -*-
"""GMS 选股快路径：预计算成功后直接读 trace，跳过全市场建池。"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms import frontend_interface as gfi


def _fake_trace_row(code="000001", market_type="CN", score_total=80.0):
    return SimpleNamespace(
        code=code,
        date="2026-07-29",
        market_type=market_type,
        score_total=score_total,
        score_accumulation=40.0,
        score_momentum=40.0,
        left_buy_signal=True,
        right_buy_signal=False,
        buy_type="左侧",
        signal_strength=0.8,
        sell_signal=False,
        delta=1.0,
        d=10.0,
        ratio_d20=0.1,
        ratio_d1=0.05,
        fz_ratio=0.5,
        volume_ratio=1.2,
        instant_deviation=0.2,
        rising_days=2,
        falling_days=0,
        score_acc_fz=10,
        score_acc_balance=10,
        score_acc_volume=10,
        score_mom_ratio_d1=10,
        score_mom_deviation=10,
        score_mom_volume=10,
        acc_fz_judge="",
        acc_balance_judge="",
        acc_volume_judge="",
        mom_ratio_d1_judge="",
        mom_deviation_judge="",
        mom_volume_judge="",
        accumulation_grade="A",
        momentum_grade="B",
        risk_tags=[],
        score_detail={
            "ratio_d": 0.08,
            "avg_volume_20d": 1000,
            "current_volume": 1200,
            "score_total": score_total,
        },
    )


def test_trace_row_merges_stored_score_detail():
    row = _fake_trace_row()
    out = gfi._trace_row_to_result(row)
    assert out["score_detail"]["ratio_d"] == 0.08
    assert out["avg_volume_20d"] == 1000
    assert out["ratio_d"] == 0.08


def test_fast_path_skips_stock_pool_when_precompute_ok(monkeypatch):
    db = MagicMock()
    iface = gfi.GMSFrontendInterface(db, {"scoring": {}}, config_id=1)
    iface.use_trace = True
    iface.set_selection_config(min_score=0, max_results=10000)

    monkeypatch.setattr(iface, "_precompute_succeeded", lambda *_a, **_k: True)
    monkeypatch.setattr(
        iface,
        "_load_traces_for_market",
        lambda *_a, **_k: [gfi._trace_row_to_result(_fake_trace_row())],
    )

    called = {"pool": False}

    def _boom(*_a, **_k):
        called["pool"] = True
        raise AssertionError("should not build stock pool on fast path")

    monkeypatch.setattr(iface, "_get_stock_pool", _boom)

    rows, meta = iface.get_selection_results(
        "2026-07-29",
        stock_pool=None,
        market="cn",
        trace_only=False,
        return_meta=True,
    )
    assert len(rows) == 1
    assert meta.get("fast_path") == "trace_market"
    assert meta.get("computed_count") == 0
    assert meta.get("trace_complete") is True
    assert called["pool"] is False


def test_precompute_job_still_builds_pool_when_not_ready(monkeypatch):
    """预计算任务（trace_only=False 且无成功记录）必须走建池路径。"""
    db = MagicMock()
    iface = gfi.GMSFrontendInterface(db, {"scoring": {}}, config_id=1)
    iface.use_trace = True

    monkeypatch.setattr(iface, "_precompute_succeeded", lambda *_a, **_k: False)
    monkeypatch.setattr(iface, "_load_traces_for_market", lambda *_a, **_k: [])
    monkeypatch.setattr(iface, "_get_stock_pool", lambda *_a, **_k: ["000001"])

    # 短路后续 ORM：无 trace、不触发计算
    with patch.object(iface, "use_trace", True):
        from backend_api import models as m

        q = MagicMock()
        q.filter.return_value.all.return_value = []
        db.query.return_value = q

        rows, meta = iface.get_selection_results(
            "2026-07-29",
            stock_pool=None,
            market="cn",
            trace_only=False,
            return_meta=True,
        )
    assert meta.get("fast_path") is None or meta.get("fast_path") != "trace_market"
    assert meta.get("requested_count") == 1


def test_batch_resolve_gms_stock_names():
    from backend_api.stock import stock_screening_routes as routes

    db = MagicMock()

    class _R:
        def __init__(self, code, name):
            self.code = code
            self.name = name

    # query(Model.code, Model.name).filter(...) 按实体类名区分
    def _query(*entities):
        m = MagicMock()
        ent0 = entities[0] if entities else None
        parent = getattr(ent0, "class_", None) or ent0
        name = getattr(parent, "__name__", str(parent))
        if "HK" in name:
            m.filter.return_value = [_R("00700", "腾讯")]
        elif "Fund" in name:
            m.filter.return_value = [_R("510300", "沪深300ETF")]
        else:
            m.filter.return_value = [_R("000001", "平安银行")]
        return m

    db.query.side_effect = _query
    names = routes._batch_resolve_gms_stock_names(
        db,
        [("000001", "CN"), ("00700", "HK"), ("510300", "ETF")],
    )
    assert names["000001"] == "平安银行"
    assert names["00700"] == "腾讯"
    assert names["510300"] == "沪深300ETF"
