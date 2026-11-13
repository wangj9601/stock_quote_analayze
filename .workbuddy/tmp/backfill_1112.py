# -*- coding: utf-8 -*-
"""自动化任务：补采 2026-11-12（historical_quotes + MA/MAVOL 指标）。

2026-11-13 12:58 盘中运行，11-12（周四）整日缺失 → 日更采集再次中断，需补采。
"""
import os
import sys
import json
import logging
from datetime import datetime

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

log_path = os.path.join(ROOT, ".workbuddy", "tmp", "backfill_1112.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)

MISSING_YYYYMMDD = ["20261112"]
OUT = {"quotes": {}, "indicators": {}}


def main():
    from backend_core.data_collectors.main import tushare_hist_collector

    for d in MISSING_YYYYMMDD:
        t0 = datetime.now()
        try:
            ok = tushare_hist_collector.collect_historical_quotes(d)
            OUT["quotes"][d] = {"success": bool(ok), "elapsed_s": round((datetime.now() - t0).total_seconds(), 1)}
        except Exception as e:  # noqa: BLE001
            OUT["quotes"][d] = {"success": False, "error": f"{type(e).__name__}: {e}"}
        logging.info("补采行情 %s -> %s", d, OUT["quotes"][d])

    ok_dates = [d for d, r in OUT["quotes"].items() if r.get("success")]
    if ok_dates:
        from backend_core.database.db import SessionLocal
        from backend_core.data_collectors.batch_ma_mavol import calculate_and_save_ma_mavol_for_date

        for d in ok_dates:
            t1 = datetime.now()
            session = SessionLocal()
            try:
                result = calculate_and_save_ma_mavol_for_date(session, f"{d[:4]}-{d[4:6]}-{d[6:]}")
                session.commit()
                OUT["indicators"][d] = {"success": True, "result": str(result), "elapsed_s": round((datetime.now() - t1).total_seconds(), 1)}
            except Exception as e:  # noqa: BLE001
                OUT["indicators"][d] = {"success": False, "error": f"{type(e).__name__}: {e}"}
                try:
                    session.rollback()
                except Exception:
                    pass
            finally:
                session.close()
            logging.info("MA+MAVOL %s -> %s", d, OUT["indicators"][d])


if __name__ == "__main__":
    main()
    print("===BACKFILL_JSON===")
    print(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), **OUT}, ensure_ascii=False, indent=2))
