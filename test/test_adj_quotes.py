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
    SOURCE_AKSHARE_SINA_QFQ,
    SOURCE_BAOSTOCK_QFQ,
    apply_qfq_to_bars,
    ensure_adj_factors,
    fetch_baostock_qfq_factors,
    fetch_qfq_factors,
    fetch_sina_qfq_factors,
    to_baostock_symbol,
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
            "date": ["2024-01-02", "2024-01-03", "1900-01-01"],
            "qfq_factor": [1.0, 1.5, 14.5],
        }
    )
    fake_ak = MagicMock()
    fake_ak.stock_zh_a_daily.return_value = df
    with patch.dict(sys.modules, {"akshare": fake_ak}):
        rows = fetch_sina_qfq_factors("600519")
    # 1900-01-01 占位行应丢弃
    assert len(rows) == 2
    assert rows[0]["code"] == "600519"
    assert rows[0]["adj_factor"] == 1.0
    assert rows[1]["adj_factor"] == 1.5
    assert all(r["trade_date"].year > 1900 for r in rows)
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

    with patch("utils.adj_quotes.fetch_qfq_factors") as fetch_mock:
        out = ensure_adj_factors(db, "600519", max_age_days=5, force_refresh=False)
    fetch_mock.assert_not_called()
    assert out["factor_fetched"] is False
    assert out["adj_factor_asof"] == today.strftime("%Y-%m-%d")


def test_to_baostock_symbol():
    assert to_baostock_symbol("600519") == "sh.600519"
    assert to_baostock_symbol("000001") == "sz.000001"


def test_fetch_qfq_factors_auto_falls_back_to_baostock():
    bao_rows = [
        {
            "code": "600519",
            "trade_date": date(2024, 1, 2),
            "adj_factor": 1.1,
            "source": SOURCE_BAOSTOCK_QFQ,
        }
    ]
    with patch(
        "utils.adj_quotes.fetch_sina_qfq_factors",
        side_effect=AdjQuotesError("新浪限流"),
    ), patch(
        "utils.adj_quotes.fetch_baostock_qfq_factors",
        return_value=bao_rows,
    ):
        rows, src = fetch_qfq_factors("600519", factor_source="auto")
    assert src == SOURCE_BAOSTOCK_QFQ
    assert rows[0]["adj_factor"] == 1.1


def test_fetch_qfq_factors_baostock_only():
    bao_rows = [
        {
            "code": "600519",
            "trade_date": date(2024, 1, 2),
            "adj_factor": 0.9,
            "source": SOURCE_BAOSTOCK_QFQ,
        }
    ]
    with patch(
        "utils.adj_quotes.fetch_sina_qfq_factors"
    ) as sina_mock, patch(
        "utils.adj_quotes.fetch_baostock_qfq_factors",
        return_value=bao_rows,
    ):
        rows, src = fetch_qfq_factors("600519", factor_source="baostock")
    sina_mock.assert_not_called()
    assert src == SOURCE_BAOSTOCK_QFQ
    assert len(rows) == 1


def test_fetch_baostock_parses_rows():
    class FakeRs:
        error_code = "0"
        fields = [
            "code",
            "dividOperateDate",
            "foreAdjustFactor",
            "backAdjustFactor",
            "adjustFactor",
        ]
        _rows = [
            ["sh.600519", "2024-01-02", "0.8", "1.2", "1.2"],
            ["sh.600519", "2024-06-01", "0.9", "1.1", "1.1"],
        ]
        _i = -1

        def next(self):
            self._i += 1
            return self._i < len(self._rows)

        def get_row_data(self):
            return self._rows[self._i]

    class FakeBs:
        def login(self):
            return MagicMock(error_code="0")

        def logout(self):
            return None

        def query_adjust_factor(self, **kwargs):
            return FakeRs()

    with patch.dict(sys.modules, {"baostock": FakeBs()}):
        rows = fetch_baostock_qfq_factors("600519")
    assert len(rows) == 2
    assert rows[0]["source"] == SOURCE_BAOSTOCK_QFQ
    assert rows[0]["adj_factor"] == 0.8
    assert rows[1]["adj_factor"] == 0.9


def test_ensure_force_refresh_uses_factor_source():
    db = MagicMock()
    today = date.today()

    def _execute(sql, params=None):
        result = MagicMock()
        result.fetchone.return_value = (today, None, SOURCE_AKSHARE_SINA_QFQ)
        result.fetchall.return_value = [(today, 1.0)]
        return result

    db.execute.side_effect = _execute
    bao_rows = [
        {
            "code": "600519",
            "trade_date": today,
            "adj_factor": 1.0,
            "source": SOURCE_BAOSTOCK_QFQ,
        }
    ]
    with patch(
        "utils.adj_quotes.fetch_qfq_factors",
        return_value=(bao_rows, SOURCE_BAOSTOCK_QFQ),
    ) as fetch_mock, patch(
        "utils.adj_quotes.upsert_adj_factors", return_value=1
    ):
        out = ensure_adj_factors(
            db, "600519", force_refresh=True, factor_source="baostock"
        )
    fetch_mock.assert_called_once()
    assert fetch_mock.call_args.kwargs.get("factor_source") == "baostock"
    assert out["source"] == SOURCE_BAOSTOCK_QFQ
    assert out["factor_fetched"] is True
