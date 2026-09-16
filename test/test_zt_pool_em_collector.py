# -*- coding: utf-8 -*-
"""涨停池采集器：空表/异常返回 success=False，不抛崩。"""

from backend_core.data_collectors.akshare import zt_pool_em as mod


def test_collect_zt_pool_em_empty(monkeypatch):
    class FakeCollector(mod.ZtPoolEmCollector):
        def fetch_dataframe(self):
            raise RuntimeError("empty")

    monkeypatch.setattr(mod, "ZtPoolEmCollector", FakeCollector)
    # still use real class path — patch collect to use Fake
    result = FakeCollector(trade_date="2026-09-15").collect()
    assert result["success"] is False
    assert "error" in result


def test_dataframe_to_rows_normalizes_code():
    import pandas as pd

    c = mod.ZtPoolEmCollector(trade_date="2026-09-15")
    df = pd.DataFrame(
        [
            {
                "代码": "2709",
                "名称": "天赐材料",
                "涨跌幅": 10.0,
                "最新价": 33.0,
                "成交额": 1e9,
                "流通市值": 1e10,
                "总市值": 1e10,
                "换手率": 2.0,
                "封板资金": 1e8,
                "首次封板时间": "093000",
                "最后封板时间": "093000",
                "炸板次数": 0,
                "涨停统计": "1/1",
                "连板数": 2,
                "所属行业": "化学制品",
            }
        ]
    )
    rows = c.dataframe_to_rows(df)
    assert len(rows) == 1
    assert rows[0]["code"] == "002709"
    assert rows[0]["board_count"] == 2
    assert rows[0]["first_seal_time"] == "09:30:00"
