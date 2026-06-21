"""GMS / 选股 ST 剔除工具测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.utils.st_stock_filter import filter_codes_exclude_st, is_st_stock_name


class _Row:
    def __init__(self, code):
        self.code = code


class _Query:
    def __init__(self, st_codes):
        self._st_codes = set(st_codes)

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return [_Row(c) for c in self._st_codes]


class _DB:
    def __init__(self, st_codes=None):
        self._st_codes = st_codes or set()

    def query(self, model):
        return _Query(self._st_codes)


def test_is_st_stock_name():
    assert is_st_stock_name("*ST海龙") is True
    assert is_st_stock_name("ST炼石") is True
    assert is_st_stock_name("平安银行") is False
    assert is_st_stock_name("") is False


def test_filter_codes_exclude_st():
    db = _DB({"000001"})
    codes = ["000001", "600519", "00700", "688001"]
    out = filter_codes_exclude_st(db, codes)
    assert out == ["600519", "00700", "688001"]


def test_filter_codes_exclude_st_no_cn():
    db = _DB({"000001"})
    assert filter_codes_exclude_st(db, ["00700", "SPY"]) == ["00700", "SPY"]
