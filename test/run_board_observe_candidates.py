# -*- coding: utf-8 -*-
"""跑一日行业观察池自动候选（可选采纳 dry-run 只打印）。

用法:
    python test/run_board_observe_candidates.py
    python test/run_board_observe_candidates.py --trade-date 2026-11-04
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trade-date", default=None)
    args = p.parse_args()
    from backend_core.board_observe.compute_daily import run_board_observe_candidates_daily

    result = run_board_observe_candidates_daily(trade_date=args.trade_date)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
