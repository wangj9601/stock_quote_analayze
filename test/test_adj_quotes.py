"""前复权因子现算与新浪符号映射单测。"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from utils.adj_quotes import (  # noqa: E402
    AdjQuotesError,
    apply_qfq_to_bars,
    ensure_adj_factors,
    fetch_sina_qfq_factors,
    to_sina_symbol,
)


def test_to_sina_symbol_sh_sz():
    assert to_sina_symbol("600519") == "sh600519"
    assert to_sina_symbol("000001") == "sz000001"
    assert to_sina_symbol("sh600519") == "sh600519"
    with pytest.raises(AdjQuotesError):
        to_sina_symbol("00700")


def test_apply_qfq_to_bars_formula():
    bars = [
        {"date": "2024-01-02", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100},
        {"date": "2024-01-03", "open": 20.0, "high": 21.0, "low": 19.0, "close": 20.0, "volume": 200},
    ]
    # 首日因子 1，末日因子 2 → f_T=2；首日 scale=0.5，末日 scale=1
    factors = [(date(2024, 1, 2), 1.0), (date(2024, 1, 3), 2.0)]
    out = apply_qfq_to_bars(bars, factors)
    assert out[0]["close"] == pytest.approx(5.0)
    assert out[0]["volume"] == 100  # 不乘因子
    assert out[1]["close"] == pytest.approx(20.0)
    assert out[1]["price_adjust"] == "qfq"


def test_apply_qfq_forward_fill():
    bars = [
        {"date": "2024-01-02", "close": 10.0, "volume": 1},
        {"date": "2024-01-03", "close": 10.0, "volume": 1},
        {"date": "2024-01-04", "close": 10.0, "volume": 1},
    ]
    factors = [(date(2024, 1, 2), 1.0), (date(2024, 1, 4), 2.0)]
    out = apply_qfq_to_bars(bars, factors)
    assert out[0]["close"] == pytest.approx(5.0)
    assert out[1]["close"] == pytest.approx(5.0)
    assert out[2]["close"] == pytest.approx(10.0)


def test_apply_qfq_missing_factors_raises():
    with pytest.raises(AdjQuotesError):
        apply_qfq_to_bars([{"date": "2024-01-02", "close": 1.0}], [])


def test_fetch_sina_qfq_factors_parses_df():
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "qfq_factor": [1.0, 1.5],
        }
    )
    fake_ak = MagicMock()
    fake_ak.stock_zh_a_daily.return_value = df
    with patch.dict(sys.modules, {"akshare": fake_ak}):
        rows = fetch_sina_qfq_factors("600519")
    assert len(rows) == 2
    assert rows[0]["code"] == "600519"
    assert rows[0]["adj_factor"] == 1.0
    assert rows[1]["adj_factor"] == 1.5
    fake_ak.stock_zh_a_daily.assert_called()
    assert fake_ak.stock_zh_a_daily.call_args.kwargs.get("adjust") == "qfq-factor"


def test_ensure_adj_factors_rejects_hk():
    db = MagicMock()
    with pytest.raises(AdjQuotesError, match="A 股"):
        ensure_adj_factors(db, "00700")


def test_ensure_uses_cache_when_fresh():
    db = MagicMock()
    today = date.today()

    def _execute(sql, params=None):
        sql_s = str(sql)
        result = MagicMock()
        if "ORDER BY trade_date DESC" in sql_s:
            result.fetchone.return_value = (today, None, "akshare_sina_qfq")
            result.fetchall.return_value = []
        else:
            result.fetchone.return_value = None
            result.fetchall.return_value = [(today, 1.2)]
        return result

    db.execute.side_effect = _execute

    with patch("utils.adj_quotes.fetch_sina_qfq_factors") as fetch_mock:
        out = ensure_adj_factors(db, "600519", max_age_days=5, force_refresh=False)
    fetch_mock.assert_not_called()
    assert out["factor_fetched"] is False
    assert out["adj_factor_asof"] == today.strftime("%Y-%m-%d")
