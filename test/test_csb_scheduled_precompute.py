"""CSB 每日预计算：买点按入库地板分（默认 50）落库；选股 min_score 只在读侧生效。"""

from backend_core.strategies.csb import scheduled_precompute as sp


def test_resolve_storage_floor_default_and_overrides(monkeypatch):
    monkeypatch.delenv("CSB_PRECOMPUTE_MIN_SCORE", raising=False)
    assert sp.resolve_csb_precompute_storage_min_score() == 50.0
    assert sp.resolve_csb_precompute_storage_min_score({"precompute_min_score": 55}) == 55.0
    monkeypatch.setenv("CSB_PRECOMPUTE_MIN_SCORE", "40")
    assert sp.resolve_csb_precompute_storage_min_score({"precompute_min_score": 55}) == 40.0


def test_filter_csb_rows_for_storage_keeps_entry_above_floor():
    rows = [
        {"code": "1", "entry_signal": True, "score": 40},
        {"code": "2", "buy_signal": True, "score": 55},
        {"code": "3", "entry_signal": False, "score": 90},
        {"code": "4", "entry_signal": True, "score": None},
        {"code": "5", "entry_signal": True, "score": 50},
    ]
    kept = sp.filter_csb_rows_for_storage(rows, min_score=50)
    assert [r["code"] for r in kept] == ["2", "5"]


def test_cfg_with_precompute_storage_floor_keeps_selection_params(monkeypatch):
    monkeypatch.delenv("CSB_PRECOMPUTE_MIN_SCORE", raising=False)
    cfg = {"min_score": 80, "channel": {"squeeze_days": 15}, "precompute_min_score": 50}
    scan = sp.cfg_with_precompute_storage_floor(cfg)
    assert scan["min_score"] == 50
    assert scan["channel"]["squeeze_days"] == 15
    assert cfg["min_score"] == 80


def test_daily_precompute_uses_storage_floor_not_selection_min_score(monkeypatch):
    captured = {}

    class _DB:
        def close(self):
            pass

    class _CM:
        def ensure_default_row(self, db):
            return None

        def get_config(self, config_id, db=None):
            return {"min_score": 80, "channel": {"squeeze_days": 15}}

    class _Loader:
        def __init__(self, db):
            pass

        def resolve_effective_trade_date(self, date_s):
            return "2026-11-06"

        def list_a_share_candidates(self, limit=None):
            return [("000001", "平安"), ("000002", "万科"), ("000003", "国农")]

    class _Engine:
        def __init__(self, loader, cfg):
            captured["engine_min_score"] = cfg.get("min_score")

        def screen(self, stocks, *, as_of_end_date=None, require_entry=False, max_results=None):
            captured["require_entry"] = require_entry
            captured["asof"] = as_of_end_date
            assert float(captured["engine_min_score"]) == 50.0
            return [
                {
                    "code": "000001",
                    "name": "平安",
                    "signal_date": as_of_end_date,
                    "entry_signal": True,
                    "buy_signal": True,
                    "score": 82,
                    "signal_type": "CSB_BREAKOUT",
                },
                {
                    "code": "000002",
                    "name": "万科",
                    "signal_date": as_of_end_date,
                    "entry_signal": True,
                    "buy_signal": True,
                    "score": 55,
                    "signal_type": "CSB_PROBE",
                },
            ]

    def _upsert(db, *, config_id, rows):
        captured["rows"] = list(rows)
        captured["config_id"] = config_id
        return len(rows)

    def _mark(db, *, config_id, trade_date, extra=None):
        captured["mark"] = {"config_id": config_id, "trade_date": trade_date, "extra": extra}

    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr("backend_core.strategies.csb.config.CSBConfigManager", _CM)
    monkeypatch.setattr("backend_core.strategies.csb.data_loader.CSBDataLoader", _Loader)
    monkeypatch.setattr("backend_core.strategies.csb.strategy_engine.CSBStrategyEngine", _Engine)
    monkeypatch.setattr("backend_core.strategies.csb.trace_store.upsert_trace_rows", _upsert)
    monkeypatch.setattr("backend_core.strategies.csb.trace_store.mark_date_scanned", _mark)
    monkeypatch.setattr(sp, "resolve_csb_trade_date", lambda db: "2026-11-06")
    monkeypatch.delenv("CSB_PRECOMPUTE_MIN_SCORE", raising=False)

    out = sp.run_csb_precompute_for_config(3)

    assert out["success"] is True
    assert out["storage_min_score"] == 50
    assert out["selection_min_score"] == 80
    assert out["hits"] == 2
    assert out["written"] == 2
    assert captured["require_entry"] is True
    assert captured["engine_min_score"] == 50
    assert [r["code"] for r in captured["rows"]] == ["000001", "000002"]
    assert captured["mark"]["extra"]["storage_min_score"] == 50
    assert captured["mark"]["extra"]["selection_min_score"] == 80
