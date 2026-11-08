"""预计算进度日志：每 200 跨边界打印。"""

import logging

from backend_core.strategies.precompute_progress import maybe_log_precompute_progress


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def test_maybe_log_every_200_and_finish():
    log = logging.getLogger("test.precompute_progress")
    log.handlers.clear()
    log.setLevel(logging.INFO)
    h = _ListHandler()
    log.addHandler(h)
    state = {"last": 0}

    maybe_log_precompute_progress(log, "URT", 150, 1000, state=state)
    assert h.records == []

    maybe_log_precompute_progress(log, "URT", 200, 1000, state=state)
    assert len(h.records) == 1
    assert "已完成 200/1000" in h.records[0]

    maybe_log_precompute_progress(log, "URT", 450, 1000, state=state)
    assert any("已完成 450/1000" in m for m in h.records)

    maybe_log_precompute_progress(log, "URT", 1000, 1000, state=state)
    assert any("已完成 1000/1000" in m for m in h.records)

    n = len(h.records)
    maybe_log_precompute_progress(log, "URT", 1000, 1000, state=state)
    assert len(h.records) == n
