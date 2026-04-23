#!/usr/bin/env python3
"""
小样本演示：同一组指标在 left_buy.min_accumulation_score=0 vs 40 下「左侧」判定差异。
非全市场回测，仅供调参前快速 sanity check。用法：python manual_scripts/gms_left_min_probe.py
"""

from backend_core.strategies.gms.models import GMSIndicators
from backend_core.strategies.gms.signal_detector import GMSSignalDetector


def main():
    ind = GMSIndicators(
        code="demo",
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
    for mn in (0, 40):
        det = GMSSignalDetector({"left_buy": {"min_accumulation_score": mn}})
        ok = det.detect_left_buy(ind)
        print(f"min_accumulation_score={mn} -> left_buy={ok}")


if __name__ == "__main__":
    main()
