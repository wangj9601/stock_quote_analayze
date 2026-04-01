from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_core.data_collectors.akshare.historical_turnover_rate import A_SHARE_LOT_SIZE


def calc_turnover_rate_from_hand(volume_hand: float, free_float_shares: float) -> float:
    """A股换手率：成交量(手) -> 股 后再计算百分比。"""
    volume_shares = volume_hand * A_SHARE_LOT_SIZE
    return round(volume_shares / free_float_shares * 100, 4)


def test_turnover_rate_formula_with_hand_volume() -> None:
    # 10000手 = 1,000,000股；流通股本 1e10 股 => 换手率 0.01%
    rate = calc_turnover_rate_from_hand(volume_hand=10000, free_float_shares=1e10)
    assert rate == 0.01

