"""相对轮动：平坦相对强度停在 100，加速段进入领先象限。"""

from backend_api.utils.board_rotation import build_rotation, compute_rrg, quadrant


def test_flat_relative_strength_sits_on_the_cross():
    closes = [10] * 12
    bench = [5] * 12
    points = compute_rrg(closes, bench, window=4)
    last = points[-1]
    assert last["rs_ratio"] == 100
    assert last["rs_momentum"] == 100
    assert last["quadrant"] == "neutral"
    assert points[0]["rs_ratio"] is None


def test_accelerating_relative_strength_ends_leading():
    # 前半段贴着基准，后半段相对涨速越来越快，RS-Ratio 本身在抬升。
    closes = [10] * 16
    step = 0.2
    price = 10.0
    for _ in range(10):
        price += step
        step += 0.35
        closes.append(round(price, 4))
    bench = [10] * len(closes)
    points = compute_rrg(closes, bench, window=5)
    last = points[-1]
    assert last["rs_ratio"] > 100
    assert last["rs_momentum"] > 100
    assert last["quadrant"] == "leading"


def test_falling_relative_strength_is_not_leading():
    closes = [20 - index * 0.4 for index in range(24)]
    bench = [10] * len(closes)
    last = compute_rrg(closes, bench, window=5)[-1]
    assert last["quadrant"] in ("lagging", "weakening")
    assert last["quadrant"] != "leading"


def test_build_rotation_aligns_dates_and_drops_short_boards():
    bench = [{"date": f"2026-01-{day:02d}", "close": 10} for day in range(1, 25)]
    long_board = [
        {
            "board_code": "881001",
            "board_name": "半导体",
            "trade_date": bar["date"],
            "close": 10 + index * 0.8,
        }
        for index, bar in enumerate(bench)
    ]
    short_board = [
        {
            "board_code": "881099",
            "board_name": "太短",
            "trade_date": bench[0]["date"],
            "close": 10,
        }
    ]
    payload = build_rotation(bench, long_board + short_board, window=5)
    assert payload["benchmark_name"] == "沪深300"
    assert payload["board_count"] == 1
    assert payload["boards"][0]["board_code"] == "881001"
    assert payload["dates"]
    assert payload["dates"][0] >= "2026-01-01"
    assert payload["boards"][0]["points"][-1]["trade_date"] == payload["dates"][-1]
    assert quadrant(101, 101) == "leading"
    assert quadrant(101, 99) == "weakening"
    assert quadrant(99, 99) == "lagging"
    assert quadrant(99, 101) == "improving"


def test_build_rotation_notes_when_benchmark_is_too_short():
    payload = build_rotation([{"date": "2026-01-02", "close": 10}], [], window=5)
    assert payload["boards"] == []
    assert "基准" in payload["note"]
