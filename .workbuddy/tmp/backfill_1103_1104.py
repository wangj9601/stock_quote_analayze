# -*- coding: utf-8 -*-
"""自动化任务：补采 2026-11-03、2026-11-04（historical_quotes + MA/MAVOL 指标）。

踩坑要点（沿用既往经验）：
- 行情补采日期格式 YYYYMMDD；指标补算日期格式 YYYY-MM-DD
- calculate_and_save_ma_mavol_for_date 用 multiprocessing（Windows spawn），
  必须放在 if __name__ == '__main__' 守卫下
- 进程结束后可能挂住（session/线程不释放），由外部 TaskStop 强杀，不影响落库
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

log_path = os.path.join(ROOT, ".workbuddy", "tmp", "backfill_1103_1104.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)

MISSING_YYYYMMDD = ["20261103", "20261104"]  # 缺失的已完成交易日（11-05 当日盘中不采）
OUT = {"quotes": {}, "indicators": {}}


def main():
    # 1) 补采 historical_quotes
    from backend_core.data_collectors.main import tushare_hist_collector

    for d in MISSING_YYYYMMDD:
        t0 = datetime.now()
        try:
            ok = tushare_hist_collector.collect_historical_quotes(d)
            OUT["quotes"][d] = {"success": bool(ok), "elapsed_s": round((datetime.now() - t0).total_seconds(), 1)}
        except Exception as e:  # noqa: BLE001
            OUT["quotes"][d] = {"success": False, "error": f"{type(e).__name__}: {e}"}
        logging.info("补采行情 %s -> %s", d, OUT["quotes"][d])

    # 2) 补算 MA+MAVOL（仅对行情成功的日期）
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
