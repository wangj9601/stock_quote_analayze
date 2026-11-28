# -*- coding: utf-8 -*-
"""GMS resolve_config_id：日线 config 不可用于周线查询。"""

from types import SimpleNamespace
from unittest.mock import patch

from backend_core.strategies.gms.config import (
    GMS_CANONICAL_STANDARD_NAME,
    GMS_CANONICAL_WEEKLY_NAME,
    GMSConfigManager,
)


def test_weekly_remaps_daily_config_id():
    mgr = GMSConfigManager()
    daily = SimpleNamespace(
        id=1,
        name=GMS_CANONICAL_STANDARD_NAME,
        timeframe="daily",
        config_params={},
    )
    with patch.object(mgr, "get_config_row", return_value=daily), patch.object(
        mgr, "ensure_canonical_weekly_config", return_value=5
    ):
        assert mgr.resolve_config_id(1, timeframe="weekly") == 5


def test_weekly_keeps_weekly_config_id():
    mgr = GMSConfigManager()
    weekly = SimpleNamespace(
        id=5,
        name=GMS_CANONICAL_WEEKLY_NAME,
        timeframe="weekly",
        config_params={"timeframe": "weekly"},
    )
    with patch.object(mgr, "get_config_row", return_value=weekly):
        assert mgr.resolve_config_id(5, timeframe="weekly") == 5
