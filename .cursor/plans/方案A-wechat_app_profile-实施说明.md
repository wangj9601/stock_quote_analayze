# 方案 A：wechat_app_profile + 多套环境变量（实施说明）

> 因会话处于 **Plan 模式**，无法自动改 `.py` / `.vue` 等文件。请在 Cursor 中 **关闭 Plan 模式** 或 **允许切换到 Agent**，然后说「按该文档实现」，即可由助手一键应用。  
> 或按下列文件与片段自行粘贴修改。

## 环境变量约定

- **默认主体**（与现网一致，可不配 profile）：
  - `WECHAT_CORP_ID`、`WECHAT_CORP_SECRET`、`WECHAT_AGENT_ID`
- **命名 profile**（仅大写字母、数字、下划线，最长 32；库中存 `B` 则读）：
  - `WECHAT_B_CORP_ID`、`WECHAT_B_CORP_SECRET`、`WECHAT_B_AGENT_ID`
- `user_push_configs.wechat_app_profile` 为空或 `NULL` → 使用默认三套变量。

## 1. 数据库迁移

新建 [`migrations/add_user_push_configs_wechat_app_profile.py`](migrations/add_user_push_configs_wechat_app_profile.py)：

```python
"""迁移：user_push_configs.wechat_app_profile"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from backend_core.database.db import engine
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE user_push_configs
            ADD COLUMN IF NOT EXISTS wechat_app_profile VARCHAR(32)
        """))
        conn.commit()
    logger.info("user_push_configs.wechat_app_profile 迁移完成")

def downgrade():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE user_push_configs DROP COLUMN IF EXISTS wechat_app_profile"))
        conn.commit()

if __name__ == "__main__":
    upgrade()
```

生产执行：`python migrations/add_user_push_configs_wechat_app_profile.py`（与现有迁移用法一致）。

## 2. ORM

在 [`backend_api/models.py`](backend_api/models.py) 的 `UserPushConfig` 中 `wechat_notify_userids` 后增加：

```python
# 可选：企业微信应用配置档（非空则读 WECHAT_<PROFILE>_*；空则读 WECHAT_CORP_ID 等）
wechat_app_profile = Column(String(32), nullable=True)
```

## 3. WeChatConfig / WeChatService

### `backend_core/wechat/wechat_config.py`

- 增加 `normalize_wechat_app_profile(raw) -> Optional[str]`：strip 后只保留 `[A-Za-z0-9_]`，转大写，最长 32；空则 `None`。
- `WeChatConfig.__init__(self, app_profile: Optional[str] = None)`：
  - `p = normalize_wechat_app_profile(app_profile)` 为 `None` 时读 `WECHAT_CORP_ID` / `WECHAT_CORP_SECRET` / `WECHAT_AGENT_ID`；
  - 否则读 `WECHAT_{p}_CORP_ID`、`WECHAT_{p}_CORP_SECRET`、`WECHAT_{p}_AGENT_ID`。
- 增加 `is_configured(self) -> bool`：三者均非空。

### `backend_core/wechat/wechat_service.py`

- `def __init__(self, app_profile: Optional[str] = None)`：`self.config = WeChatConfig(app_profile)`（`WeChatConfig()` 等价于 `app_profile=None`）。

## 4. PushService

在 [`backend_api/services/push_service.py`](backend_api/services/push_service.py)：

- 模块级 `_wechat_service_lock` + `_wechat_service_by_key: Dict[str, WeChatService]`，key 为 `""`（默认）或规范化后的 profile。
- 方法 `_get_wechat_service_for_push_config(self, config) -> WeChatService`：从 `getattr(config, "wechat_app_profile", None)` 规范化后取缓存实例。
- `_send_via_wechat(..., push_config=None)`：若 `push_config` 非空则用 `_get_wechat_service_for_push_config(push_config)` 发消息；否则用 `self.wechat_service`（兼容旧调用）。
- 发前若 `push_config` 含 `wechat` 渠道且 `wechat_targets` 非空：检查 `wx.config.is_configured()`，否则返回明确 `ChannelResult` 错误（避免静默失败）。
- `push_to_user` 里调用 `_send_via_wechat` 时传入 `config`；重试路径里传入 `config_retry`。

## 5. ConfigService / push_routes

- [`backend_api/services/config_service.py`](backend_api/services/config_service.py)：`ConfigUpdate` 增加 `wechat_app_profile: Optional[str] = None`；`update_user_config`、`update_config_by_id`、`create_config` 及 upsert 分支读写该字段；`None` 表示不更新；传 `""` 可清空为 `NULL`（与 `wechat_notify_userids` 类似处理）。
- [`backend_api/push_routes.py`](backend_api/push_routes.py)：`UserPushConfigResponse`、`ConfigUpdateRequest`、`ConfigCreateRequest` 增加 `wechat_app_profile: Optional[str] = None`；`update_push_config` 组装 `ConfigUpdate` 时传入；`admin_create_push_config` 调用 `create_config(..., wechat_app_profile=body.wechat_app_profile)`（需在 `create_config` 签名中增加该参数）。

## 6. 管理端

- [`admin/src/services/push.service.ts`](admin/src/services/push.service.ts)：`UserPushConfigResponse`、`ConfigUpdateRequest`、`createPushConfig` body 增加可选 `wechat_app_profile?: string | null`。
- [`admin/src/views/PushConfigView.vue`](admin/src/views/PushConfigView.vue)：
  - 表格列展示 `wechat_app_profile` 或「默认」；
  - 添加/编辑表单增加 `el-input`（placeholder 说明示例 `B` 对应 `WECHAT_B_*`）；
  - `addForm` / `editForm` / `submitAddTask` / `submitEdit` 携带该字段；清空时传 `''` 以清除 profile。

## 7. 文档与示例

- [`.env.example`](.env.example) 增加注释块说明 `WECHAT_<PROFILE>_CORP_ID` 等。
- [`docs/prod/triple_volume_observe_ops.md`](docs/prod/triple_volume_observe_ops.md)「推送」小节补充：扫描/复核两条任务可设不同 `wechat_app_profile` + 各自 `wechat_notify_userids`（userid 须属于对应企业应用可见范围）。

## 8. 测试（建议放在 `test/`）

- `normalize_wechat_app_profile` 用例；
- `WeChatConfig` 在 `monkeypatch.setenv` 下对 `B` profile 读取正确变量名。

---

完成以上修改后，在服务器为第二主体配置 `WECHAT_B_CORP_ID` 等，管理端将对应任务的「企微应用 profile」填 `B` 即可。
