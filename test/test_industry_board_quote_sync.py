# -*- coding: utf-8 -*-
"""行业板实时↔历史指数互补单测。"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend_core.data_collectors.akshare import industry_board_quote_sync as mod


def test_ymd_helpers():
    assert mod._ymd("2026-09-11") == "2026-09-11"
    assert mod._ymd(None) is None


def test_supplement_calls_both_directions(monkeypatch):
    session = MagicMock()
    calls = {"rt": 0, "hist": 0}

    def fake_rt(sess, *, asof_date=None):
        calls["rt"] += 1
        return {"updated": 3, "asof_date": asof_date}

    def fake_hist(sess, *, trade_date):
        calls["hist"] += 1
        return {"upserted": 1, "trade_date": trade_date}

    monkeypatch.setattr(mod, "supplement_realtime_from_historical", fake_rt)
    monkeypatch.setattr(mod, "supplement_historical_from_realtime", fake_hist)

    out = mod.supplement_industry_board_quotes(
        session, trade_date="2026-09-11", commit=True
    )
    assert calls["rt"] == 1
    assert calls["hist"] == 1
    assert out["realtime_from_hist"]["updated"] == 3
    assert out["hist_from_realtime"]["upserted"] == 1
    session.commit.assert_called_once()


def test_supplement_historical_requires_trade_date():
    session = MagicMock()
    out = mod.supplement_historical_from_realtime(session, trade_date=None)
    assert out["upserted"] == 0
    assert out.get("error") == "missing_trade_date"
    session.execute.assert_not_called()
