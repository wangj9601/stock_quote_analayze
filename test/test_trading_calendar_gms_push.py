"""GMS 定时推送与 trading_calendar / 周末 / 分市场 判定。"""
import datetime
import unittest
from unittest.mock import MagicMock, patch

from backend_api.utils.trading_calendar_utils import (
    is_weekend,
    should_skip_gms_scheduled_notification,
)


class TestTradingCalendarGmsPush(unittest.TestCase):
    def test_is_weekend(self):
        self.assertTrue(is_weekend(datetime.date(2026, 5, 9)))   # 周六
        self.assertTrue(is_weekend(datetime.date(2026, 5, 10)))  # 周日
        self.assertFalse(is_weekend(datetime.date(2026, 5, 8)))

    def test_empty_watchlist_no_skip(self):
        db = MagicMock()
        skip, reason = should_skip_gms_scheduled_notification(db, datetime.date(2026, 5, 9), set())
        self.assertFalse(skip)
        self.assertEqual(reason, "")

    @patch("backend_api.utils.trading_calendar_utils.is_market_session_closed")
    def test_cn_holiday_hk_still_open_mixed_watchlist_no_skip(self, mock_closed):
        """A股休市、港股仍交易时，同时持有 A+H 的用户仍应推送。"""
        db = MagicMock()

        def _closed(_db, market, _d):
            return market == "CN"

        mock_closed.side_effect = _closed
        skip, _ = should_skip_gms_scheduled_notification(
            db,
            datetime.date(2026, 5, 6),
            {"CN", "HK"},
        )
        self.assertFalse(skip)

    @patch("backend_api.utils.trading_calendar_utils.is_market_session_closed")
    def test_hk_only_user_cn_holiday_weekday_no_skip(self, mock_closed):
        """仅港股持仓：A股放假不影响。"""
        db = MagicMock()
        mock_closed.side_effect = lambda _db, m, _d: m == "CN"
        skip, _ = should_skip_gms_scheduled_notification(
            db,
            datetime.date(2026, 5, 6),
            {"HK"},
        )
        self.assertFalse(skip)

    @patch("backend_api.utils.trading_calendar_utils.is_market_session_closed")
    def test_cn_only_user_cn_closed_skip(self, mock_closed):
        mock_closed.side_effect = lambda _db, m, _d: m == "CN"
        skip, reason = should_skip_gms_scheduled_notification(
            MagicMock(),
            datetime.date(2026, 5, 6),
            {"CN"},
        )
        self.assertTrue(skip)
        self.assertIn("A股", reason)

    @patch("backend_api.utils.trading_calendar_utils.is_market_session_closed")
    def test_both_markets_closed_skip(self, mock_closed):
        mock_closed.return_value = True
        skip, _ = should_skip_gms_scheduled_notification(
            MagicMock(),
            datetime.date(2026, 5, 6),
            {"CN", "HK"},
        )
        self.assertTrue(skip)


if __name__ == "__main__":
    unittest.main()
