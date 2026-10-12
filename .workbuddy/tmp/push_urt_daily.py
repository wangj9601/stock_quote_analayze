# -*- coding: utf-8 -*-
"""
自动化任务：推送每日 URT 策略信号列表
- 复用项目既有 PushService（生成 URT 自选股日报 → 按 user_push_configs 渠道推送）
- 目标：所有 enabled 且 report_type='urt_daily' 的推送配置
不修改任何项目代码，仅调用既有服务层。
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

import backend_api.config  # noqa: F401  —— 触发 .env 加载
from backend_api.database import SessionLocal
from backend_api.push_routes import get_push_service
from backend_api.services.config_service import ConfigService
from backend_api.models import User

OUT = {"run_at": datetime.now().isoformat(timespec="seconds"), "targets": [], "errors": []}

db = SessionLocal()
try:
    cs = ConfigService(db)
    # 收集所有 enabled 的 urt_daily 配置
    from backend_api.models import UserPushConfig

    cfgs = (
        db.query(UserPushConfig)
        .filter(UserPushConfig.report_type == "urt_daily")
        .order_by(UserPushConfig.id)
        .all()
    )
    OUT["configs_found"] = [
        {
            "id": int(c.id),
            "user_id": int(c.user_id),
            "enabled": bool(c.enabled),
            "channels": list(c.channels or []),
            "push_times": list(c.push_times or []),
            "wechat_notify_userids": c.wechat_notify_userids,
            "wechat_app_profile": c.wechat_app_profile,
        }
        for c in cfgs
    ]

    targets = [c for c in cfgs if bool(c.enabled)]
    push_service = get_push_service(db)

    for c in targets:
        cid = int(c.id)
        uid = int(c.user_id)
        user = db.query(User).filter(User.id == uid).first()
        push_time = f"M{datetime.now().strftime('%H:%M:%S')}"
        rec = {
            "config_id": cid,
            "user_id": uid,
            "username": getattr(user, "username", None),
            "wechat_userid": getattr(user, "wechat_userid", None),
            "push_time": push_time,
        }
        try:
            res = push_service.push_to_user(
                user_id=uid, push_time=push_time, config_id=cid, force=True
            )
            rec["success"] = bool(res.success)
            rec["record_id"] = res.record_id
            rec["error_message"] = res.error_message
            rec["channels"] = [
                {"channel": cr.channel, "success": bool(cr.success), "error": cr.error_message}
                for cr in (res.channel_results or [])
            ]
        except Exception as e:  # noqa: BLE001
            logging.exception("推送配置 %s 失败", cid)
            rec["success"] = False
            rec["error_message"] = f"{type(e).__name__}: {e}"
        OUT["targets"].append(rec)
finally:
    try:
        db.close()
    except Exception:
        pass

# 回读 push_records 拿到报告文件路径
try:
    from backend_api.database import SessionLocal as _SL
    from backend_api.models import PushRecord

    db2 = _SL()
    for rec in OUT["targets"]:
        rid = rec.get("record_id")
        if not rid:
            continue
        pr = db2.query(PushRecord).filter(PushRecord.id == rid).first()
        if pr:
            rec["report_file_path"] = pr.report_file_path
            rec["record_status"] = pr.status
            rec["channel_status"] = pr.channel_status
    db2.close()
except Exception as e:  # noqa: BLE001
    OUT["errors"].append(f"回读 push_records 失败: {e}")

out_path = os.path.join(ROOT, ".workbuddy", "tmp", "push_urt_daily_result.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=2, default=str)

print("===RESULT_JSON===")
print(json.dumps(OUT, ensure_ascii=False, indent=2, default=str))
