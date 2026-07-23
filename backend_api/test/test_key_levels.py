#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关键价位计算测试（已改为 KDE，详细用例见 test/test_key_levels_kde.py）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

from test.test_key_levels_kde import (  # noqa: E402
    test_key_levels_insufficient_samples,
    test_key_levels_uses_kde_peaks,
)


if __name__ == "__main__":
    test_key_levels_uses_kde_peaks()
    test_key_levels_insufficient_samples()
    print("OK")
