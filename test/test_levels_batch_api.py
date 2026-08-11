"""批量 KDE 支撑/阻力接口（URT/RPE 选股「按前复权计算」）。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api"))

from stock.stock_analysis_routes import (  # noqa: E402
    LevelsBatchRequest,
    _normalize_batch_codes,
    get_key_levels_batch,
)


def test_normalize_batch_codes_dedupe_and_pad():
    # 与 levels 单股路由一致：≤5 位按港股补齐 5 位；6 位 A 股保持
    assert _normalize_batch_codes(["2837", "002837", "002837", "", " 600519 "]) == [
        "02837",
        "002837",
        "600519",
    ]


def test_levels_batch_aggregates_success_and_fail():
    import asyncio
    import json

    db = MagicMock()

    def fake_compute(code, max_levels, *, db, adjust, refresh_factor, factor_source):
        if code == "99999":
            return 400, {"success": False, "message": "获取港股复权因子失败"}
        return 200, {
            "success": True,
            "data": {
                "nearest_support": 10.5,
                "nearest_resistance": 20.5,
                "support_levels": [10.5],
                "resistance_levels": [20.5],
                "current_price": 15.0,
                "price_adjust": "qfq",
            },
        }

    body = LevelsBatchRequest(codes=["600519", "00700", "99999"], adjust="qfq")
    with patch("stock.stock_analysis_routes._compute_levels_payload", side_effect=fake_compute):
        resp = asyncio.run(get_key_levels_batch(body, db))

    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["success"] is True
    assert data["total"] == 3
    assert data["ok_count"] == 2
    assert data["fail_count"] == 1
    by_code = {it["code"]: it for it in data["items"]}
    assert by_code["600519"]["success"] is True
    assert by_code["00700"]["success"] is True
    assert by_code["99999"]["success"] is False
