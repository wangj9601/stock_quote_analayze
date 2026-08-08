# -*- coding: utf-8 -*-
"""板块分析聚合：过滤与编排冒烟。"""

from backend_core.analysis.board_signals import (
    _enrich_items,
    _filter_gms,
    _filter_rpe,
    _filter_sbbr,
    _filter_urt,
)
from backend_core.analysis.trade_advice import build_trade_advice


def test_filters():
    # 默认 min_score=0：仅买点
    assert len(_filter_gms([{"left_buy_signal": True}, {"score_total": 80}])) == 1
    # 总分达标
    assert (
        len(
            _filter_gms(
                [{"left_buy_signal": True}, {"score_total": 80}],
                min_score=60,
            )
        )
        == 2
    )
    assert len(_filter_urt([{"buy_signal": True}, {"buy_signal": False}])) == 1
    entry, watch = _filter_sbbr(
        [{"entry_signal": True}, {"bottom_matched": True}, {"entry_signal": False}]
    )
    assert len(entry) == 1 and len(watch) == 1
    assert len(_filter_rpe([{"watch_only": True}, {"signal_type": "x"}])) == 1


def test_sbbr_advice_defense():
    adv = build_trade_advice(
        "sbbr",
        {
            "entry_signal": True,
            "entry_low": 8.5,
            "defense_low": 8.0,
            "defense_high": 8.2,
            "box_resistance": 9.5,
        },
    )
    assert adv["action"] == "buy"
    assert adv["stop_zone"]["basis"] == "defense"


def test_enrich_items_last_close():
    items = _enrich_items(
        "gms",
        [{"code": "000001", "left_buy_signal": True}],
        names={"000001": "平安银行"},
        ref_by_code={},
        last_close_by_code={"000001": 12.345},
    )
    assert items[0]["last_close"] == 12.35
    assert items[0]["name"] == "平安银行"
