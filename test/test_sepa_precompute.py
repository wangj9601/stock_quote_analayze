# -*- coding: utf-8 -*-
"""SEPA 买点预计算：过滤口径、覆盖判断、落库替换、采集节点。"""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend_api.models import Base, SEPASignalScan, SEPASignalTrace
from backend_core.analysis.sepa.screener import filter_table_rows
from backend_core.analysis.sepa.scheduled_precompute import run_sepa_precompute
from backend_core.analysis.sepa.trace_store import cache_covers_request, replace_trace
from backend_core.data_collectors.workflow.adapters import exec_sepa_cn
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.node_registry import get_node


def _rows():
    return [
        {"code": "000001", "vcp_status": "breakout", "score": 90, "tier": "A"},
        {"code": "000002", "vcp_status": "ready", "score": 10, "tier": "A"},
        {"code": "000003", "vcp_status": "forming", "score": 80, "tier": "C"},
        {"code": "000004", "vcp_status": "extended", "score": 70, "tier": "C"},
        {"code": "000005", "vcp_status": "quiet", "score": 40, "tier": "B"},
    ]


def test_filter_table_rows_default_is_actionable_ready_first():
    kept = filter_table_rows(_rows(), top=10)
    assert [r["code"] for r in kept] == ["000002", "000005", "000001"]


def test_filter_table_rows_can_include_watch_statuses():
    kept = filter_table_rows(_rows(), top=10, include_forming=True, tiers=["C"])
    assert [r["code"] for r in kept] == ["000003"]


def test_cache_covers_only_same_full_pool():
    pool = {"min_avg_amount": 50_000_000}
    assert cache_covers_request(pool, limit_codes=0, min_avg_amount=50_000_000)
    assert cache_covers_request(pool, limit_codes=0, min_avg_amount=50_000_000.4)
    assert not cache_covers_request(pool, limit_codes=200, min_avg_amount=50_000_000)
    assert not cache_covers_request(pool, limit_codes=0, min_avg_amount=0)
    assert not cache_covers_request({}, limit_codes=0, min_avg_amount=50_000_000)


def test_replace_trace_overwrites_same_day():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[SEPASignalScan.__table__, SEPASignalTrace.__table__])
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        replace_trace(
            db,
            trade_date="2026-11-11",
            rows=_rows(),
            universe=4000,
            funnel={"ready": 1, "forming": 1},
            pool={"min_avg_amount": 50_000_000, "exclude_st": True},
        )
        replace_trace(
            db,
            trade_date="2026-11-11",
            rows=[_rows()[1]],
            universe=4000,
            funnel={"ready": 1},
            pool={"min_avg_amount": 50_000_000},
        )
        assert db.query(SEPASignalTrace).count() == 1
        scan = db.query(SEPASignalScan).one()
        assert scan.trade_date == date(2026, 11, 11)
        assert scan.hit_count == 1
        assert scan.funnel["ready"] == 1
        assert db.query(SEPASignalTrace).one().vcp_status == "ready"
    finally:
        db.close()


def test_sepa_node_registered_with_trade_date():
    node = get_node("sepa_signals_cn")
    assert node is not None
    assert "SEPA" in node.name
    props = (node.param_schema or {}).get("properties") or {}
    assert props["trade_date"]["format"] == "date"


def test_exec_sepa_uses_explicit_trade_date(monkeypatch):
    captured = {}

    def _fake(*, trade_date=None, **kwargs):
        captured["trade_date"] = trade_date
        return {"success": True, "skipped": False, "trade_date": trade_date, "written": 2}

    monkeypatch.setattr(
        "backend_core.analysis.sepa.scheduled_precompute.run_sepa_precompute",
        _fake,
    )
    ctx = WorkflowContext(
        run_id="t",
        workflow_id=1,
        trigger_source="manual",
        node_params={"trade_date": "2026-11-10"},
    )
    result = exec_sepa_cn(ctx)
    assert result.success is True
    assert result.skipped is False
    assert captured["trade_date"] == "2026-11-10"


def test_exec_sepa_without_date_lets_job_pick_latest(monkeypatch):
    captured = {}

    def _fake(*, trade_date=None, **kwargs):
        captured["trade_date"] = trade_date
        return {"success": True, "written": 0}

    monkeypatch.setattr(
        "backend_core.analysis.sepa.scheduled_precompute.run_sepa_precompute",
        _fake,
    )
    ctx = WorkflowContext(run_id="t", workflow_id=1, trigger_source="cron", trade_date=date(2026, 11, 12))
    result = exec_sepa_cn(ctx)
    assert result.success is True
    assert captured["trade_date"] is None


def test_precompute_stores_every_morphology(monkeypatch):
    captured = {}

    class _DB:
        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setenv("ENABLE_SEPA_PRECOMPUTE", "true")
    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.fetch_inputs",
        lambda db, **kwargs: {
            "bars": {"000001": []},
            "margin": {},
            "float_mv": {},
            "names": {"000001": "平安银行"},
            "codes": ["000001"],
            "pool": {"min_avg_amount": 50_000_000},
        },
    )

    def _screen(bars, **kwargs):
        captured["screen"] = kwargs
        return {"rows": [{"code": "000001", "vcp": {"status": "forming"}}], "stats": {"forming": 1}}

    monkeypatch.setattr("backend_core.analysis.sepa.screen_report", _screen)
    monkeypatch.setattr(
        "backend_core.analysis.sepa.to_table_rows",
        lambda rows: [{"code": "000001", "vcp_status": "forming", "score": 1, "tier": "C"}],
    )

    def _replace(db, **kwargs):
        captured["replace"] = kwargs
        return 1

    monkeypatch.setattr("backend_core.analysis.sepa.trace_store.replace_trace", _replace)
    out = run_sepa_precompute(trade_date="2026-11-11")
    assert out["success"] is True
    assert out["written"] == 1
    assert captured["screen"]["include_forming"] is True
    assert captured["screen"]["include_extended"] is True
    assert captured["screen"]["top"] >= 1000
    assert captured["replace"]["rows"][0]["vcp_status"] == "forming"
