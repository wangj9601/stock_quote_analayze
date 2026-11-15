"""RPE 日终预计算以概念板块为处理单位。"""

from backend_core.strategies.rpe.scheduled_precompute import run_rpe_precompute


class _Loader:
    def __init__(self, boards):
        self.boards = boards
        self.kinds = []

    def resolve_trade_date(self):
        return "2026-11-14"

    def list_boards(self, kind, limit=None):
        self.kinds.append((kind, limit))
        rows = list(self.boards)
        if limit:
            rows = rows[: int(limit)]
        return rows


class _Engine:
    def __init__(self, db_session=None, config=None, board_code_source=None):
        self.loader = _Loader(
            [
                {"board_code": "C1", "board_name": "概念一"},
                {"board_code": "C2", "board_name": "概念二"},
            ]
        )
        self.calls = []

    def screen_board(self, board_code, board_name, **kwargs):
        self.calls.append((board_code, kwargs.get("board_kind"), kwargs.get("include_no_signal")))
        return [
            {
                "code": "000001",
                "sector_id": board_code,
                "sector_name": board_name,
                "signal_type": "catch_up",
                "entry_signal": board_code == "C1",
                "date": "2026-11-14",
            },
            {
                "code": "000002",
                "sector_id": board_code,
                "signal_type": None,
                "entry_signal": False,
                "date": "2026-11-14",
            },
        ]


class _DB:
    def __init__(self):
        self.added = []
        self.closed = False

    def add(self, row):
        self.added.append(row)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        self.closed = True


class _ConfigMgr:
    def get_default_config_id(self):
        return 7

    def get_config(self, config_id):
        assert config_id == 7
        return {"scan": {"max_results": 200, "max_boards": None, "min_sector_members": 5}}


def test_precompute_keeps_each_concept_for_same_stock(monkeypatch):
    engine = _Engine()
    db = _DB()
    deleted = []
    saved = []

    monkeypatch.setattr(
        "backend_api.database.SessionLocal",
        lambda: db,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.config.RPEConfigManager",
        _ConfigMgr,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        lambda *a, **k: engine,
    )

    def _delete(session, *, config_id, trade_date, market_type="CN", sector_ids=None):
        deleted.append(
            {
                "config_id": config_id,
                "trade_date": trade_date,
                "sector_ids": sector_ids,
            }
        )
        return 3

    def _upsert(session, rows, *, config_id, trade_date):
        saved.append([(r["code"], r["sector_id"]) for r in rows])
        return len(rows)

    monkeypatch.setattr(
        "backend_core.strategies.rpe.signal_storage.delete_traces_for_date",
        _delete,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.signal_storage.upsert_signal_traces",
        _upsert,
    )
    monkeypatch.setattr(
        "backend_api.models.RPEPrecomputeRun",
        lambda **kwargs: kwargs,
    )

    summary = run_rpe_precompute()

    assert summary["ok"] is True
    assert summary["board_kind"] == "concept"
    assert summary["boards"] == 2
    assert summary["partial"] is False
    assert summary["screened"] == 2
    assert summary["saved"] == 2
    assert summary["entry_count"] == 1
    assert engine.loader.kinds == [("concept", None)]
    assert engine.calls == [("C1", "concept", False), ("C2", "concept", False)]
    assert deleted == [
        {"config_id": 7, "trade_date": "2026-11-14", "sector_ids": None}
    ]
    assert saved == [[("000001", "C1")], [("000001", "C2")]]
    assert db.closed is True


def test_partial_precompute_only_clears_scanned_concepts(monkeypatch):
    engine = _Engine()
    db = _DB()
    deleted = []

    monkeypatch.setattr("backend_api.database.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "backend_core.strategies.rpe.config.RPEConfigManager",
        _ConfigMgr,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.strategy_engine.RPEStrategyEngine",
        lambda *a, **k: engine,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.signal_storage.delete_traces_for_date",
        lambda session, **kwargs: deleted.append(kwargs.get("sector_ids")) or 0,
    )
    monkeypatch.setattr(
        "backend_core.strategies.rpe.signal_storage.upsert_signal_traces",
        lambda session, rows, **kwargs: len(rows),
    )
    monkeypatch.setattr(
        "backend_api.models.RPEPrecomputeRun",
        lambda **kwargs: kwargs,
    )

    summary = run_rpe_precompute(max_boards=1)

    assert summary["partial"] is True
    assert summary["boards"] == 1
    assert deleted == [["C1"]]
    assert [c[0] for c in engine.calls] == ["C1"]
