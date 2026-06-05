"""A股实时采集：代码规范化与 collect_enabled 过滤。"""
from backend_core.data_collectors.akshare.realtime import (
    normalize_stock_code,
    should_collect_stock,
)


def test_normalize_em_code():
    assert normalize_stock_code("1") == "000001"
    assert normalize_stock_code(600036) == "600036"


def test_normalize_sina_code():
    assert normalize_stock_code("sz000001", "sina") == "000001"
    assert normalize_stock_code("sh600036", "sina") == "600036"


def test_should_collect_disabled_only():
    disabled = {"000001", "600036"}
    assert should_collect_stock("000001", disabled) is False
    assert should_collect_stock("000002", disabled) is True

