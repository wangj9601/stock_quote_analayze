"""SBBR 告警与回测辅助逻辑单测。"""

from backend_core.strategies.sbbr.alert_hooks import _format_entry_message, notify_sbbr_events
from backend_core.strategies.sbbr.backtest_runner import _count_by, _hit_rate
from backend_core.strategies.sbbr.config import get_default_sbbr_config


class _FakeLoader:
    def load_bars(self, code, end_date=None, limit=120):
        # 信号日后上涨
        bars = []
        p = 10.0
        for i in range(80):
            d = f"2024-06-{(i % 28) + 1:02d}"
            if i > 40:
                p *= 1.02
            bars.append(
                {
                    "date": f"2024-06-{min(i + 1, 28):02d}" if i < 28 else f"2024-07-{(i - 27):02d}",
                    "open": p,
                    "high": p * 1.03,
                    "low": p * 0.98,
                    "close": p,
                    "volume": 100,
                    "turnover_rate": 5,
                }
            )
        # 固定信号日
        bars[40]["date"] = "2024-06-15"
        return bars


def test_format_entry_message():
    msg = _format_entry_message(
        [{"code": "000001", "name": "测试", "bottom_mode": "range_accumulation", "close": 10, "defense_low": 9.5}],
        "2024-06-15",
    )
    assert "000001" in msg
    assert "入场信号" in msg


def test_notify_without_push_service():
    r = notify_sbbr_events(
        entry_rows=[{"code": "1", "name": "a", "close": 1, "defense_low": 0.9}],
        position_events=[],
        trade_date="2024-01-01",
        config=get_default_sbbr_config(),
    )
    assert "errors" in r


def test_hit_rate_helper():
    samples = [
        {
            "code": "000001",
            "date": "2024-06-15",
            "close": 10.0,
            "defense_low": 9.0,
        }
    ]
    summary = _hit_rate(_FakeLoader(), samples, horizon=30, target_pct=0.2, cfg=get_default_sbbr_config())
    assert summary["total_samples"] >= 0
    assert "hit_rate" in summary


def test_count_by():
    assert _count_by([{"exit_reason": "a"}, {"exit_reason": "a"}, {"exit_reason": "b"}], "exit_reason") == {
        "a": 2,
        "b": 1,
    }
