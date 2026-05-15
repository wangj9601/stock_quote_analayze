"""wechat_app_profile 规范化与环境变量名（方案 A）。"""
import pytest

from backend_core.wechat.wechat_config import normalize_wechat_app_profile, WeChatConfig


def test_normalize_empty_and_trim():
    assert normalize_wechat_app_profile(None) is None
    assert normalize_wechat_app_profile("") is None
    assert normalize_wechat_app_profile("   ") is None


def test_normalize_strips_invalid_chars_uppercase():
    assert normalize_wechat_app_profile("b") == "B"
    assert normalize_wechat_app_profile("sub-b_1") == "SUBB_1"
    assert normalize_wechat_app_profile("a" * 40) == "A" * 32


def test_normalize_non_string_returns_none():
    assert normalize_wechat_app_profile(123) is None  # type: ignore[arg-type]


def test_wechat_config_default_env_keys(monkeypatch):
    monkeypatch.setenv("WECHAT_CORP_ID", "cid")
    monkeypatch.setenv("WECHAT_CORP_SECRET", "sec")
    monkeypatch.setenv("WECHAT_AGENT_ID", "100")
    c = WeChatConfig(None)
    assert c.corp_id == "cid"
    assert c.corp_secret == "sec"
    assert c.agent_id == "100"
    assert c.is_configured() is True


def test_wechat_config_named_profile_env_keys(monkeypatch):
    monkeypatch.delenv("WECHAT_CORP_ID", raising=False)
    monkeypatch.setenv("WECHAT_B_CORP_ID", "cidb")
    monkeypatch.setenv("WECHAT_B_CORP_SECRET", "secb")
    monkeypatch.setenv("WECHAT_B_AGENT_ID", "200")
    c = WeChatConfig("b")
    assert c.app_profile == "B"
    assert c.corp_id == "cidb"
    assert c.corp_secret == "secb"
    assert c.agent_id == "200"
    assert c.is_configured() is True
