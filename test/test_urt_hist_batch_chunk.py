# -*- coding: utf-8 -*-
"""URT 批量拉行情分块大小与 OOM 回退。"""

from unittest.mock import MagicMock, patch

from backend_core.strategies.urt.data_loader import URTDataLoader
from backend_core.strategies.urt.strategy_engine import URTStrategyEngine


def test_resolve_hist_batch_chunk_size_long_window_is_small():
    # 与生产类似：~3 年回看（KDE 750*1.6）
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2023-04-16",
        end_date="2026-09-07",
    )
    assert 1 <= n <= 40
    assert n < 80


def test_resolve_hist_batch_chunk_size_short_window_allows_more():
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2026-08-01",
        end_date="2026-09-07",
    )
    assert n >= 20


def test_resolve_hist_batch_chunk_size_explicit_override():
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2023-04-16",
        end_date="2026-09-07",
        chunk_size=25,
    )
    assert n == 25


def test_fetch_batch_oom_shrinks_then_succeeds():
    loader = URTDataLoader(MagicMock(), market="CN")
    calls = {"n": 0}

    def _fake_execute(*_a, **_k):
        calls["n"] += 1
        # 前两次模拟 Portal OOM，第三次成功空结果
        if calls["n"] <= 2:
            raise Exception(
                '(psycopg2.errors.OutOfMemory) 错误:  内存用尽\n'
                'DETAIL:  在内存上下文"PortalHoldContext"中请求大小为68时失败.'
            )
        m = MagicMock()
        m.__iter__ = lambda self: iter([])
        return m

    loader.db.execute.side_effect = _fake_execute
    loader.db.rollback = MagicMock()
    with patch.object(URTDataLoader, "resolve_hist_batch_chunk_size", return_value=8):
        out = loader.fetch_historical_desc_batch(
            ["600519", "000001", "000002", "000003", "000004", "000005", "000006", "000007"],
            start_date="2023-01-01",
            end_date="2026-09-23",
        )
    assert set(out.keys()) == {
        "600519",
        "000001",
        "000002",
        "000003",
        "000004",
        "000005",
        "000006",
        "000007",
    }
    assert loader.db.rollback.called
    assert calls["n"] >= 3


def test_load_hist_map_rollbacks_before_fallback():
    loader = MagicMock()
    loader.fetch_historical_desc_batch.side_effect = Exception("OutOfMemory PortalHoldContext")
    loader.db.rollback = MagicMock()
    engine = URTStrategyEngine(loader, {})
    got = engine._load_hist_map([("600519", "茅台")], "2023-01-01", "2026-09-23")
    assert got is None
    loader.db.rollback.assert_called()


if __name__ == "__main__":
    test_resolve_hist_batch_chunk_size_long_window_is_small()
    test_resolve_hist_batch_chunk_size_short_window_allows_more()
    test_resolve_hist_batch_chunk_size_explicit_override()
    test_fetch_batch_oom_shrinks_then_succeeds()
    test_load_hist_map_rollbacks_before_fallback()
    print("test_urt_hist_batch_chunk.py: all passed")
