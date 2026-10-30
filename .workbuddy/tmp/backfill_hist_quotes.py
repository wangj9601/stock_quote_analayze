# -*- coding: utf-8 -*-
"""自动化任务：补采 historical_quotes 缺失交易日（tushare 全市场日线，按日幂等补写）。"""
import os
import sys
import json
import logging
from datetime import datetime

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)

from backend_core.data_collectors.main import tushare_hist_collector

MISSING = ["20261023", "20261026", "20261027"]  # 缺失的已完成交易日（10-28 当日盘中不采）
results = {}
for d in MISSING:
    t0 = datetime.now()
    try:
        ok = tushare_hist_collector.collect_historical_quotes(d)
        results[d] = {"success": bool(ok), "elapsed_s": round((datetime.now() - t0).total_seconds(), 1)}
    except Exception as e:  # noqa: BLE001
        results[d] = {"success": False, "error": f"{type(e).__name__}: {e}"}
    logging.info("补采 %s -> %s", d, results[d])

print("===BACKFILL_JSON===")
print(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), "results": results}, ensure_ascii=False, indent=2))
