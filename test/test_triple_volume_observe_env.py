"""3倍量观察：扫描环境变量解析（无数据库）。"""

import pytest

from backend_core.strategies.triple_volume_observe.env_config import (
    TRIPLE_VOLUME_PUSH_REPORT_TYPES,
    is_triple_volume_observe_enabled,
    load_scan_env,
)


def test_load_scan_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIPLE_VOLUME_OBSERVE_ENABLED", raising=False)
    monkeypatch.delenv("TRIPLE_VOLUME_MARKETS", raising=False)
    monkeypatch.delenv("TRIPLE_VOLUME_BOARDS", raising=False)
    monkeypatch.delenv("TRIPLE_VOLUME_RATIO", raising=False)
    cfg = load_scan_env()
    assert cfg.enabled is False
    assert cfg.markets == ["CN"]
    assert cfg.board_keys == []
    assert cfg.volume_ratio == 3.0
    assert is_triple_volume_observe_enabled() is False


def test_load_scan_env_enabled_and_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIPLE_VOLUME_OBSERVE_ENABLED", "true")
    monkeypatch.setenv("TRIPLE_VOLUME_MARKETS", "CN, HK")
    monkeypatch.setenv("TRIPLE_VOLUME_BOARDS", "CYB, SZ_MAIN")
    monkeypatch.setenv("TRIPLE_VOLUME_RATIO", "2.5")
    cfg = load_scan_env()
    assert cfg.enabled is True
    assert cfg.markets == ["CN", "HK"]
    assert cfg.board_keys == ["CYB", "SZ_MAIN"]
    assert cfg.volume_ratio == 2.5
    assert is_triple_volume_observe_enabled() is True


def test_push_report_types_constant() -> None:
    assert "triple_volume_observe_scan" in TRIPLE_VOLUME_PUSH_REPORT_TYPES
    assert "triple_volume_observe_eval" in TRIPLE_VOLUME_PUSH_REPORT_TYPES
