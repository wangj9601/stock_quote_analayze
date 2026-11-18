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
    captured = {"screens": []}

    class _DB:
        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setenv("ENABLE_SEPA_PRECOMPUTE", "true")
    monkeypatch.setenv("SEPA_BARS_BATCH_SIZE", "1")
    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_universe",
        lambda db, **kwargs: {
            "codes": ["000002", "000001"],
            "names": {"000001": "平安银行", "000002": "万科"},
            "min_avg_amount": 50_000_000,
            "exclude_st": True,
        },
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_momentum_map",
        lambda db, codes, end_date, n_bars=340: {code: float(i) for i, code in enumerate(codes)},
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_bars",
        lambda db, codes, end_date, n_bars=340: {code: [{"close": 1}] for code in codes},
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_margin",
        lambda db, codes, end_date, n_rows=90: {},
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_float_mv",
        lambda db, codes, end_date: {},
    )

    def _screen(bars, **kwargs):
        captured["screens"].append(kwargs)
        stats = kwargs.get("stats")
        if stats is not None:
            stats.update(
                {
                    "universe": len(bars),
                    "trend_pass": len(bars),
                    "vcp_any": len(bars),
                    "forming": len(bars),
                    "breakout": 0,
                    "quiet": 0,
                    "ready": 0,
                    "extended": 0,
                }
            )
        return [
            {"code": code, "vcp": {"status": "forming"}, "score": 1, "tier": "C"}
            for code in bars
        ]

    monkeypatch.setattr("backend_core.analysis.sepa.screener.screen_universe", _screen)
    monkeypatch.setattr(
        "backend_core.analysis.sepa.screener.to_table_rows",
        lambda rows: [
            {"code": r["code"], "vcp_status": "forming", "score": r.get("score") or 1, "tier": "C"}
            for r in rows
        ],
    )

    def _replace(db, **kwargs):
        captured["replace"] = kwargs
        return len(kwargs["rows"])

    monkeypatch.setattr("backend_core.analysis.sepa.trace_store.replace_trace", _replace)
    out = run_sepa_precompute(trade_date="2026-11-11")
    assert out["success"] is True
    assert out["written"] == 2
    assert len(captured["screens"]) == 2
    assert all(call["include_forming"] is True for call in captured["screens"])
    assert all(call["include_extended"] is True for call in captured["screens"])
    assert all(call["top"] >= 1000 for call in captured["screens"])
    assert all(call["ranks"] for call in captured["screens"])
    assert {row["vcp_status"] for row in captured["replace"]["rows"]} == {"forming"}
    assert captured["replace"]["universe"] == 2


def test_scan_pool_matches_single_pass(monkeypatch):
    """分批扫描的名单和漏斗必须与一次装入 screen_universe 相同。"""
    import importlib.util
    from pathlib import Path

    from backend_core.analysis.sepa.scheduled_precompute import scan_sepa_pool
    from backend_core.analysis.sepa.screener import screen_universe, to_table_rows

    path = Path(__file__).with_name("test_sepa.py")
    spec = importlib.util.spec_from_file_location("sepa_fixtures", path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)

    bars = {
        "000010": fixtures._vcp_bars(seed=11),
        "000001": fixtures._vcp_bars(seed=7),
        "000003": fixtures._uptrend_bars(),
        "000002": fixtures._downtrend_bars(),
    }
    monkeypatch.setenv("SEPA_BARS_BATCH_SIZE", "1")
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_universe",
        lambda db, **kwargs: {
            "codes": list(bars),
            "names": {},
            "min_avg_amount": 50_000_000,
            "exclude_st": True,
        },
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_bars",
        lambda db, codes, end_date, n_bars=340: {code: bars[code] for code in codes if code in bars},
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_margin",
        lambda db, codes, end_date, n_rows=90: {},
    )
    monkeypatch.setattr(
        "backend_core.analysis.sepa.loaders.load_float_mv",
        lambda db, codes, end_date: {},
    )

    scanned = scan_sepa_pool(
        object(),
        end_date="2026-11-11",
        min_avg_amount=50_000_000,
        top=100,
        include_forming=True,
        include_extended=True,
    )
    ordered = {code: bars[code] for code in sorted(bars)}
    full = to_table_rows(
        screen_universe(ordered, top=100, include_forming=True, include_extended=True)
    )
    assert [row["code"] for row in scanned["rows"]] == [row["code"] for row in full]
    assert [row["vcp_status"] for row in scanned["rows"]] == [row["vcp_status"] for row in full]
    assert [row["score"] for row in scanned["rows"]] == [row["score"] for row in full]
    assert scanned["universe"] == 4
