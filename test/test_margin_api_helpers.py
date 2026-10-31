# -*- coding: utf-8 -*-
"""两融 API 辅助逻辑：信号文案与 rz_net。"""

from backend_api.stock.margin import DISCLAIMER, _compute_signal, _rz_net


def test_rz_net():
    assert _rz_net({"rzmre": 100, "rzche": 40}) == 60
    assert _rz_net({"rzmre": None, "rzche": None}) is None


def test_compute_signal_none_risk():
    series = []
    for i in range(10):
        series.append(
            {
                "code": "600000",
                "name": "浦发",
                "trade_date": f"2026-10-{i + 1:02d}",
                "rzye": 1e9,
                "rzmre": 1e7,
                "rzche": 9e6,
                "rqye": 0,
                "rqyl": 0,
                "rqmcl": 0,
                "rqchl": 0,
                "rzrqye": 1e9,
                "source": "tushare",
            }
        )
    sig = _compute_signal(
        series,
        trade_date="2026-10-10",
        float_mv=5e10,
        float_mv_source="test",
    )
    assert sig["available"] is True
    assert sig["squeeze_risk"] in ("none", "low", "mid", "high")
    assert "squeeze_label" in sig
    assert DISCLAIMER in sig["disclaimer"]


def test_compute_signal_high_when_collapse():
    series = []
    for i in range(12):
        # 前段高余额，末日骤降 + 净偿还
        rzye = 1e10 if i < 11 else 8e9
        series.append(
            {
                "code": "600000",
                "name": "浦发",
                "trade_date": f"2026-10-{i + 1:02d}",
                "rzye": rzye,
                "rzmre": 1e6,
                "rzche": 5e8,
                "rqye": 0,
                "rqyl": 0,
                "rqmcl": 0,
                "rqchl": 0,
                "rzrqye": rzye,
                "source": "tushare",
            }
        )
    sig = _compute_signal(
        series,
        trade_date="2026-10-12",
        float_mv=1e10,  # crowding = 80%
        float_mv_source="test",
    )
    assert sig["available"] is True
    assert sig["flags"]["high_crowding"] is True
    assert sig["squeeze_risk"] in ("mid", "high")
