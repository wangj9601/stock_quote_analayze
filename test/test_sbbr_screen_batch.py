# -*- coding: utf-8 -*-
"""SBBR 全市场扫描按批取 K 线，评完即丢。"""

from backend_core.strategies.gms.structure_levels import kde_bars_limit
from backend_core.strategies.sbbr.config import get_default_sbbr_config
from backend_core.strategies.sbbr.data_loader import SBBRDataLoader
from backend_core.strategies.sbbr.strategy_engine import (
    SBBRStrategyEngine,
    sbbr_bars_batch_size,
)


def test_batch_size_shrinks_to_row_budget(monkeypatch):
    monkeypatch.delenv("SBBR_BARS_BATCH_SIZE", raising=False)
    # 800 根时 12000 // 800 = 15，配置里的 200 不会整批装入
    assert sbbr_bars_batch_size({"batch_size": 200}, 800) == 15
    assert sbbr_bars_batch_size({"batch_size": 8}, 800) == 8
    assert sbbr_bars_batch_size({"batch_size": 200}, 30) == 200


def test_batch_size_env_overrides_config(monkeypatch):
    monkeypatch.setenv("SBBR_BARS_BATCH_SIZE", "2")
    assert sbbr_bars_batch_size({"batch_size": 200}, 800) == 2


def test_batch_size_invalid_env_uses_config(monkeypatch):
    monkeypatch.setenv("SBBR_BARS_BATCH_SIZE", "nope")
    assert sbbr_bars_batch_size({"batch_size": 200}, 800) == 15


class _BatchLoader:
    def __init__(self):
        self.calls = []

    def resolve_effective_trade_date(self, requested=None):
        return "2024-06-14"

    def load_market_returns(self, **kwargs):
        return [0.0] * 5

    def load_share_map(self, codes, as_of_date=None):
        return {code: {"code": code, "name": code} for code in codes}

    def load_bars_batch(self, codes, *, end_date=None, limit=120):
        self.calls.append((list(codes), end_date, limit))
        return {
            code: [
                {
                    "date": "2024-06-14",
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 1,
                    "amount": 1,
                    "turnover_rate": None,
                }
            ]
            for code in codes
        }


def _row(code, *, entry=False):
    return {
        "code": code,
        "entry_signal": entry,
        "bottom_matched": False,
        "volume_ratio": 1.0,
        "size_ok": True,
    }


def test_screen_loads_bars_in_batches(monkeypatch):
    monkeypatch.delenv("SBBR_BARS_BATCH_SIZE", raising=False)
    cfg = get_default_sbbr_config()
    cfg["scan"]["batch_size"] = 1
    engine = SBBRStrategyEngine(config=cfg)
    loader = _BatchLoader()
    engine.loader = loader
    seen = []

    def _eval(code, **kwargs):
        seen.append((code, kwargs.get("date"), kwargs.get("bars")))
        return _row(code, entry=(code == "000002"))

    engine.evaluate_code = _eval
    rows = engine.screen(
        codes=["000003", "000001", "000002"],
        require_size=False,
        require_bottom=False,
        max_results=10,
    )
    assert [call[0] for call in loader.calls] == [["000003"], ["000001"], ["000002"]]
    assert loader.calls[0][1] == "2024-06-14"
    assert loader.calls[0][2] == max(120, kde_bars_limit(cfg))
    assert [item[0] for item in seen] == ["000003", "000001", "000002"]
    assert seen[0][2][0]["date"] == "2024-06-14"
    assert [row["code"] for row in rows] == ["000002", "000003", "000001"]


def test_screen_env_batch_size(monkeypatch):
    monkeypatch.setenv("SBBR_BARS_BATCH_SIZE", "2")
    cfg = get_default_sbbr_config()
    cfg["scan"]["batch_size"] = 50
    engine = SBBRStrategyEngine(config=cfg)
    loader = _BatchLoader()
    engine.loader = loader
    engine.evaluate_code = lambda code, **kwargs: None
    rows = engine.screen(
        codes=["000001", "000002", "000003"],
        require_size=False,
        require_bottom=False,
    )
    assert [call[0] for call in loader.calls] == [["000001", "000002"], ["000003"]]
    assert rows == []


def test_screen_without_batch_loader_keeps_per_code_load():
    class _PerCode:
        def resolve_effective_trade_date(self, requested=None):
            return "2024-06-14"

        def load_market_returns(self, **kwargs):
            return []

        def load_share_map(self, codes, as_of_date=None):
            return {}

    engine = SBBRStrategyEngine(config=get_default_sbbr_config())
    engine.loader = _PerCode()
    seen = []

    def _eval(code, **kwargs):
        seen.append(kwargs.get("bars"))
        return _row(code)

    engine.evaluate_code = _eval
    rows = engine.screen(codes=["000001"], require_size=False, require_bottom=False)
    assert seen == [None]
    assert rows[0]["code"] == "000001"


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    def __init__(self, fail):
        self.fail = fail
        self.batch_sizes = []
        self.solo = []
        self.rollbacks = 0

    def execute(self, sql, params):
        if "codes" in params:
            codes = list(params["codes"])
            self.batch_sizes.append(len(codes))
            if self.fail(codes):
                raise MemoryError("out of memory")
            return _Rows(
                [
                    (code, "2024-06-14", 1, 2, 0.5, 1.2, 10, 20, None)
                    for code in codes
                ]
            )
        self.solo.append(params.get("code"))
        return _Rows([("2024-06-14", 1, 2, 0.5, 1.2, 10, 20, 1.5)])

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        raise AssertionError("shared session must stay open")


def test_load_bars_batch_splits_on_oom():
    db = _FakeDB(fail=lambda codes: len(codes) > 1)
    loader = SBBRDataLoader(db_session=db)
    out = loader.load_bars_batch(["1", "2", "3"], end_date="2024-06-14", limit=5)
    assert db.batch_sizes == [3, 1, 2, 1, 1]
    assert db.rollbacks == 2
    assert db.solo == []
    assert list(out) == ["000001", "000002", "000003"]
    assert out["000002"][0]["close"] == 1.2
    assert out["000002"][0]["turnover_rate"] is None


def test_load_bars_batch_falls_back_to_single_code():
    db = _FakeDB(fail=lambda codes: True)
    loader = SBBRDataLoader(db_session=db)
    out = loader.load_bars_batch(["000001", "000002"], end_date="2024-06-14", limit=5)
    assert db.solo == ["000001", "000002"]
    assert out["000001"][0]["turnover_rate"] == 1.5
    assert out["000002"][0]["date"] == "2024-06-14"
