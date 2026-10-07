# Alembic 迁移目录

本目录是**唯一**的 schema 变更入口（自引入 Alembic 起）。

```
alembic/
├── env.py              # 运行环境：连接串来源 + metadata 合并 + 防误删守卫
├── script.py.mako      # 新迁移脚本模板
├── versions/           # 迁移脚本（每个文件一个 revision）
└── README.md           # 本文件
```

## 与历史 `migrations/` 的边界

| 目录 | 状态 | 说明 |
|---|---|---|
| `migrations/*.py` | **冻结** | 84 个历史手写脚本，保留备查，不再新增，也不再由 Alembic 执行 |
| `alembic/versions/` | **唯一入口** | 所有新 schema 变更写在这里 |

`0001_baseline` 是基线 revision：它 **不执行任何 DDL**，只代表"引入 Alembic 那一刻
既有库的 schema 状态"。既有库通过 `alembic stamp 0001_baseline` 打标即可，
不会重新建表；全新库先跑 `init_db.py`（`create_all` + 旧脚本）再 stamp。

## 常用命令

```bash
# 查看当前版本
.venv/Scripts/alembic.exe current

# 升到最新
.venv/Scripts/alembic.exe upgrade head

# 生成新迁移（自动比对 ORM metadata 与库结构）
.venv/Scripts/alembic.exe revision --autogenerate -m "add xxx column"

# 回退一步
.venv/Scripts/alembic.exe downgrade -1
```

也可用封装脚本（自带漂移预览、口令脱敏等）：

```bash
.venv/Scripts/python.exe scripts/db_migrate.py status
.venv/Scripts/python.exe scripts/db_migrate.py check
```

详细说明见 `docs/database/Alembic迁移指南.md`。
