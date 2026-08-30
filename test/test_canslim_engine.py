"""CAN SLIM 引擎单元测试（不连真实库外网）。"""

from backend_core.strategies.canslim.config import get_default_canslim_config, merge_canslim_config
from backend_core.strategies.canslim.engine import CanSlimEngine, _apply_qfq, _cagr


def test_default_config_shape():
    cfg = get_default_canslim_config()
    assert "C" in cfg and "A" in cfg and "N" in cfg and "S" in cfg and "L" in cfg and "M" in cfg
    assert cfg["C"]["q_eps_yoy_min"] == 25.0
    assert cfg["L"]["rs_rating_min"] == 80
    assert cfg["M"]["index_ts_code"] == "000300.SH"
    assert cfg["I"]["enabled"] is False


def test_merge_override_rs():
    cfg = merge_canslim_config({"L": {"rs_rating_min": 90}})
    assert cfg["L"]["rs_rating_min"] == 90
    assert cfg["C"]["q_eps_yoy_min"] == 25.0


def test_cagr():
    assert abs(_cagr(1.0, 1.953125, 3) - 25.0) < 0.1
    assert _cagr(0, 1, 3) is None


def test_apply_qfq_scales_prices():
    bars = [
        {"date": "2024-01-01", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
        {"date": "2024-01-02", "open": 10.5, "high": 12.0, "low": 10.0, "close": 11.0, "volume": 120},
    ]
    factors = [("2024-01-01", 0.5), ("2024-01-02", 1.0)]
    out = _apply_qfq(bars, factors)
    # f_T=1.0 → 首日 *0.5
    assert abs(out[0]["close"] - 5.25) < 1e-9
    assert abs(out[1]["close"] - 11.0) < 1e-9
    assert out[0]["volume"] == 100


def test_eval_C_pass_fail():
    eng = CanSlimEngine.__new__(CanSlimEngine)
    eng.cfg = get_default_canslim_config()
    ok = eng.eval_C([{"end_date": "20250331", "q_eps_yoy": 30.0, "q_sales_yoy": 10.0}])
    assert ok["ok"] is True
    bad = eng.eval_C([{"end_date": "20250331", "q_eps_yoy": 10.0}])
    assert bad["ok"] is False
    empty = eng.eval_C([])
    assert empty["ok"] is False


def test_eval_A_requires_roe_and_years():
    eng = CanSlimEngine.__new__(CanSlimEngine)
    eng.cfg = get_default_canslim_config()
    rows = [
        {"end_date": "20241231", "basic_eps_yoy": 30.0, "eps": 1.5, "roe_waa": 20.0},
        {"end_date": "20231231", "basic_eps_yoy": 28.0, "eps": 1.2, "roe_waa": 18.0},
        {"end_date": "20221231", "basic_eps_yoy": 26.0, "eps": 0.9, "roe_waa": 17.0},
    ]
    assert eng.eval_A(rows)["ok"] is True
    low_roe = [
        {"end_date": "20241231", "basic_eps_yoy": 30.0, "eps": 1.5, "roe_waa": 10.0},
        {"end_date": "20231231", "basic_eps_yoy": 28.0, "eps": 1.2, "roe_waa": 10.0},
        {"end_date": "20221231", "basic_eps_yoy": 26.0, "eps": 0.9, "roe_waa": 10.0},
    ]
    assert eng.eval_A(low_roe)["ok"] is False


def test_eval_L_and_N_and_S():
    eng = CanSlimEngine.__new__(CanSlimEngine)
    eng.cfg = get_default_canslim_config()
    assert eng.eval_L(None)["ok"] is False
    assert eng.eval_L({"rs_rating": 79})["ok"] is False
    assert eng.eval_L({"rs_rating": 85, "date": "2026-01-01"})["ok"] is True

    bars = [{"date": f"d{i}", "high": 10.0, "close": 9.0, "open": 8.5, "volume": 200} for i in range(10)]
    bars[-1]["close"] = 9.0
    bars[-1]["high"] = 10.0
    # 9/10 = 0.9 >= 0.85
    n = eng.eval_N(bars, None)
    assert n["ok"] is True and n["near_high_ok"] is True

    n2 = eng.eval_N(
        [{"date": "d", "high": 10.0, "close": 5.0, "open": 5.0, "volume": 1}],
        {"status": "forming"},
    )
    assert n2["ok"] is True and n2["cupb_ok"] is True

    s_ok = eng.eval_S(
        5e8,  # 5 亿股
        {"open": 10.0, "close": 11.0, "volume": 150},
        {"mavol20": 100},
    )
    assert s_ok["ok"] is True
    s_big = eng.eval_S(30e8, {"open": 10.0, "close": 11.0, "volume": 150}, {"mavol20": 100})
    assert s_big["ok"] is False


def test_market_disabled_skips_index():
    class FakeLoader:
        def load_index_closes(self, *a, **k):
            raise AssertionError("should not load index when M disabled")

    eng = CanSlimEngine.__new__(CanSlimEngine)
    eng.cfg = merge_canslim_config({"M": {"enabled": False}})
    eng.loader = FakeLoader()
    m = eng.check_market("2026-01-01")
    assert m["ok"] is True and m["enabled"] is False
