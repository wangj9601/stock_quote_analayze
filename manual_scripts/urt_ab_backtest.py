# -*- coding: utf-8 -*-
"""URT 结构出场 A/B 回测：同区间批量对比并输出汇总表。

用法（项目根目录）:
  python manual_scripts/urt_ab_backtest.py
  python manual_scripts/urt_ab_backtest.py --start 2026-05-27 --end 2026-08-12
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal
from backend_core.strategies.urt.backtest_runner import run_urt_backtest

START_DEFAULT = "2026-05-27"
END_DEFAULT = "2026-08-12"


def _trail_override(pct: float) -> Dict[str, Any]:
    return {
        "structure_protect_trail_drawdown_pct": pct,
        "structure_fallback_trail_drawdown_pct": pct,
    }


SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "A0_baseline",
        "label": "基线(当前默认)",
        "min_score": 70.0,
        "config_overrides": None,
    },
    {
        "id": "A1_vol35",
        "label": "量能硬筛≥3.5",
        "min_score": 70.0,
        "config_overrides": {"volume_multiple": 3.5},
    },
    {
        "id": "A2_vol35_trail5",
        "label": "量能≥3.5 + 回撤5%",
        "min_score": 70.0,
        "config_overrides": {"volume_multiple": 3.5, **_trail_override(0.05)},
    },
    {
        "id": "B1_trail5",
        "label": "仅峰值回撤5%",
        "min_score": 70.0,
        "config_overrides": _trail_override(0.05),
    },
    {
        "id": "B2_trail6",
        "label": "仅峰值回撤6%",
        "min_score": 70.0,
        "config_overrides": _trail_override(0.06),
    },
    {
        "id": "C1_min75",
        "label": "最低得分75",
        "min_score": 75.0,
        "config_overrides": None,
    },
    {
        "id": "C2_vol35_min75",
        "label": "量能≥3.5 + 得分≥75",
        "min_score": 75.0,
        "config_overrides": {"volume_multiple": 3.5},
    },
]


def _pct(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def _num(v: Any, nd: int = 2) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def _exit_share(summary: Dict[str, Any], key: str) -> str:
    ses = summary.get("structure_exit_stats") or {}
    total = int(summary.get("total_signals") or 0)
    if not total:
        return "-"
    n = int(ses.get(key) or 0)
    return f"{n} ({n / total * 100:.1f}%)"


def run_scenario(
    db,
    *,
    start: str,
    end: str,
    scenario: Dict[str, Any],
) -> Dict[str, Any]:
    print(f"\n>>> 运行 {scenario['id']} — {scenario['label']} ...", flush=True)
    result = run_urt_backtest(
        db,
        start_date=start,
        end_date=end,
        target_pct=0.10,
        horizon_days=10,
        min_score=scenario.get("min_score"),
        use_trace=True,
        stock_pool=None,
        exit_mode="structure_exit",
        config_overrides=scenario.get("config_overrides"),
    )
    sm = result.get("summary") or {}
    cmpd = sm.get("hit_rate_compare") or {}
    row = {
        "id": scenario["id"],
        "label": scenario["label"],
        "signals": sm.get("total_signals"),
        "hit_rate": sm.get("hit_rate"),
        "win_rate": sm.get("win_rate"),
        "avg_pnl_pct": sm.get("avg_pnl_pct"),
        "avg_max_gain_pct": sm.get("avg_max_gain_pct"),
        "avg_bars_held": sm.get("avg_bars_held"),
        "trail_exits": _exit_share(sm, "fallback_trail"),
        "structure_stop": _exit_share(sm, "structure_stop"),
        "horizon_end": _exit_share(sm, "horizon_end"),
        "max_gain_gap": cmpd.get("max_gain_vs_actual_pnl_gap"),
        "horizon_gap": cmpd.get("horizon_vs_actual_pnl_gap"),
    }
    print(
        f"    信号 {row['signals']} · 命中率 {_pct(row['hit_rate'])} · "
        f"胜率 {_pct(row['win_rate'])} · 均盈亏 {_num(row['avg_pnl_pct'])}%",
        flush=True,
    )
    return row


def print_table(rows: List[Dict[str, Any]]) -> None:
    headers = [
        ("label", "方案", 22),
        ("signals", "信号", 6),
        ("hit_rate", "命中率", 8),
        ("win_rate", "胜率", 8),
        ("avg_pnl_pct", "均盈亏%", 8),
        ("avg_max_gain_pct", "均最大涨幅%", 10),
        ("avg_bars_held", "均持有", 6),
        ("max_gain_gap", "回吐缺口", 8),
        ("trail_exits", "移动止盈", 14),
    ]
    print("\n" + "=" * 110)
    print("URT 结构出场 A/B 汇总")
    print("=" * 110)
    hdr = "".join(f"{title:<{width}}" for _, title, width in headers)
    print(hdr)
    print("-" * 110)
    for r in rows:
        line = ""
        for key, _, width in headers:
            val = r.get(key)
            if key in ("hit_rate", "win_rate"):
                text = _pct(val)
            elif key in ("avg_pnl_pct", "avg_max_gain_pct", "avg_bars_held", "max_gain_gap"):
                text = _num(val)
            else:
                text = str(val if val is not None else "-")
            line += f"{text:<{width}}"
        print(line)
    print("=" * 110)


def pick_best(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ok = [r for r in rows if r.get("avg_pnl_pct") is not None and r.get("signals")]
    if not ok:
        return None
    return max(ok, key=lambda r: float(r.get("avg_pnl_pct") or 0))


def main() -> int:
    parser = argparse.ArgumentParser(description="URT 结构出场 A/B 回测")
    parser.add_argument("--start", default=START_DEFAULT)
    parser.add_argument("--end", default=END_DEFAULT)
    parser.add_argument("--out", default="", help="可选：JSON 结果输出路径")
    args = parser.parse_args()

    print(f"区间: {args.start} ~ {args.end} · 全市场 · 结构出场 · use_trace=True")
    db = SessionLocal()
    rows: List[Dict[str, Any]] = []
    try:
        for sc in SCENARIOS:
            rows.append(run_scenario(db, start=args.start, end=args.end, scenario=sc))
    finally:
        db.close()

    print_table(rows)
    best = pick_best(rows)
    if best:
        print(f"\n均盈亏最优: {best['label']} ({best['id']}) → {_num(best['avg_pnl_pct'])}%")
    baseline = next((r for r in rows if r["id"] == "A0_baseline"), None)
    if baseline and best and best["id"] != "A0_baseline":
        try:
            delta = float(best["avg_pnl_pct"]) - float(baseline["avg_pnl_pct"])
            print(f"相对基线提升: {delta:+.2f} pp")
        except (TypeError, ValueError):
            pass

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
