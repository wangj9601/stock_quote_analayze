"""RPE 流动性分层与板别解析单测。"""

from backend_core.strategies.rpe.config import get_default_rpe_config
from backend_core.strategies.rpe.filters import liquidity_ok
from backend_core.strategies.rpe.listed_board import (
    board_segment_label,
    resolve_listed_board_segment,
    resolve_min_avg_amount,
)


def test_resolve_listed_board_segment():
    assert resolve_listed_board_segment("600519") == "MAIN"
    assert resolve_listed_board_segment("000001") == "MAIN"
    assert resolve_listed_board_segment("001979") == "MAIN"
    assert resolve_listed_board_segment("002415") == "SZ_SME"
    assert resolve_listed_board_segment("300750") == "CYB"
    assert resolve_listed_board_segment("688981") == "KCB"
    assert resolve_listed_board_segment("830799") == "BJ"
    assert resolve_listed_board_segment("920000") == "BJ"
    assert resolve_listed_board_segment("bad") == "DEFAULT"
    assert board_segment_label("SZ_SME") == "中小板"


def test_resolve_min_avg_amount_by_board():
    cfg = get_default_rpe_config()["liquidity"]
    seg, amt = resolve_min_avg_amount("600000", cfg)
    assert seg == "MAIN" and amt == 30_000_000
    seg, amt = resolve_min_avg_amount("002001", cfg)
    assert seg == "SZ_SME" and amt == 20_000_000
    seg, amt = resolve_min_avg_amount("300001", cfg)
    assert seg == "CYB" and amt == 15_000_000
    seg, amt = resolve_min_avg_amount("688001", cfg)
    assert seg == "KCB" and amt == 15_000_000
    seg, amt = resolve_min_avg_amount("830001", cfg)
    assert seg == "BJ" and amt == 5_000_000


def test_resolve_min_avg_amount_legacy_fallback():
    legacy = {"min_avg_amount": 5_000_000.0, "min_avg_turnover_rate": 0.5}
    seg, amt = resolve_min_avg_amount("600000", legacy)
    assert seg == "MAIN" and amt == 5_000_000


def test_liquidity_ok_board_tiers():
    cfg = get_default_rpe_config()["liquidity"]
    # 主板：800 万 < 3000 万 → 不过
    thin = [{"amount": 8_000_000, "turnover_rate": 1.0} for _ in range(20)]
    r = liquidity_ok(thin, stock_code="600000", liq_cfg=cfg)
    assert r["liquidity_ok"] is False
    assert r["board_segment"] == "MAIN"
    assert r["min_avg_amount_applied"] == 30_000_000

    # 主板：3.5 亿额 + 换手够 → 过
    rich = [{"amount": 350_000_000, "turnover_rate": 1.0} for _ in range(20)]
    r2 = liquidity_ok(rich, stock_code="600000", liq_cfg=cfg)
    assert r2["liquidity_ok"] is True

    # 额够但换手 0.3% < 0.8% → 不过
    low_tr = [{"amount": 350_000_000, "turnover_rate": 0.3} for _ in range(20)]
    r3 = liquidity_ok(low_tr, stock_code="600000", liq_cfg=cfg)
    assert r3["liquidity_ok"] is False

    # 中小板：1800 万 < 2000 万 → 不过；2200 万 → 过
    sme_fail = [{"amount": 18_000_000, "turnover_rate": 1.0} for _ in range(20)]
    assert liquidity_ok(sme_fail, stock_code="002001", liq_cfg=cfg)["liquidity_ok"] is False
    sme_ok = [{"amount": 22_000_000, "turnover_rate": 1.0} for _ in range(20)]
    assert liquidity_ok(sme_ok, stock_code="002001", liq_cfg=cfg)["liquidity_ok"] is True

    # 创业板 1600 万 > 1500 万
    cyb = [{"amount": 16_000_000, "turnover_rate": 0.9} for _ in range(20)]
    assert liquidity_ok(cyb, stock_code="300001", liq_cfg=cfg)["liquidity_ok"] is True

    # 北证 600 万 > 500 万
    bj = [{"amount": 6_000_000, "turnover_rate": 0.9} for _ in range(20)]
    assert liquidity_ok(bj, stock_code="830001", liq_cfg=cfg)["liquidity_ok"] is True


def test_default_turnover_is_0_8():
    assert get_default_rpe_config()["liquidity"]["min_avg_turnover_rate"] == 0.8
