# -*- coding: utf-8 -*-
"""集合竞价服务单元测试（Mock Fuyao，不依赖外网）。"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend_api.services import auction_service
from backend_api.utils.fuyao_client import auction_item_to_record


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_basic_info (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    collect_enabled INTEGER DEFAULT 1
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO stock_basic_info (code, name) VALUES ('600519', '贵州茅台')")
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_auction_daily (
                    trade_date TEXT NOT NULL,
                    code TEXT NOT NULL,
                    auction_phase TEXT NOT NULL DEFAULT 'final',
                    thscode TEXT,
                    name TEXT,
                    data_status TEXT,
                    auction_price REAL,
                    auction_pct REAL,
                    auction_volume REAL,
                    auction_volume_shares REAL,
                    auction_amount REAL,
                    auction_unmatched REAL,
                    auction_unmatched_shares REAL,
                    auction_turnover_pct REAL,
                    auction_yesterday_ratio_pct REAL,
                    auction_volume_ratio REAL,
                    pre_close_price REAL,
                    open_price REAL,
                    last_price REAL,
                    float_market_cap REAL,
                    source TEXT DEFAULT 'fuyao',
                    response_timestamp INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (trade_date, code, auction_phase)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_auction_benchmark (
                    trade_date TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    thscode TEXT,
                    code TEXT,
                    name TEXT,
                    auction_pct REAL,
                    tags TEXT,
                    source TEXT DEFAULT 'fuyao',
                    response_timestamp INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (trade_date, seq)
                )
                """
            )
        )
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_auction_item_to_record_volume_in_hands():
    """Fuyao auction_volume 已是手；示例 12600 手应原样入库，股数=手×100。"""
    row = auction_item_to_record(
        {
            "ticker": "600519",
            "thscode": "600519.SH",
            "name": "贵州茅台",
            "auction_volume": 12600,
            "auction_unmatched": 800,
            "auction_pct": 0.35,
            "auction_price": 1421.0,
            "auction_amount": 12600 * 100 * 1421.0,
        }
    )
    assert row["code"] == "600519"
    assert row["auction_volume"] == 12600
    assert row["auction_volume_shares"] == 1260000.0
    assert row["auction_unmatched"] == 800
    assert row["auction_unmatched_shares"] == 80000.0


def test_auction_item_to_record_ticker_fallback_from_thscode():
    row = auction_item_to_record(
        {
            "thscode": "600519.SH",
            "name": "贵州茅台",
            "auction_volume": 12600,
            "auction_pct": 0.35,
        }
    )
    assert row["code"] == "600519"
    assert row["thscode"] == "600519.SH"
    assert row["auction_volume"] == 12600
    assert row["auction_volume_shares"] == 1260000.0


@patch("backend_api.utils.fuyao_client._fuyao_get_json")
def test_fetch_auction_snapshot_not_ready_message(mock_get):
    from backend_api.utils.fuyao_client import fetch_a_share_auction_snapshot

    mock_get.return_value = {
        "ok": True,
        "data": {
            "timestamp": 1786689000000,
            "auction_phase": "final",
            "data_status": "not_ready",
            "total": 0,
            "item": [],
        },
        "raw": {},
    }
    result = fetch_a_share_auction_snapshot(["600519"], stage="final")
    assert result["ok"] is False
    assert "not_ready" in (result.get("error") or "")
    assert result.get("data_status") == "not_ready"


@patch("backend_api.services.auction_service.fetch_a_share_auction_snapshot")
@patch("backend_api.services.auction_service.fetch_a_share_auction_short_term_benchmark")
def test_collect_auction_snapshot(mock_benchmark, mock_snapshot, db_session):
    mock_benchmark.return_value = {
        "ok": True,
        "date": "2026-09-22",
        "timestamp": 1786689000000,
        "items": [{"ticker": "600519", "name": "贵州茅台", "auction_pct": 0.35, "tags": ["高开"]}],
    }
    mock_snapshot.return_value = {
        "ok": True,
        "auction_phase": "final",
        "data_status": "ready",
        "timestamp": 1786689000000,
        "items": [
            {
                "ticker": "600519",
                "thscode": "600519.SH",
                "name": "贵州茅台",
                "auction_price": 1421.0,
                "auction_pct": 0.35,
                "auction_volume": 12600,
            }
        ],
    }

    result = auction_service.collect_auction_snapshot(
        db_session,
        codes=["600519"],
        stage="final",
        refresh_benchmark=False,
    )
    assert result["success"] is True
    assert result["saved"] == 1

    listed = auction_service.query_auction_list(
        db_session,
        trade_date=result["trade_date"],
    )
    assert listed["total"] == 1
    assert listed["items"][0]["code"] == "600519"


@patch("backend_api.services.auction_service.fetch_a_share_auction_snapshot")
def test_query_auction_stock_prefers_db_without_live(mock_snapshot, db_session):
    """live=False 时有库数据直接返回，绝不请求 Fuyao。"""
    day = "2026-09-22"
    db_session.execute(
        text(
            """
            INSERT INTO stock_auction_daily (
                trade_date, code, auction_phase, name, auction_price, auction_pct, source
            ) VALUES (
                :d, '600519', 'final', '贵州茅台', 1421.0, 0.35, 'fuyao'
            )
            """
        ),
        {"d": day},
    )
    db_session.commit()

    out = auction_service.query_auction_stock(
        db_session, "600519", trade_date=day, live=False
    )
    assert out["success"] is True
    assert out["data"]["source_mode"] == "db"
    assert out["data"]["auction_pct"] == 0.35
    mock_snapshot.assert_not_called()


@patch("backend_api.services.auction_service.fetch_a_share_auction_snapshot")
def test_query_auction_stock_db_miss_no_fuyao_when_not_live(mock_snapshot, db_session):
    """live=False 且库中无当日该股时，不打外部接口。"""
    out = auction_service.query_auction_stock(
        db_session, "600519", trade_date="2026-09-22", live=False
    )
    assert out["success"] is False
    assert "库中暂无" in (out.get("message") or "")
    mock_snapshot.assert_not_called()


@patch("backend_api.services.auction_service.fetch_a_share_auction_snapshot")
def test_query_auction_stock_live_fallback_to_db_on_429(mock_snapshot, db_session):
    """live=True 遇 429 时回退库内当日数据。"""
    day = "2026-09-22"
    db_session.execute(
        text(
            """
            INSERT INTO stock_auction_daily (
                trade_date, code, auction_phase, name, auction_price, auction_pct, source
            ) VALUES (
                :d, '600519', 'final', '贵州茅台', 1421.0, 0.35, 'fuyao'
            )
            """
        ),
        {"d": day},
    )
    db_session.commit()
    mock_snapshot.return_value = {"ok": False, "error": "http_429", "code": 429}

    out = auction_service.query_auction_stock(
        db_session, "600519", trade_date=day, live=True
    )
    assert out["success"] is True
    assert out["data"]["source_mode"] == "db"
    assert out["data"]["live_error"] == "http_429"
