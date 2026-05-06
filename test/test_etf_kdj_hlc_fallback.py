"""ETF KDJ：high/low 为空时用收盘价兜底。"""
import unittest

from backend_core.data_collectors.akshare.etf_collector import ETFCollector


class TestEtfKdjHlcFallback(unittest.TestCase):
    def test_hlc_from_rows_fills_null_high_low(self):
        rows = [
            ("2026-01-01", 10.0, None, None, 10.5, 1000.0),
            ("2026-01-02", 10.5, 11.0, 10.0, 10.8, 1100.0),
        ]
        h, l, c = ETFCollector._hlc_from_rows_for_indicators(rows)
        self.assertEqual(h[0], 10.5)
        self.assertEqual(l[0], 10.5)
        self.assertEqual(c[0], 10.5)
        self.assertEqual(h[1], 11.0)
        self.assertEqual(l[1], 10.0)


if __name__ == "__main__":
    unittest.main()
