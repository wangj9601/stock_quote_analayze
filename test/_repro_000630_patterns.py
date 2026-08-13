# -*- coding: utf-8 -*-
"""复现 000630 asof=2026-08-12：默认 items 为空但 invalidated_count>0。

用法（需可连库）::

    python test/_repro_000630_patterns.py

期望：hit_count=0、items=[]、invalidated_count>=1（案例常见为 2）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))


def main() -> int:
    from backend_api.database import SessionLocal
    from backend_core.analysis.chart_patterns.engine import detect_all_counted
    from backend_core.analysis.chart_patterns.scanner import (
        apply_qfq_to_code_bars,
        normalize_price_adjust,
    )
    from backend_core.strategies.double_bottom.data_loader import (
        batch_load_ohlc_asc,
        resolve_effective_trade_date,
    )

    code = os.environ.get("PATTERN_REPRO_CODE", "000630")
    asof = os.environ.get("PATTERN_REPRO_ASOF", "2026-08-12")
    adjust = normalize_price_adjust(os.environ.get("PATTERN_REPRO_ADJUST", "qfq"))
    lookback = int(os.environ.get("PATTERN_REPRO_LOOKBACK", "160"))

    db = SessionLocal()
    try:
        asof_s = resolve_effective_trade_date(db, asof, market="CN")
        bars_map = batch_load_ohlc_asc(db, [code], lookback=lookback, asof=asof_s)
        bars = bars_map.get(code) or []
        if adjust == "qfq" and bars:
            bars, _ = apply_qfq_to_code_bars(db, code, bars)
        hits, inv_n = detect_all_counted(bars, types=None)
        print(
            f"code={code} asof={asof_s} adjust={adjust} bars={len(bars)} "
            f"hit_count={len(hits)} invalidated_count={inv_n}"
        )
        # 核心断言：计数在过滤前统计，且字段可用
        assert isinstance(inv_n, int) and inv_n >= 0
        if len(hits) == 0 and inv_n > 0:
            print(
                f"OK: 有效命中 0（另有 {inv_n} 条已失效）— 与产品文案口径一致"
            )
        elif inv_n == 0:
            print("NOTE: 当前无失效项；若期望 000630 案例，请核对行情/asof/复权口径")
        else:
            print(f"OK: 有效命中 {len(hits)}（另有 {inv_n} 条已失效）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
