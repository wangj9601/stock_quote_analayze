"""URT 每日预计算：未买点也落库。"""

from backend_core.strategies.urt import scheduled_precompute as sp


def test_daily_precompute_persists_non_buy(monkeypatch):
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
            return [("000001", "平安"), ("000002", "万科")]

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

    out = sp.run_urt_precompute_for_config(3, market="CN")

    assert out["success"] is True
    assert captured["require_pass"] is False
    assert out["hits"] == 1
    assert out["rows"] == 2
    assert out["written"] == 2
    assert [r["buy_signal"] for r in captured["rows"]] == [True, False]
    assert captured["mark"]["trade_date"] == "2026-09-17"
    assert captured["mark"]["extra"]["scope"] == "full_market"
    assert captured["mark"]["extra"]["candidates"] == 2
