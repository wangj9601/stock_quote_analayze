"""GMS 左侧买点「均值收敛态得分下限」可选收紧逻辑"""

import unittest

from backend_core.strategies.gms.models import GMSIndicators
from backend_core.strategies.gms.signal_detector import GMSSignalDetector


def _base_ind_left_eligible():
    """满足典型左侧前置 + 粘合 + 地量（非 S/A 路径），score_accumulation=35"""
    return GMSIndicators(
        code="000001",
        date="2026-04-22",
        market_type="CN",
        delta=-0.15,
        d=14.31,
        ratio_d20=-0.011,
        ratio_d1=-0.011,
        instant_deviation=-0.78,
        rising_days=9,
        falling_days=11,
        avg_volume_20d=142800.0,
        current_volume=106200.0,
        ratio_d=-0.0545,
        volume_ratio=0.74,
        fz_ratio=11 / 9,
        score_accumulation=35.0,
        score_momentum=-10.0,
        score_total=35.0,
        accumulation_grade="",
        momentum_grade="",
    )


class TestLeftBuyMinAccumulation(unittest.TestCase):
    def test_default_min_zero_left_passes(self):
        d = GMSSignalDetector({"left_buy": {"min_accumulation_score": 0}})
        ind = _base_ind_left_eligible()
        self.assertTrue(d.detect_left_buy(ind))

    def test_min_40_blocks_low_accumulation(self):
        d = GMSSignalDetector({"left_buy": {"min_accumulation_score": 40}})
        ind = _base_ind_left_eligible()
        self.assertFalse(d.detect_left_buy(ind))

    def test_min_40_allows_high_accumulation(self):
        d = GMSSignalDetector({"left_buy": {"min_accumulation_score": 40}})
        ind = _base_ind_left_eligible()
        ind.score_accumulation = 72.0
        self.assertTrue(d.detect_left_buy(ind))


if __name__ == "__main__":
    unittest.main()
