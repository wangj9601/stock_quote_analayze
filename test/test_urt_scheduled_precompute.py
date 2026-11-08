"""URT 每日预计算：低于入库地板分的非买点不落库；扫描占位仍写。"""

from backend_core.strategies.urt import scheduled_precompute as sp


def test_filter_urt_rows_for_storage_keeps_buys_and_floor():
    rows = [
        {"code": "1", "buy_signal": True, "score": 40},
        {"code": "2", "buy_signal": False, "score": 55},
        {"code": "3", "buy_signal": False, "score": 12},
        {"code": "4", "buy_signal": False, "score": None},
    ]
    kept = sp.filter_urt_rows_for_storage(rows, min_score=50)
    assert [r["code"] for r in kept] == ["1", "2"]


def test_daily_precompute_skips_below_storage_floor(monkeypatch):
    captured = {}

    class _DB:
        def close(self):
            pass

        def get_bind(self):
            raise RuntimeError("no bind")

    class _CM:
        def ensure_default_row(self, db):
            return None

        def get_config(self, config_id, db=None):
            return {"min_score": 70}

    class _Loader:
        def __init__(self, db, market="CN"):
            self.market = market

        @staticmethod
        def resolve_effective_history_end_date(db, date_s, market="CN"):
            return "2026-09-17"

        def list_a_share_candidates(self, limit=None):
            return [("000001", "平安"), ("000002", "万科"), ("000003", "国农")]

        def list_hk_share_candidates(self, limit=None):
            return []

    class _Engine:
        def __init__(self, loader, cfg):
            pass

        def screen_universe(self, stocks, *, as_of_end_date=None, require_pass=True):
            captured["require_pass"] = require_pass
            captured["asof"] = as_of_end_date
            return [
                {
                    "code": "000001",
                    "name": "平安",
                    "signal_date": as_of_end_date,
                    "buy_signal": True,
                    "score": 80,
                },
                {
                    "code": "000002",
                    "name": "万科",
                    "signal_date": as_of_end_date,
                    "buy_signal": False,
                    "score": 55,
                },
                {
                    "code": "000003",
                    "name": "国农",
                    "signal_date": as_of_end_date,
                    "buy_signal": False,
                    "score": 12,
                },
            ]

    def _upsert(db, *, config_id, rows):
        captured["rows"] = list(rows)
        captured["config_id"] = config_id
        return len(rows)

    def _mark(db, *, config_id, trade_date, extra=None):
        captured["mark"] = {"config_id": config_id, "trade_date": trade_date, "extra": extra}

    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr("backend_core.strategies.urt.config.URTConfigManager", _CM)
    monkeypatch.setattr("backend_core.strategies.urt.data_loader.URTDataLoader", _Loader)
    monkeypatch.setattr("backend_core.strategies.urt.strategy_engine.URTStrategyEngine", _Engine)
    monkeypatch.setattr("backend_core.strategies.urt.trace_store.upsert_trace_rows", _upsert)
    monkeypatch.setattr("backend_core.strategies.urt.trace_store.mark_date_scanned", _mark)
    monkeypatch.setattr(sp, "resolve_urt_trade_date", lambda db, market="CN": "2026-09-17")
    monkeypatch.delenv("URT_PRECOMPUTE_MIN_SCORE", raising=False)

    out = sp.run_urt_precompute_for_config(3, market="CN")

    assert out["success"] is True
    assert captured["require_pass"] is False
    assert out["hits"] == 1
    assert out["rows"] == 3
    assert out["written"] == 2
    assert out["storage_min_score"] == 50
    assert [r["code"] for r in captured["rows"]] == ["000001", "000002"]
    assert captured["mark"]["trade_date"] == "2026-09-17"
    assert captured["mark"]["extra"]["scope"] == "full_market"
    assert captured["mark"]["extra"]["candidates"] == 3
    assert captured["mark"]["extra"]["scanned_rows"] == 3
    assert captured["mark"]["extra"]["written"] == 2
    assert captured["mark"]["extra"]["storage_min_score"] == 50


def test_gms_trace_storage_floor(monkeypatch):
    from backend_core.strategies.gms import frontend_interface as gfi

    monkeypatch.delenv("GMS_PRECOMPUTE_MIN_SCORE", raising=False)
    assert gfi.resolve_gms_trace_storage_min_score() == 50
    assert gfi._passes_gms_trace_storage_floor({"score_total": 50})
    assert not gfi._passes_gms_trace_storage_floor({"score_total": 49.9})
    assert not gfi._passes_gms_trace_storage_floor({"score_total": None})
    monkeypatch.setenv("GMS_PRECOMPUTE_MIN_SCORE", "60")
    assert gfi.resolve_gms_trace_storage_min_score() == 60
