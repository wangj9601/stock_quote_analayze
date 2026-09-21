# -*- coding: utf-8 -*-
"""龙虎榜：同花顺优先，东方财富兜底，字段归一化。"""

from backend_api.stock.dragon_tiger import (
    load_dragon_tiger,
    norm_code,
    normalize_fuyao_data,
    records_to_em_payload,
)
from backend_api.stock.dragon_tiger_store import should_replace_snapshot


def test_norm_code_zfill_and_suffix():
    assert norm_code("2709") == "002709"
    assert norm_code("000001.SZ") == "000001"
    assert norm_code("SH600519") == "600519"


def test_normalize_fuyao_sorts_by_net_and_keeps_hot_money():
    data = normalize_fuyao_data(
        {
            "trade_date": "2026-09-18",
            "stock_count": 2,
            "stock_items": [
                {
                    "ticker": "000001",
                    "name": "平安银行",
                    "change": 1.2,
                    "buy_value": 1e8,
                    "sell_value": 2e8,
                    "org_net_value": -1e7,
                    "hot_money_net_value": 3e6,
                    "limit_reason": "日涨幅偏离",
                },
                {
                    "thscode": "600519.SH",
                    "name": "贵州茅台",
                    "change": -0.5,
                    "buy_value": 5e8,
                    "sell_value": 1e8,
                    "limit_reason": "振幅",
                },
            ],
            "hot_money_items": [
                {
                    "name": "赵老哥",
                    "rows": [
                        {
                            "ticker": "000001",
                            "name": "平安银行",
                            "buy_value": 2e7,
                            "sell_value": 1e7,
                        }
                    ],
                }
            ],
        },
        board_type="all",
    )
    assert data["source"] == "fuyao"
    assert data["trade_date"] == "2026-09-18"
    assert data["items"][0]["code"] == "600519"
    assert data["items"][0]["net_value"] == 4e8
    assert data["items"][1]["net_value"] == -1e8
    assert data["hot_money_items"][0]["name"] == "赵老哥"
    assert data["hot_money_items"][0]["net_value"] == 1e7
    assert data["hot_money_items"][0]["stocks"][0]["code"] == "000001"
    assert data["items"][1]["org_net_value"] == -1e7
    assert data["items"][1]["hot_money_net_value"] == 3e6
    assert data["items"][0]["org_net_value"] is None
    assert data["items"][0]["hot_money_net_value"] is None


def test_em_payload_picks_latest_day_and_zfills_code():
    payload = records_to_em_payload(
        [
            {
                "代码": "788",
                "名称": "北大医药",
                "上榜日": "2026-09-17 00:00:00",
                "涨跌幅": 10.0,
                "收盘价": 8.5,
                "龙虎榜买入额": 1e8,
                "龙虎榜卖出额": 2e7,
                "龙虎榜净买额": 8e7,
                "净买额占总成交比": 12.3,
                "上榜原因": "涨幅偏离",
                "上榜后1日": 1.1,
            },
            {
                "代码": "000002",
                "名称": "万科A",
                "上榜日": "2026-09-18",
                "涨跌幅": -3.2,
                "龙虎榜净买额": -5e7,
                "上榜原因": "跌幅偏离",
            },
        ],
        board_type="org",
        trade_date=None,
    )
    assert payload["trade_date"] == "2026-09-18"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["code"] == "000002"
    assert payload["board_type_note"]
    assert payload["hot_money_items"] == []


def test_load_prefers_fuyao():
    called = {"em": 0}

    def fuyao_loader(board_type, trade_date):
        return {
            "ok": True,
            "data": normalize_fuyao_data(
                {
                    "trade_date": "2026-09-18",
                    "stock_items": [
                        {"ticker": "000001", "name": "平安银行", "buy_value": 2, "sell_value": 1}
                    ],
                },
                board_type=board_type,
            ),
        }

    def em_loader(board_type, trade_date):
        called["em"] += 1
        return {"ok": False, "error": "should_not_call"}

    out = load_dragon_tiger("all", None, fuyao_loader=fuyao_loader, em_loader=em_loader)
    assert out["success"] is True
    assert out["data"]["source"] == "fuyao"
    assert called["em"] == 0


def test_load_falls_back_to_em():
    def fuyao_loader(board_type, trade_date):
        return {"ok": False, "error": "missing_api_key"}

    def em_loader(board_type, trade_date):
        return {
            "ok": True,
            "data": records_to_em_payload(
                [
                    {
                        "代码": "600000",
                        "名称": "浦发银行",
                        "上榜日": "2026-09-18",
                        "龙虎榜净买额": 100,
                        "上榜原因": "换手率",
                    }
                ],
                board_type=board_type,
                trade_date=trade_date,
            ),
        }

    out = load_dragon_tiger("all", "2026-09-18", fuyao_loader=fuyao_loader, em_loader=em_loader)
    assert out["success"] is True
    assert out["data"]["source"] == "akshare_em"
    assert out["data"]["items"][0]["code"] == "600000"
    assert "东方财富" in (out["data"]["fallback_reason"] or "")


def test_load_both_empty_is_success_with_message():
    out = load_dragon_tiger(
        "all",
        "2026-09-18",
        fuyao_loader=lambda *_a, **_k: {"ok": False, "error": "empty_items"},
        em_loader=lambda *_a, **_k: {"ok": False, "error": "empty_items"},
    )
    assert out["success"] is True
    assert out["data"]["items"] == []
    assert out["data"]["fallback_reason"]


def test_load_rejects_bad_date():
    out = load_dragon_tiger("all", "20260918")
    assert out["success"] is False


def test_fuyao_snapshot_not_replaced_by_eastmoney():
    assert should_replace_snapshot(None, "fuyao") is True
    assert should_replace_snapshot(None, "akshare_em") is True
    assert should_replace_snapshot("akshare_em", "fuyao") is True
    assert should_replace_snapshot("fuyao", "akshare_em") is False
    assert should_replace_snapshot("fuyao", "none") is False
    assert should_replace_snapshot(None, "none") is False
