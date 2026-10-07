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
python init_db.py                                  # 空库引导：create_all + 本目录全部脚本
```

> `python init_db.py` 仍会跑本目录下全部脚本，但**仅在"空库引导"这一条路径上**，
> 跑完立刻 `stamp 0001_baseline` 把库纳入 Alembic 管理；之后它只会走
> `alembic upgrade head`，不会再碰本目录（详见文末「与 Alembic 的关系」）。

## 为什么冻结

这种方式有三个结构性缺陷，正是引入 Alembic 的原因：

| 缺陷 | 具体表现 |
|---|---|
| **无版本账本** | 库里不记录"已经跑过哪些"。是否跑过、跑到哪一步，全靠翻文件时间和人的记忆。 |
| **按 mtime 排序执行** | `run_recent_migrations.py` 用**文件修改时间**排序。`git clone` / 归档解压会重写 mtime，导致执行顺序错乱或漏跑。 |
| **无回滚能力** | 只有 `upgrade` 语义，写错了只能手工反向写 SQL。`init_db.py --rollback` 此前是 `未实现`（现已由 Alembic 的 `downgrade` 接管）。 |

## 与 Alembic 的关系

- **不迁移、不改写**：这 84 个脚本保持原样，作为历史存档（也是"库里那 40+ 张
  无 ORM 声明的表"的唯一书面来源）。
- **不重复执行**：`0001_baseline` 基线已代表"这些脚本全部跑完后的状态"。
  既有库执行 `alembic stamp 0001_baseline` 即纳管，**不会重跑本目录任何脚本**。
- **仍可用但会告警**：`run_recent_migrations.py` 已加弃用提示，仅供补历史库时应急。

## 在 `init_db.py` 里怎么被执行（2026-10-07 修复）

`init_db.py` 只在**空库引导**时执行本目录，方式是 `exec(code, globals)`。
原实现注入的全局变量不完整，导致这段路径**从未真正跑通过**：

| 缺失的注入名 | 后果 |
|---|---|
| `__file__` | 82 个脚本靠 `dirname(dirname(abspath(__file__)))` 定位项目根 → `NameError` |
| `__name__` | **84 个脚本全部**是 `if __name__ == "__main__": main()`；不设成 `"__main__"` 就静默空转，完全不设则 `NameError` |

两者都已补上。补上后实测 **64/84 成功**，空库引导可建出 **144** 张表
（`create_all` 贡献 125 张）。剩余 20 个失败属历史遗留，原因见
[`docs/database/Alembic_guide.md`](../docs/database/Alembic_guide.md) §4.1，**不建议修**——
这些脚本即将被对应的 Alembic revision 取代。

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
