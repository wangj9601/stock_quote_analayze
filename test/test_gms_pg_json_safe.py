"""GMS / PG JSON：NaN 清洗，避免 gms_signal_trace 写入失败。"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.gms.json_safe import finite_or_none, sanitize_for_pg_json


def test_sanitize_nan_and_inf_to_none():
    payload = {
        "ma60_d": float("nan"),
        "ma60_d_lag": float("inf"),
        "ok": 1.25,
        "nested": {"x": float("-inf"), "y": None},
        "arr": [0.1, float("nan"), "txt"],
    }
    out = sanitize_for_pg_json(payload)
    assert out["ma60_d"] is None
    assert out["ma60_d_lag"] is None
    assert out["ok"] == 1.25
    assert out["nested"]["x"] is None
    assert out["nested"]["y"] is None
    assert out["arr"] == [0.1, None, "txt"]
    # 产出必须可被标准 JSON（禁用 nan）序列化
    import json

    s = json.dumps(out, allow_nan=False)
    assert "NaN" not in s
    assert "Infinity" not in s


def test_finite_or_none():
    assert finite_or_none(float("nan")) is None
    assert finite_or_none(3.14) == 3.14
    assert finite_or_none("x") == "x"


def test_numpy_scalar_nan():
    try:
        import numpy as np
    except ImportError:
        return
    out = sanitize_for_pg_json({"ma60_d": np.float64("nan"), "v": np.int64(3)})
    assert out["ma60_d"] is None
    assert out["v"] == 3
    assert not math.isnan(out["v"] if isinstance(out["v"], float) else 0)


if __name__ == "__main__":
    test_sanitize_nan_and_inf_to_none()
    test_finite_or_none()
    test_numpy_scalar_nan()
    print("ok")
