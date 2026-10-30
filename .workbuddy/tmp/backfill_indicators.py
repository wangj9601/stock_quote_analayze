# -*- coding: utf-8 -*-
"""补算 10-26 / 10-27 全市场 MA+MAVOL 指标（10-23 已完成）。日志写文件，便于排查。"""
import os
import sys
import logging
from datetime import datetime

ROOT = r"E:\wangxw\股票分析软件\编码\stock_quote_analayze"
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

log_path = os.path.join(ROOT, ".workbuddy", "tmp", "backfill_indicators.log")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)])

from backend_core.database.db import SessionLocal
from backend_core.data_collectors.batch_ma_mavol import calculate_and_save_ma_mavol_for_date

for d_dash in ["2026-10-26", "2026-10-27"]:
    t0 = datetime.now()
    session = SessionLocal()
    try:
        result = calculate_and_save_ma_mavol_for_date(session, d_dash)
        session.commit()
        logging.info("MA+MAVOL %s 完成: %s，耗时 %.1fs", d_dash, result, (datetime.now() - t0).total_seconds())
    except Exception as e:  # noqa: BLE001
        logging.exception("MA+MAVOL %s 失败: %s", d_dash, e)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()

logging.info("全部补算结束")
