# -*- coding: utf-8 -*-
"""URT 港股 scope 轻量单测（不连库）。"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
for p in (str(project_root), str(project_root / "backend_api"), str(project_root / "backend_core")):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend_core.strategies.urt.data_loader import (  # noqa: E402
    is_hk_stock_code,
    normalize_hk_code,
)
from backend_core.strategies.urt.scheduled_precompute import (  # noqa: E402
    run_urt_precompute_hk,
    scheduled_urt_signals_hk,
)


def test_normalize_hk_code():
    assert normalize_hk_code("700") == "00700"
    assert normalize_hk_code("00700") == "00700"
    assert normalize_hk_code("") is None


def test_is_hk_stock_code():
    assert is_hk_stock_code("00700") is True
    assert is_hk_stock_code("000001") is False
    assert is_hk_stock_code("700") is True


def test_hk_precompute_imports():
    assert callable(run_urt_precompute_hk)
    assert callable(scheduled_urt_signals_hk)
