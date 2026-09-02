# -*- coding: utf-8 -*-
"""Fuyao REST / realtime_quote_by_code 优先级单元测试（不泄露 API Key）。"""

from __future__ import annotations

import pandas as pd
import pytest


def test_code_to_thscode():
    from backend_api.utils.fuyao_client import code_to_thscode

    assert code_to_thscode("000001") == "000001.SZ"
    assert code_to_thscode("600519") == "600519.SH"
    assert code_to_thscode("300750") == "300750.SZ"
    assert code_to_thscode("830799") == "830799.BJ"
    assert code_to_thscode("sh600519") == "600519.SH"
    assert code_to_thscode("000001.SZ") == "000001.SZ"


def test_snapshot_item_to_quote():
    from backend_api.utils.fuyao_client import snapshot_item_to_quote

    item = {
        "thscode": "000001.SZ",
        "ticker": "000001",
        "volume": 100000,  # 股
        "turnover": 1200000,
        "last_price": 11.91,
        "price_change": -0.01,
        "price_change_ratio_pct": -0.08,
        "open_price": 11.92,
        "high_price": 11.99,
        "low_price": 11.85,
        "prev_price": 11.92,
    }
    q = snapshot_item_to_quote(
        item,
        code="000001",
        name="平安银行",
        free_float_shares=20000000,  # 股
    )
    assert q["code"] == "000001"
    assert q["name"] == "平安银行"
    assert q["current_price"] == 11.91
    assert q["change_amount"] == -0.01
    assert q["pre_close"] == 11.92
    assert q["volume"] == 1000.0  # 股→手
    assert abs(q["average_price"] - 12.0) < 1e-9  # 成交额/股
    assert abs(q["turnover_rate"] - 0.5) < 1e-9  # 100000/20000000*100
    assert q["source"] == "fuyao"


def test_volume_shares_to_hands_and_turnover():
    from backend_api.utils.fuyao_client import (
        calc_turnover_rate_pct,
        volume_shares_to_hands,
    )

    assert volume_shares_to_hands(89224752) == 892247.52
    assert calc_turnover_rate_pct(100000, 20000000) == 0.5
    assert calc_turnover_rate_pct(100000, None) is None
    assert calc_turnover_rate_pct(None, 20000000) is None


def test_get_fuyao_api_key_from_credentials_file(tmp_path, monkeypatch):
    from backend_api.utils import fuyao_client as mod

    monkeypatch.delenv("HITHINK_FINANCE_API_KEY", raising=False)
    monkeypatch.delenv("FUYAO_API_KEY", raising=False)
    cred = tmp_path / "credentials.env"
    cred.write_text("HITHINK_FINANCE_API_KEY=test-key-abc\n", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path.parent))
    # APPDATA/hithink-finance/credentials.env
    dest_dir = tmp_path.parent / "hithink-finance"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "credentials.env").write_text(
        "HITHINK_FINANCE_API_KEY=test-key-abc\n", encoding="utf-8"
    )
    monkeypatch.setenv("APPDATA", str(tmp_path.parent))

    mod._api_key_loaded = False
    mod._api_key_cache = None
    key = mod.get_fuyao_api_key(force_reload=True)
    assert key == "test-key-abc"


def test_realtime_quote_prefers_fuyao(monkeypatch):
    from backend_api.stock import stock_manage as sm
    import json
    import asyncio

    called = {"fuyao": 0, "em": 0}

    class FakeDB:
        def query(self, *args, **kwargs):
            raise AssertionError("DB should not be queried when Fuyao succeeds")

    async def _run():
        monkeypatch.setattr(sm, "is_hk_stock", lambda code, db: False)
        monkeypatch.setattr(sm, "_lookup_stock_name", lambda db, code: "测试股")
        monkeypatch.setattr(sm, "_lookup_free_float_shares", lambda db, code: 1e9)

        def _fake_fuyao(code, name=None, free_float_shares=None):
            called["fuyao"] += 1
            return {
                "code": code,
                "name": name,
                "current_price": 10.5,
                "change_amount": 0.1,
                "change_percent": 0.96,
                "open": 10.4,
                "pre_close": 10.4,
                "high": 10.6,
                "low": 10.3,
                "volume": 100,
                "turnover": 1050,
                "turnover_rate": 1.2,
                "pe_dynamic": None,
                "average_price": 10.5,
                "source": "fuyao",
            }

        monkeypatch.setattr(
            "backend_api.utils.fuyao_client.fetch_realtime_quote_by_code",
            _fake_fuyao,
        )
        monkeypatch.setattr(
            sm,
            "_quote_from_akshare_em",
            lambda code, name=None: called.__setitem__("em", called["em"] + 1) or None,
        )

        resp = await sm.get_realtime_quote_by_code(code="600519", db=FakeDB())
        data = json.loads(resp.body)
        assert data["success"] is True
        assert data["data"]["source"] == "fuyao"
        assert data["data"]["current_price"] == "10.50"
        assert called["fuyao"] == 1
        assert called["em"] == 0

    asyncio.run(_run())


def test_realtime_quote_falls_back_to_em(monkeypatch):
    from backend_api.stock import stock_manage as sm
    import json
    import asyncio

    class FakeDB:
        def query(self, *args, **kwargs):
            raise AssertionError("DB should not be queried when EM succeeds")

    async def _run():
        monkeypatch.setattr(sm, "is_hk_stock", lambda code, db: False)
        monkeypatch.setattr(sm, "_lookup_stock_name", lambda db, code: "测试股")
        monkeypatch.setattr(sm, "_lookup_free_float_shares", lambda db, code: None)
        monkeypatch.setattr(
            "backend_api.utils.fuyao_client.fetch_realtime_quote_by_code",
            lambda code, name=None, free_float_shares=None: None,
        )
        monkeypatch.setattr(
            sm,
            "_quote_from_akshare_em",
            lambda code, name=None: {
                "code": code,
                "name": name,
                "current_price": 9.9,
                "change_amount": -0.1,
                "change_percent": -1.0,
                "open": 10.0,
                "pre_close": 10.0,
                "high": 10.1,
                "low": 9.8,
                "volume": 200,
                "turnover": 1980,
                "turnover_rate": 0.5,
                "pe_dynamic": 12.3,
                "average_price": 9.9,
                "source": "akshare_em",
            },
        )
        resp = await sm.get_realtime_quote_by_code(code="000001", db=FakeDB())
        data = json.loads(resp.body)
        assert data["success"] is True
        assert data["data"]["source"] == "akshare_em"
        assert data["data"]["current_price"] == "9.90"

    asyncio.run(_run())


def test_quote_from_akshare_em_filters_code(monkeypatch):
    from backend_api.stock import stock_manage as sm

    df = pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 11.91,
                "涨跌额": -0.01,
                "涨跌幅": -0.08,
                "今开": 11.92,
                "昨收": 11.92,
                "最高": 11.99,
                "最低": 11.85,
                "成交量": 1000,
                "成交额": 12000,
                "换手率": 1.1,
                "市盈率-动态": 5.5,
            }
        ]
    )
    monkeypatch.setattr(sm, "get_cached_spot_df", lambda: df)
    q = sm._quote_from_akshare_em("000001")
    assert q is not None
    assert q["source"] == "akshare_em"
    assert q["current_price"] == 11.91
    assert q["pe_dynamic"] == 5.5
