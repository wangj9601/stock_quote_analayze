# -*- coding: utf-8 -*-
"""港股 RS Rating 相关单测（不依赖数据库）。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend_core.indicators.rs_rating.config import (
    HK_FACTOR_SOURCES,
    MARKET_TYPE_HK,
    PRICE_ADJUST,
)
from backend_core.indicators.rs_rating.qfq_closes import (
    PREFERRED_SOURCES_HK,
    QUOTES_TABLE_HK,
)
from backend_core.indicators.rs_rating.universe_hk import _normalize_hk_code
from backend_core.data_collectors.workflow.node_registry import get_node, list_node_defs


def test_hk_config_constants():
    assert MARKET_TYPE_HK == "HK"
    assert PRICE_ADJUST == "qfq"
    assert HK_FACTOR_SOURCES == PREFERRED_SOURCES_HK
    assert "akshare_sina_hk_qfq" in HK_FACTOR_SOURCES
    assert QUOTES_TABLE_HK == "historical_quotes_hk"
    from backend_core.indicators.rs_rating.config import (
        LOOKBACK_CALENDAR_DAYS,
        LOOKBACK_CALENDAR_DAYS_HK,
        coverage_threshold,
    )

    assert LOOKBACK_CALENDAR_DAYS_HK > LOOKBACK_CALENDAR_DAYS
    assert coverage_threshold("HK") == coverage_threshold(MARKET_TYPE_HK)
    assert coverage_threshold("CN") == 0.90


def test_normalize_hk_code():
    assert _normalize_hk_code("700") == "00700"
    assert _normalize_hk_code("00700") == "00700"
    assert _normalize_hk_code("HK00700") == "00700"
    assert _normalize_hk_code("600519") is None
    assert _normalize_hk_code("") is None


def test_node_registry_has_rs_rating_hk():
    keys = {n.key for n in list_node_defs()}
    assert "rs_rating_hk" in keys
    assert "rs_rating_cn" in keys
    node = get_node("rs_rating_hk")
    assert node is not None
    assert node.name == "港股相对强度RS预计算"


def test_service_routes_hk_by_code_length():
    from backend_core.indicators.rs_rating import service as svc

    assert svc._is_hk_market("HK", "00700") is True
    assert svc._is_hk_market("CN", "00700") is True  # 5 位数字也视为港股
    assert svc._is_hk_market("CN", "600519") is False
    assert svc._normalize_hk_code("700") == "00700"


def test_list_candidate_codes_hk_explicit_filters(monkeypatch):
    from backend_core.indicators.rs_rating import universe_hk as uh

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [("00700",), ("00941",)]
    out = uh.list_candidate_codes_hk(session, "2025-01-02", codes=["700", "941", "bad"])
    assert out == ["00700", "00941"]
    assert session.execute.called
