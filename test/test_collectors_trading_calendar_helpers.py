"""定时采集 main 中的休市判定与 trading_calendar_utils 一致。"""
import datetime
import unittest
from unittest.mock import MagicMock, patch


class TestCollectorsTradingCalendarHelpers(unittest.TestCase):
    @patch("backend_core.data_collectors.main.ApiSessionLocal")
    @patch("backend_core.data_collectors.main.is_market_session_closed")
    def test_cn_helper_delegates(self, mock_closed, mock_session_local):
        mock_closed.return_value = True
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        from backend_core.data_collectors import main

        self.assertTrue(main._cn_session_closed_today())
        mock_closed.assert_called_once()
        args = mock_closed.call_args[0]
        self.assertEqual(args[1], "CN")
        self.assertEqual(args[2], datetime.date.today())


if __name__ == "__main__":
    unittest.main()
