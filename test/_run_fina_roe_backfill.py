# -*- coding: utf-8 -*-
"""全市场 AkShare fina（含 ROE）回填入口。"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from backend_core.data_collectors.akshare.fina_indicator import (  # noqa: E402
    run_akshare_fina_indicator_collect,
)


def main() -> int:
    result = run_akshare_fina_indicator_collect()
    print("FINA_BACKFILL_RESULT:", result, flush=True)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
