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
既有库的 schema 状态"。

**两种库都由 `init_db.py` 统一引导，不需要手工敲 `stamp`：**

| 库的现状 | `python init_db.py` 做什么 |
|---|---|
| 既有库（schema 已就绪） | 只 `stamp 0001_baseline` 写账本，**不执行任何 DDL** |
| 全新空库 | `create_all` → 历史 `migrations/*.py` → `stamp 0001_baseline` → `upgrade head` |
| 已纳管库 | `upgrade head`（只补未执行的 revision） |

即：`init_db.py` 把原来「手工两步（建表 + stamp）」合并为一条幂等命令。

## 常用命令

```bash
# 引导 / 迁移（按库的现状自动决策，推荐）
python init_db.py

# 查看数据库与账本状态（含脱敏后的连接串）
python init_db.py --status

# 查看当前版本
.venv/Scripts/alembic.exe current

# 升到最新
.venv/Scripts/alembic.exe upgrade head

# 生成新迁移（自动比对 ORM metadata 与库结构）
.venv/Scripts/alembic.exe revision --autogenerate -m "add xxx column"

# 回退一步
python init_db.py --rollback
```

也可用封装脚本（自带漂移预览、口令脱敏等）：

```bash
.venv/Scripts/python.exe scripts/db_migrate.py status
.venv/Scripts/python.exe scripts/db_migrate.py check
```

详细说明见 `docs/database/Alembic_guide.md`。

---

## 生产环境如何执行迁移

> 本文件会随发布包一起发到服务器（`alembic/` 不在打包排除清单里），
> 而 `docs/` 被排除 —— 所以服务器上能看到的操作说明就是这一节。

### 为什么必须手工执行

生产发布流程**不会自动跑迁移**，有两个原因：

1. `scripts/deploy/release.ps1` 里的迁移步骤是
   `if (Test-Path 'migrate_db.py') { python migrate_db.py }`，
   而**仓库里没有 `migrate_db.py`**，这段永远不执行。
2. 生产启动器 `start_backend_api.py` 只负责拉起 `uvicorn`，
   **完全不碰数据库**。

（注意区别：另一个启动器 `backend_api/start.py` 会在启动时调用
`init_db.py` → 自动 `upgrade head`。生产用的是前者，不要依赖后者。）

### 一次性前提

```bash
# ① 服务器安装 alembic —— 它不在生产依赖里，必须单独装
pip install alembic==1.13.1

# ② 确认 .env 指向生产库（最容易出错的地方）
python scripts/db_migrate.py status
#    → 打印的连接串应形如 postgres:***@<生产库主机>:5446/stock_analysis
```

`alembic` 为什么不在 `requirements-prod.txt`：该文件经
`scripts/deploy/Assert-RequirementsProdMinimal.ps1` 校验，**只允许两条
`-r .../requirements-minimal.txt`**，禁止任何直接依赖行。而两个 minimal 文件
也刻意不含 alembic（应用运行时不 import 它）。所以要自动安装，只能把它加进
`backend_api/requirements-minimal.txt` —— 当前设计有意不这么做。

### 每次新增迁移后的执行顺序

**开发机**（写变更、验证、入库）：

```bash
python scripts/db_migrate.py revision -m "add xxx table"
#   → 编辑 alembic/versions/<rev>_*.py，手写 op.create_table / op.add_column
python scripts/db_migrate.py upgrade      # 本地实际执行一遍
python scripts/db_migrate.py downgrade    # 验证能回滚
git add alembic/versions/                 # ★ revision 文件必须入库
git commit -m "..."
```

**服务器**（在部署根目录执行，即 `current/`）：

```bash
# 0) 先备份 —— 迁移不可逆时的唯一退路
pg_dump -h <host> -p 5446 -U postgres -d stock_analysis -F c \
        -f stock_analysis_$(date +%Y%m%d_%H%M%S).dump

# 1) 看当前版本与连接目标，确认没连错库
python scripts/db_migrate.py status

# 2) 预演（可选，不连库、不执行，输出 SQL 供审阅）
python scripts/db_migrate.py sql

# 3) 执行到最新
python scripts/db_migrate.py upgrade

# 4) 校验
python init_db.py --verify
```

如果第 3 步之前服务已在运行，**先停服务再迁库**，迁完再起：
`start_production_services.bat`（或对应的 NSSM 服务重启）。

### 回滚

```bash
python scripts/db_migrate.py downgrade        # 撤销一步
python scripts/db_migrate.py downgrade 0001_baseline   # 回到基线
```

`upgrade` 在**单个事务**内执行（PostgreSQL 的 DDL 可回滚），任一步失败整体
回退，不会留下半迁移状态。

### 四条硬约束

| 约束 | 说明 |
|---|---|
| `ALEMBIC_ALLOW_DROP` 保持默认 `0` | 默认守卫「只增不减」。本项目库里有 44 张表没有 ORM 声明，放开守卫会导致 autogenerate 生成删表语句 |
| **不要**用 `upgrade` 代替 `stamp` | 迁机/恢复全量 dump 后 schema 已就绪，跑 `upgrade` 会因重复建表报错。此时只需 `python init_db.py`（等价 `--stamp`，只写账本） |
| `versions/` 下的 revision 必须入 git | 它是版本账本的一部分，且必须随发布包发到服务器；`.gitignore` 已确认未忽略 |
| 生产机上没有 `docs/` | 打包排除清单含 `docs`，需要查阅完整指南请看仓库 |
