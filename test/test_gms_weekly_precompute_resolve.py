# -*- coding: utf-8 -*-
"""周线预计算 config 解析：勿被日线白名单滤空。"""

import os
from unittest.mock import patch

from backend_core.strategies.gms.scheduled_precompute import _resolve_precompute_config_ids


def test_weekly_does_not_inherit_daily_whitelist(monkeypatch):
    monkeypatch.setenv("GMS_PRECOMPUTE_CONFIG_IDS", "1,2")
    monkeypatch.delenv("GMS_WEEKLY_PRECOMPUTE_CONFIG_IDS", raising=False)
    with patch(
        "backend_core.strategies.gms.config.GMSConfigManager.list_precompute_config_ids",
        return_value=[5],
    ):
        ids = _resolve_precompute_config_ids("weekly")
    assert ids == [5]


def test_weekly_whitelist_applies_when_set(monkeypatch):
    monkeypatch.setenv("GMS_WEEKLY_PRECOMPUTE_CONFIG_IDS", "9")
    with patch(
        "backend_core.strategies.gms.config.GMSConfigManager.list_precompute_config_ids",
        return_value=[5, 9],
    ):
        ids = _resolve_precompute_config_ids("weekly")
    assert ids == [9]


def test_force_ignores_weekly_whitelist(monkeypatch):
    monkeypatch.setenv("GMS_WEEKLY_PRECOMPUTE_CONFIG_IDS", "9")
    with patch(
        "backend_core.strategies.gms.config.GMSConfigManager.list_precompute_config_ids",
        return_value=[5],
    ):
        ids = _resolve_precompute_config_ids("weekly", ignore_env_whitelist=True)
    assert ids == [5]