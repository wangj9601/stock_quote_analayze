"""GMS 任务进度 clamp 与回测进度百分比上限。"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms.backtest_storage import clamp_gms_progress
from backend_core.strategies.gms.backtest_runner import _progress_pct


def test_clamp_gms_progress():
    assert clamp_gms_progress(283) == 100
    assert clamp_gms_progress(100) == 100
    assert clamp_gms_progress(0) == 0
    assert clamp_gms_progress(-5) == 0
    assert clamp_gms_progress("50") == 50
    assert clamp_gms_progress(None) == 0


def test_progress_pct_caps():
    assert _progress_pct(283, 100) == 100
    assert _progress_pct(50, 100) == 50
    assert _progress_pct(0, 10) == 0
    assert _progress_pct(1, 0) == 0
