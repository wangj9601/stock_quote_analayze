"""
标准版 vs 增强版同股分数对比冒烟（需连接真实数据库）。

运行：
  python test/test_gms_scoring_smoke_compare.py
  python -m pytest test/test_gms_scoring_smoke_compare.py -v -s
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import desc, func  # noqa: E402

from backend_api.models import MeanFrequencyResonanceIndicators  # noqa: E402
from backend_core.database.db import SessionLocal  # noqa: E402
from backend_core.strategies.gms.config import GMSConfigManager  # noqa: E402
from backend_core.strategies.gms.data_loader import GMSDataLoader  # noqa: E402
from backend_core.strategies.gms.indicators_calculator import GMSIndicatorsCalculator  # noqa: E402
from backend_core.strategies.gms.scoring.penalties import _close_price  # noqa: E402

PENALTY_POINTS = 10
SCAN_POOL_SIZE = 80


def _build_configs() -> tuple[Dict[str, Any], Dict[str, Any]]:
    mgr = GMSConfigManager()
    base = copy.deepcopy(mgr.get_config())
    standard = copy.deepcopy(base)
    standard.setdefault("scoring", {})["mechanism"] = "tiered_dual_max"
    standard["scoring"]["penalty_rules"] = []

    enhanced = copy.deepcopy(base)
    enhanced.setdefault("scoring", {})["mechanism"] = "tiered_dual_penalty"
    enhanced["scoring"]["penalty_rules"] = [
        {
            "id": "close_below_ma60",
            "enabled": True,
            "points": PENALTY_POINTS,
            "label": "收盘低于60日均线",
        }
    ]
    return standard, enhanced


def _deviation_series(loader: GMSDataLoader, code: str, date: str, market: str, stable_days: int):
    if stable_days <= 1:
        return None
    multi = loader.load_indicators_multi_day([code], date, market, days=stable_days)
    by_code: Dict[str, List[Dict[str, Any]]] = {}
    for r in multi:
        by_code.setdefault(r["code"], []).append(r)
    rows = by_code.get(code) or []
    rows.sort(key=lambda x: x["date"])
    recent = rows[-stable_days:]
    if len(recent) < stable_days:
        return None
    return [float(r.get("instant_deviation", 0) or 0) for r in recent]


def _score_one(
    row: Dict[str, Any],
    config: Dict[str, Any],
    loader: GMSDataLoader,
) -> Optional[Any]:
    stable_days = int((config.get("scoring") or {}).get("instant_deviation_stable_days", 3))
    market = row.get("market_type") or "CN"
    date = str(row.get("date") or "")[:10]
    code = str(row.get("code") or "")
    dev = _deviation_series(loader, code, date, market, stable_days)
    return GMSIndicatorsCalculator(config).calculate(row, instant_deviation_series=dev)


def _is_below_ma60(row: Dict[str, Any]) -> bool:
    ma60 = row.get("ma60_d")
    if ma60 is None:
        return False
    close = _close_price(row)
    ma60_f = float(ma60)
    return close > 0 and ma60_f > 0 and close < ma60_f


def _latest_cn_trade_date(db) -> Optional[str]:
    dt = (
        db.query(func.max(MeanFrequencyResonanceIndicators.date))
        .filter(MeanFrequencyResonanceIndicators.market_type == "CN")
        .scalar()
    )
    return str(dt)[:10] if dt else None


def _sample_codes(db, trade_date: str, limit: int = SCAN_POOL_SIZE) -> List[str]:
    rows = (
        db.query(MeanFrequencyResonanceIndicators.code)
        .filter(
            MeanFrequencyResonanceIndicators.market_type == "CN",
            MeanFrequencyResonanceIndicators.date == trade_date,
        )
        .order_by(MeanFrequencyResonanceIndicators.code)
        .limit(limit)
        .all()
    )
    return [str(r[0]).strip() for r in rows if r[0]]


def run_smoke_compare(db, *, verbose: bool = True, penalty_points: int = PENALTY_POINTS) -> Dict[str, Any]:
    """对真实库样本股对比标准版与增强版分数，返回结构化结果。"""
    trade_date = _latest_cn_trade_date(db)
    if not trade_date:
        raise RuntimeError("指标表无 CN 数据，无法冒烟")

    codes = _sample_codes(db, trade_date)
    if not codes:
        raise RuntimeError(f"日期 {trade_date} 无可用股票代码")

    loader = GMSDataLoader(db)
    rows = loader.load_indicators(codes, trade_date, "CN", use_latest_per_stock=False)
    if not rows:
        rows = loader.load_indicators(codes, trade_date, "CN", use_latest_per_stock=True)
    if not rows:
        raise RuntimeError(f"日期 {trade_date} 无法加载 GMS 指标行")

    standard_cfg, enhanced_cfg = _build_configs()
    if penalty_points != PENALTY_POINTS:
        enhanced_cfg["scoring"]["penalty_rules"][0]["points"] = penalty_points

    below_cases: List[Dict[str, Any]] = []
    above_cases: List[Dict[str, Any]] = []

    for row in rows:
        if row.get("ma60_d") is None:
            continue
        std_ind = _score_one(row, standard_cfg, loader)
        enh_ind = _score_one(row, enhanced_cfg, loader)
        if std_ind is None or enh_ind is None:
            continue

        close = _close_price(row)
        ma60 = float(row["ma60_d"])
        below = _is_below_ma60(row)
        case = {
            "code": row["code"],
            "date": row["date"],
            "close": round(close, 4),
            "ma60_d": round(ma60, 4),
            "below_ma60": below,
            "standard_total": float(std_ind.score_total),
            "enhanced_total": float(enh_ind.score_total),
            "score_base_total": float(getattr(enh_ind, "score_base_total", std_ind.score_total)),
            "penalty_deduction": float(getattr(enh_ind, "score_penalty_deduction", 0) or 0),
            "penalty_details": getattr(enh_ind, "penalty_details", []) or [],
            "score_accumulation": float(std_ind.score_accumulation),
            "score_momentum": float(std_ind.score_momentum),
        }
        if below:
            below_cases.append(case)
        else:
            above_cases.append(case)

    picked: List[Dict[str, Any]] = []
    if below_cases:
        picked.append(sorted(below_cases, key=lambda x: x["standard_total"], reverse=True)[0])
    if above_cases:
        picked.append(sorted(above_cases, key=lambda x: x["standard_total"], reverse=True)[0])
    for extra in below_cases[1:3]:
        if extra not in picked:
            picked.append(extra)
    for extra in above_cases[1:3]:
        if extra not in picked and len(picked) < 5:
            picked.append(extra)

    if verbose:
        _print_report(trade_date, len(rows), below_cases, above_cases, picked, penalty_points)

    return {
        "trade_date": trade_date,
        "scanned": len(rows),
        "below_ma60_count": len(below_cases),
        "above_ma60_count": len(above_cases),
        "cases": picked,
        "penalty_points": penalty_points,
    }


def _print_report(
    trade_date: str,
    scanned: int,
    below_cases: List[Dict[str, Any]],
    above_cases: List[Dict[str, Any]],
    picked: List[Dict[str, Any]],
    penalty_points: int,
) -> None:
    print("=" * 72)
    print("GMS 打分冒烟：标准版 tiered_dual_max vs 增强版 tiered_dual_penalty")
    print(f"交易日: {trade_date}  |  扫描: {scanned} 只  |  减分规则: close_below_ma60 -{penalty_points}")
    print(f"低于 MA60: {len(below_cases)} 只  |  高于/等于 MA60: {len(above_cases)} 只")
    print("=" * 72)
    if not picked:
        print("未找到同时具备 ma60_d 的有效样本，请检查指标表或行情补全链路。")
        return

    header = (
        f"{'代码':<8} {'收盘':>8} {'MA60':>8} {'MA60?':>6} "
        f"{'标准分':>7} {'增强分':>7} {'减分':>5} {'差值':>6}  减分明细"
    )
    print(header)
    print("-" * 72)
    for c in picked:
        diff = c["standard_total"] - c["enhanced_total"]
        flag = "低于" if c["below_ma60"] else "高于"
        details = ", ".join(
            f"{d.get('label', d.get('id'))}(-{d.get('points')})" for d in c["penalty_details"]
        ) or "-"
        print(
            f"{c['code']:<8} {c['close']:>8.2f} {c['ma60_d']:>8.2f} {flag:>6} "
            f"{c['standard_total']:>7.1f} {c['enhanced_total']:>7.1f} {c['penalty_deduction']:>5.1f} "
            f"{diff:>6.1f}  {details}"
        )
    print("=" * 72)
    print("预期：低于 MA60 → 增强分 = 标准分 - 减分；高于/等于 MA60 → 两版分数相同。")


def _assert_cases(result: Dict[str, Any]) -> None:
    if result["below_ma60_count"] < 1:
        pytest.skip("样本池中无「收盘低于 MA60」股票，跳过低于均线用例断言")
    if result["above_ma60_count"] < 1:
        pytest.skip("样本池中无「收盘高于/等于 MA60」股票，跳过高于均线用例断言")

    pts = result["penalty_points"]
    saw_below = saw_above = False
    for case in result["cases"]:
        if case["below_ma60"]:
            saw_below = True
            assert case["score_base_total"] == case["standard_total"]
            assert case["penalty_deduction"] == pts, case
            assert case["enhanced_total"] == max(0.0, case["standard_total"] - pts), case
        else:
            saw_above = True
            assert case["penalty_deduction"] == 0.0, case
            assert case["enhanced_total"] == case["standard_total"], case

    assert saw_below, "展示样本中应至少包含 1 只低于 MA60 的股票"
    assert saw_above, "展示样本中应至少包含 1 只高于/等于 MA60 的股票"


@pytest.mark.integration
def test_gms_standard_vs_penalty_smoke_compare():
    db = SessionLocal()
    try:
        result = run_smoke_compare(db, verbose=False)
        _assert_cases(result)
    except RuntimeError as e:
        pytest.skip(str(e))
    finally:
        db.close()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        outcome = run_smoke_compare(db, verbose=True)
        _assert_cases(outcome)
        print("\n[OK] 冒烟断言全部通过")
    except Exception as e:
        print(f"\n[FAIL] {e}", file=sys.stderr)
        raise
    finally:
        db.close()
