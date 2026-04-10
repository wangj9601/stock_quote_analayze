import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend_api.admin.gms_admin_routes import _normalize_market, _normalize_stock_code  # noqa: E402


def test_normalize_market():
    assert _normalize_market("A") == "A"
    assert _normalize_market("cn") == "A"
    assert _normalize_market("港股") == "HK"
    assert _normalize_market("HK") == "HK"


def test_normalize_stock_code():
    assert _normalize_stock_code("A", "1") == "000001"
    assert _normalize_stock_code("A", "SZ000001") == "000001"
    assert _normalize_stock_code("HK", "700") == "00700"

    with pytest.raises(Exception):
        _normalize_stock_code("A", "ABC")
