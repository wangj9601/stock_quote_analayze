# -*- coding: utf-8 -*-
"""002412 杯底重锚回归（需本地 PostgreSQL）。"""

import pytest

from backend_core.strategies.cup_bottom.config import merge_pattern_cfg, get_default_cupb_config
from backend_core.strategies.cup_bottom.detector import detect_cup_bottom
from backend_core.strategies.double_bottom.data_loader import batch_load_ohlc_asc, resolve_effective_trade_date


@pytest.mark.integration
def test_002412_cup_bottom_reanchored_to_june():
    from backend_api.database import SessionLocal

    db = SessionLocal()
    try:
        asof = resolve_effective_trade_date(db, "2026-08-25")
        bars = batch_load_ohlc_asc(db, ["002412"], lookback=180, asof=asof).get("002412") or []
        cfg = merge_pattern_cfg(get_default_cupb_config())
        hit = detect_cup_bottom(bars, pattern_cfg=cfg)
        assert hit is not None, "应识别到杯底形态"
        assert hit.get("cup_bottom_date") >= "2026-06-20", (
            f"杯底应重锚至6月低点，实际 {hit.get('cup_bottom_date')}"
        )
        assert float(hit.get("cup_bottom_price") or 0) <= 5.5
        assert hit.get("status") in ("forming", "confirmed")
    finally:
        db.close()
