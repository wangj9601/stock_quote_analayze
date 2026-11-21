# -*- coding: utf-8 -*-
"""确保行情路由在包导入方式下可挂载（生产曾因 from database/models 静默失败 → 404）。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-jwt-secret-key-at-least-32-chars!!",
)


def test_quotes_routes_import_and_paths():
    from backend_api.quotes_routes import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/api/quotes/stocks" in paths
    assert "/api/quotes/history" in paths
    assert "/api/quotes/indices" in paths
