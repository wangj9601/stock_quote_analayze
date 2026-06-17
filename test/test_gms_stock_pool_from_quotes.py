"""GMS 股票池：应从当日行情表取码，而非 stock_basic_info 全量"""

import os
import sys
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend_core.strategies.gms import frontend_interface as gfi


def test_resolve_pool_date_falls_back_when_day_empty():
    db = MagicMock()
    # max date = 2026-06-16
    db.query.return_value.scalar.return_value = "2026-06-16"
    db.query.return_value.filter.return_value.limit.return_value.first.return_value = None

    eff = gfi._resolve_pool_date_for_quotes(db, "2026-06-17", MagicMock(date=MagicMock()))
    assert eff == "2026-06-16"


def test_normalize_cn_pool_code():
    assert gfi._normalize_cn_pool_code(1) == "000001"
    assert gfi._normalize_cn_pool_code("600519") == "600519"


def test_get_stock_pool_cn_queries_historical_quotes(monkeypatch):
    db = MagicMock()
    iface = gfi.GMSFrontendInterface(db, {})

    monkeypatch.setattr(gfi, "_resolve_pool_date_for_quotes", lambda _db, d, _m: "2026-06-17")
    monkeypatch.setattr(
        gfi,
        "_distinct_codes_from_quotes",
        lambda _db, _m, d, _fn: ["000001", "600519"] if d == "2026-06-17" else [],
    )

    codes = iface._get_stock_pool("2026-06-17", "cn")
    assert codes == ["000001", "600519"]
