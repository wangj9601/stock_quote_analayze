# -*- coding: utf-8 -*-
"""URT 批量拉行情分块大小。"""

from backend_core.strategies.urt.data_loader import URTDataLoader


def test_resolve_hist_batch_chunk_size_long_window_is_small():
    # 与生产类似：~3 年回看（KDE 750*1.6）
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2023-04-16",
        end_date="2026-09-07",
    )
    assert 10 <= n <= 80
    assert n < 400


def test_resolve_hist_batch_chunk_size_short_window_allows_more():
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2026-08-01",
        end_date="2026-09-07",
    )
    assert n >= 40


def test_resolve_hist_batch_chunk_size_explicit_override():
    n = URTDataLoader.resolve_hist_batch_chunk_size(
        start_date="2023-04-16",
        end_date="2026-09-07",
        chunk_size=25,
    )
    assert n == 25
