# migrations/ —— 历史迁移脚本（已冻结）

> **自 2026-10-07 起，本目录冻结。新的 schema 变更请写进 [`alembic/versions/`](../alembic/versions/)。**

## 现状

本目录是项目早期（引入 Alembic 之前）的迁移方式：**84 个独立的手写 Python 脚本**，
每个脚本自己连库、自己判断、自己 commit。典型形状见 `add_stock_adj_factor.py`：

```python
from backend_core.database.db import engine     # 或 backend_api.database.SessionLocal
with engine.begin() as conn:
    conn.execute(text("CREATE TABLE IF NOT EXISTS ..."))
```

运行方式有两种，都靠"人工判断该跑哪个"：

```bash
python migrations/<某个脚本>.py
python scripts/run_recent_migrations.py --days 2   # 按文件修改时间批量跑
python init_db.py                                  # create_all + 目录下全部脚本
```

## 为什么冻结

这种方式有三个结构性缺陷，正是引入 Alembic 的原因：

| 缺陷 | 具体表现 |
|---|---|
| **无版本账本** | 库里不记录"已经跑过哪些"。是否跑过、跑到哪一步，全靠翻文件时间和人的记忆。 |
| **按 mtime 排序执行** | `run_recent_migrations.py` 用**文件修改时间**排序。`git clone` / 归档解压会重写 mtime，导致执行顺序错乱或漏跑。 |
| **无回滚能力** | 只有 `upgrade` 语义，写错了只能手工反向写 SQL。`init_db.py --rollback` 至今是 `未实现`。 |

## 与 Alembic 的关系

- **不迁移、不改写**：这 84 个脚本保持原样，作为历史存档（也是"库里那 40+ 张
  无 ORM 声明的表"的唯一书面来源）。
- **不重复执行**：`0001_baseline` 基线已代表"这些脚本全部跑完后的状态"。
  既有库执行 `alembic stamp 0001_baseline` 即纳管，**不会重跑本目录任何脚本**。
- **仍可用但会告警**：`run_recent_migrations.py` 已加弃用提示，仅供补历史库时应急。

## 需要新加一个变更时

```bash
# 1) 生成迁移
.venv/Scripts/python.exe scripts/db_migrate.py revision -m "add xxx column to yyy"

# 2) 编辑 alembic/versions/ 下新文件，写 op.add_column / op.create_table ...

# 3) 先看漂移、再执行
.venv/Scripts/python.exe scripts/db_migrate.py check
.venv/Scripts/python.exe scripts/db_migrate.py upgrade
```

完整说明见 [`docs/database/Alembic_guide.md`](../docs/database/Alembic_guide.md)。
