# -*- coding: utf-8 -*-
"""自动化任务：补采 2026-10-30（周五）historical_quotes + MA/MAVOL 指标。"""
import os
import sys
import json
import logging
from datetime import datetime

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

log_path = os.path.join(ROOT, ".workbuddy", "tmp", "backfill_1030.log")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)])

out = {"quotes": None, "indicators": None}

# 1) 补采 historical_quotes（YYYYMMDD）
from backend_core.data_collectors.main import tushare_hist_collector

t0 = datetime.now()
try:
    ok = tushare_hist_collector.collect_historical_quotes("20261030")
    out["quotes"] = {"success": bool(ok), "elapsed_s": round((datetime.now() - t0).total_seconds(), 1)}
    logging.info("补采行情 20261030 -> %s", out["quotes"])
except Exception as e:  # noqa: BLE001
    out["quotes"] = {"success": False, "error": f"{type(e).__name__}: {e}"}
    logging.exception("补采行情失败")

# 2) 补算 MA+MAVOL（YYYY-MM-DD）
if out["quotes"] and out["quotes"].get("success"):
    from backend_core.database.db import SessionLocal
    from backend_core.data_collectors.batch_ma_mavol import calculate_and_save_ma_mavol_for_date

    t1 = datetime.now()
    session = SessionLocal()
    try:
        result = calculate_and_save_ma_mavol_for_date(session, "2026-10-30")
        session.commit()
        out["indicators"] = {"success": True, "result": str(result), "elapsed_s": round((datetime.now() - t1).total_seconds(), 1)}
        logging.info("MA+MAVOL 2026-10-30 完成: %s", out["indicators"])
    except Exception as e:  # noqa: BLE001
        out["indicators"] = {"success": False, "error": f"{type(e).__name__}: {e}"}
        logging.exception("MA+MAVOL 失败")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()

print("===BACKFILL_1030_JSON===")
print(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), **out}, ensure_ascii=False, indent=2))
