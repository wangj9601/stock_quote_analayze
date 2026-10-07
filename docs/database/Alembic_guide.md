# Alembic 迁移指南

> 适用范围：`stock_quote_analayze`（冰枫堂「股票分析」平台）全部数据库结构变更。
> 引入日期：2026-10-07 ｜ Alembic 版本：1.13.1 ｜ 数据库：PostgreSQL 17

---

## 1. 一句话上手

```bash
# ① 库的引导/纳管 —— 任意状态的库都跑这一条（含 --status / --dry-run / --stamp / --rollback）
.venv/Scripts/python.exe init_db.py --status     # 先看状态
.venv/Scripts/python.exe init_db.py              # 按现状自动决策并执行

# ② 日常变更
# 看漂移（ORM metadata vs 真实库，只汇总不落文件）
.venv/Scripts/python.exe scripts/db_migrate.py check

# 建一个变更
.venv/Scripts/python.exe scripts/db_migrate.py revision -m "add xxx column to yyy"
#  → 编辑 alembic/versions/ 下新文件，写 op.add_column / op.create_table ...

# 执行 / 回滚
.venv/Scripts/python.exe scripts/db_migrate.py upgrade
.venv/Scripts/python.exe scripts/db_migrate.py downgrade      # 默认撤销一步
```

`init_db.py` 负责**引导库**，`db_migrate.py` 负责**改 schema**，两者都基于同一个
`alembic_version` 账本。`db_migrate.py` 是 `alembic` 命令的封装（口令脱敏 +
漂移汇总 + 交互确认），直接用 `.venv/Scripts/alembic.exe` 也完全可以。

---

## 2. 文件布局与职责

```
alembic.ini                      # 配置。**纯 ASCII**，不写口令
alembic/
├── env.py                       # 运行环境：连接串注入 + metadata 合并 + 防误删守卫
├── script.py.mako               # 新迁移脚本模板（含本项目约定）
├── README.md                    # 目录说明
├── schema_snapshot_0001.json    # 基线时刻结构快照（归档参考，Alembic 不读）
└── versions/
    └── 0001_baseline.py         # 基线 revision（no-op）
init_db.py                       # 库的引导入口（按库现状自动决策，**推荐用这个**）
scripts/db_migrate.py            # 便捷入口（status/check/upgrade/…）
migrations/                      # 历史手写脚本，**已冻结**（见其 README.md）
```

三者分工：

| 入口 | 定位 | 何时用 |
|---|---|---|
| `init_db.py` | **引导 + 纳管**：把任意状态的库带到当前 schema | 新环境搭库、接手一个未纳管的库 |
| `scripts/db_migrate.py` | **日常变更**：写/查/执行单个 revision | 加字段、改表、回滚 |
| `alembic.exe` | 底层命令 | 需要 `--sql`、`-x` 等原生参数时 |

---

## 3. 三个必须知道的坑

这三条是接入时实测出来的，踩了会丢数据或报错，**改 `env.py` 前务必先读**。

### 坑 1 ｜ 两套 ORM Base，且不能直接传 metadata 列表

项目里有两个互不相干的 `declarative_base()`：

| 来源 | 表数 | 说明 |
|---|---|---|
| `backend_api.models.Base` | 125 | 主 ORM，定义在 `backend_api/models.py` |
| `backend_core.database.db.Base` | 9 | 采集流程 / watchlist 等历史 ORM |

注意 `backend_api/models` 其实是个**包**（与 `models.py` 同名），`Base` 由包内
`importlib` 动态载入 `models.py`，`from backend_api.models import Base` 拿到的就是它。

两套 metadata 有 4 张同名表：`watchlist`、`historical_quotes`、
`ma_indicators`、`macd_indicators`。

**Alembic 不允许同名表跨 metadata**：`AutogenContext.table_key_to_table`
（`alembic/autogenerate/api.py`）会直接抛
`ValueError: Duplicate table keys across multiple MetaData objects`。

所以 `env.py` 里用 `MetaData.to_metadata()` 深拷贝合并成**单一** MetaData，
以 `backend_api` 侧定义为准。合并结果：**130 张表**。

### 坑 2 ｜ 库里有一批"没有 ORM 声明"的表 → autogenerate 会想删掉它们

引入 Alembic 时库里 **171 张表**，而 ORM 只声明了 **130 张**，差额 **44 张**
（`historical_quotes`、`market_daily_review`、龙虎榜、财报季频表、`*_collect_operation_logs` …）
是当年 `migrations/*.py` 手写 SQL 建的、从未进 ORM。

若不做处理，`alembic revision --autogenerate` 会生成一堆 `op.drop_table`，
**执行即不可逆丢数据**。

`env.py` 的 `include_object()` 因此默认「**只增不减**」：

```python
def include_object(obj, name, type_, reflected, compare_to):
    if not ALLOW_DROP and reflected and compare_to is None:
        return False    # 跳过「库里有、metadata 没有」的对象（表/列/索引/约束）
    return True
```

实测：`upgrade` 段内 `drop_table` / `drop_column` **均为 0**，守卫有效。

确需删除时显式开启：`ALEMBIC_ALLOW_DROP=1 alembic ... upgrade`。

### 坑 3 ｜ ORM metadata 与真实库存在系统性偏差 → **不要盲信 autogenerate**

`db_migrate.py check` 的实测结果（2026-10-07，171 张表基线）：

| 类型 | 数量 | 解读 |
|---|---|---|
| `create_table` | 3 | ORM 有、库里没有：`one_yang_three_lines_signals`、`system_alert_rules`、`system_performance_reports` |
| `create_index` | 164 | ORM 声明 `index=True`，库里缺对应索引 |
| `alter_column` | 353 | 绝大多数是**伪漂移**（见下） |
| `create_foreign_key` | 14 | ORM 声明 FK，库里没有 |
| `create_unique_constraint` | 6 | 同上 |
| `drop_index` | 2 | **索引重定义**（同名 drop + create，如补 `unique=True`） |
| `drop_table` / `drop_column` | **0** | 结构性删除，守卫已拦截 |

"伪漂移"的来源是**建表方式不一致**：ORM 写 `String()` / `Integer` / `JSON`，
而库里的表是手写 SQL 建的、用的是 `TEXT` / `BIGINT` / `JSONB`。
语义等价或兼容，但 Alembic 的 `compare_type=True` 会逐条报出来。

> **结论：本项目规范做法是「手写 revision」。**
> 把 `--autogenerate` 只当作**线索**（它能帮你确认哪些表/列漏了），
> 生成结果必须逐条人工筛掉伪漂移，**绝不可原样提交**。

---

## 4. 基线（baseline）原理

`0001_baseline` 的 `upgrade()` / `downgrade()` 都是 `pass`。它不建表，只是版本账本的起点。

| 场景 | 操作 |
|---|---|
| **既有库**（已在跑，171 张表） | `python init_db.py` —— 只写账本，不执行任何 DDL |
| **全新空库** | `python init_db.py` —— `create_all` + 历史脚本 + `stamp` 基线 + `upgrade head` |
| **已纳管库** | `python init_db.py` —— `upgrade head`，只补未执行的 revision |
| 之后所有变更 | 从 `0002` 起写进 `alembic/versions/`，`upgrade head` 增量应用 |

`stamp` 与 `upgrade` 的区别：`stamp` **只改 `alembic_version` 表**，
不会碰业务表；`upgrade` 会真的执行 DDL。既有库**千万不要**用 `upgrade` 代替 `stamp`。

### 4.1 库的引导：`init_db.py`

`init_db.py` 是**唯一需要记的入口**——它探测库的现状，自己决定该做什么，
所以三种库都用同一条命令。原来"先建表、再手工 stamp"的两步已合并进它内部。

```bash
python init_db.py            # 自动判断并执行（推荐）
python init_db.py --status   # 只看状态：账本 / 当前 revision / 代码 head / 判定
python init_db.py --dry-run  # 只打印将要执行的动作
python init_db.py --stamp    # 只打标，纳管既有库（不执行 DDL）
python init_db.py --rollback # 回退一步（alembic downgrade -1）
python init_db.py --verify   # 校验 users / user_push_configs / push_records 结构
python init_db.py --yes      # 跳过交互确认（CI / 无人值守）
```

决策逻辑：

```
读 alembic_version 表 + 统计业务表
├─ 账本存在 ─────────────→ alembic upgrade head（幂等，已最新则直接返回）
└─ 账本不存在
   ├─ 无业务表（空库）───→ create_all(125 张 ORM 表)
   │                        → 历史 migrations/*.py（可 --no-legacy 跳过）
   │                        → 校验关键表（不过则中止、不写账本）
   │                        → stamp 0001_baseline
   │                        → upgrade head
   └─ 有业务表 ──────────→ 仅 stamp 0001_baseline，**不执行任何 DDL**（需确认）
```

**"空库引导"到底能建多少张表？** 实测（2026-10-07）：

| 步骤 | 表数 |
|---|---|
| `create_all`（ORM 声明） | 125 |
| \+ 历史脚本成功执行 64/84 | **144** |
| 既有库（生产） | **171** |

144 < 171 **不是引导失败**。差额 30 张里绝大多数是**采集器运行时自建**的表——
`backend_core/data_collectors/**/_init_db()` 会在首次采集时建出来，例如
`weekly_quotes`（`weekly_collector.py`）、`industry_board_basic_info`
（`realtime_stock_industry_board_ak.py`）、7 张 `*_collect_operation_logs`；
另有少数在 `manual_scripts/` 下按需手工执行（如 `pvfrs_monitor_metrics`）。

20 个历史脚本失败的三类原因（都是历史遗留，非本次改造引入）：

| 原因 | 例子 | 处置 |
|---|---|---|
| argparse 脚本需人工传参 → `SystemExit` | `sync_industry_board_to_production.py` | 需要时手工单独跑 |
| 依赖采集器运行时才建的表 → `UndefinedTable` | `add_board_code_source.py` 需要 `industry_board_basic_info` | 采集跑过后再跑 |
| ORM 已建表导致种子数据 `NotNullViolation` | `add_gms_strategy_configs.py`（缺 `created_at`） | 用 Alembic 重写种子数据 |

> 提示：`migrations/` 内的脚本**按文件名排序**执行，本身存在依赖顺序问题
> （如 `add_cn_close_workflow_extra_nodes.py` 排在建表的
> `add_collection_workflow_tables.py` 之前）。这也是它们只能当"一次性建库补丁"
> 而不能当迁移系统用的原因之一。

### 4.2 两个历史 bug（本次顺带修掉）

原来的 `init_db.py` 用 `exec(code, globals)` 跑历史脚本，但注入的全局变量不完整，
导致它在空库上**从未成功过**：

| 缺失的注入名 | 后果 |
|---|---|
| `__file__` | 82 个脚本靠 `dirname(dirname(abspath(__file__)))` 定位项目根 → `NameError` |
| `__name__` | **84 个脚本全部**是 `if __name__ == "__main__": main()` → 不设成 `"__main__"` 则静默空转；**完全不设**则 `NameError` |

原实现两者都没给，于是 83/84 在第一行就抛 `NameError`，`run_all_migrations()`
返回 `False`，`main()` 直接 `sys.exit(1)`——**空库引导必定失败**。
现已注入 `__file__`（真实脚本路径，两个脚本还要读同目录 `sql/*.sql`）与
`__name__ = "__main__"`。

---

## 5. 日常工作流

### 5.1 加一个字段（推荐：手写）

```bash
.venv/Scripts/python.exe scripts/db_migrate.py revision -m "add source to stock_recommend_brief"
```

编辑生成的文件：

```python
def upgrade() -> None:
    op.add_column("stock_recommend_brief", sa.Column("source", sa.String(length=32)))
    op.create_index("ix_stock_recommend_brief_source", "stock_recommend_brief", ["source"])


def downgrade() -> None:
    op.drop_index("ix_stock_recommend_brief_source", table_name="stock_recommend_brief")
    op.drop_column("stock_recommend_brief", "source")
```

然后：

```bash
.venv/Scripts/python.exe scripts/db_migrate.py check      # 确认没有意外的大范围改动
.venv/Scripts/python.exe scripts/db_migrate.py upgrade
```

### 5.2 数据回填

拆成**独立 revision**，与 DDL 分开，出问题时只需回退一步：

```python
def upgrade() -> None:
    op.execute(sa.text("UPDATE xxx SET yyy = 0 WHERE yyy IS NULL"))
```

### 5.3 回滚

```bash
.venv/Scripts/python.exe scripts/db_migrate.py downgrade        # 撤销最后一步
.venv/Scripts/python.exe scripts/db_migrate.py downgrade 0001_baseline   # 回到基线
```

`upgrade` 在单个事务里执行（PG 的 DDL 可回滚），任一步失败即整体回退，
不会留下半迁移状态。

### 5.4 生产上线前预演

```bash
# 离线生成 SQL，交 DBA 审阅；不连库、不执行
.venv/Scripts/python.exe scripts/db_migrate.py sql
```

也可用 `alembic upgrade <from>:<to> --sql` 指定区间。

---

## 6. 环境变量与配置

| 变量 | 默认 | 作用 |
|---|---|---|
| `ALEMBIC_ALLOW_DROP` | `0` | 置 `1` 后放开"删表/删列"守卫。**仅在明确要删结构时临时开启** |
| `ALEMBIC_VERBOSE` | `0` | 置 `1` 打印 metadata 合并报告（排查 autogenerate 异常用） |

连接串来源（`env.py` → `backend_api.config`）：

1. 优先 `.env` 的 `DATABASE_URL`；
2. 否则由 `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` 拼装。

`alembic.ini` 中的 `sqlalchemy.url` 是空占位符，**口令不进配置文件**。

临时指向别的库：`alembic -x db_url=postgresql+psycopg2://... upgrade head`。

---

## 7. 部署注意

1. **`alembic.ini` 必须保持纯 ASCII**。
   Alembic 1.13.x 用**系统 locale** 编码读该文件（zh-CN Windows 下是 GBK），
   中文注释会导致 `UnicodeDecodeError: 'gbk' codec can't decode`。
   中文说明统一写在 `env.py`（Python 源，UTF-8）和本文档里。

2. **alembic 不在生产最小依赖里**。
   `backend_api/requirements-minimal.txt` 刻意不含 alembic（应用运行时不 import 它）。
   需要在服务器执行迁移时单独安装：
   ```bash
   pip install alembic==1.13.1
   ```

3. **迁机/恢复全量 dump 后**：dump 已含最终 schema，**不要**跑 `upgrade`。
   先 `python init_db.py --status` 看账本内容；若 `alembic_version` 不存在，
   直接 `python init_db.py`（等价于 `--stamp`，只写账本、不碰业务表）即可归位。

4. `versions/` 内的 revision 文件是**版本账本的一部分，必须入 git**，
   不要加进 `.gitignore`。

5. **生产发布流程不会自动执行迁移**，`upgrade` 必须手工敲。
   两条证据：
   * `scripts/deploy/release.ps1` 的迁移步骤是
     `if (Test-Path 'migrate_db.py') { python migrate_db.py }`，
     而**仓库里没有 `migrate_db.py`** → 该分支永不触发；
   * 生产启动器 `start_backend_api.py` 只起 `uvicorn`，不碰数据库。
     （`backend_api/start.py` 会调 `init_db.py` 自动 `upgrade head`，
     但生产用的不是它 —— 别混淆。）

6. **打包包含情况**（`scripts/deploy/deploy.ps1` 的排除清单）：

   | 路径 | 是否随发布包到服务器 |
   |---|---|
   | `alembic/`、`alembic.ini`、`scripts/` | ✅ 包含（迁移所需文件齐全） |
   | `docs/` | ❌ 排除 —— 所以生产机上**看不到本文件** |
   | `test/`、`migrations/`、`manual_scripts/` | ❌ 排除 |

   正因如此，**生产环境的操作说明写在 `alembic/README.md`**（该文件会随包发出），
   完整步骤见其「生产环境如何执行迁移」一节。以下是其要点摘录：

   ```bash
   # 服务器（部署根，即 current/）
   pg_dump ... -F c -f backup.dump      # 0) 备份
   python scripts/db_migrate.py status  # 1) 确认版本与连接目标（别连错库）
   python scripts/db_migrate.py sql     # 2) 预演（可选，不连库）
   python scripts/db_migrate.py upgrade # 3) 执行
   python init_db.py --verify           # 4) 校验
   ```

   前置条件：服务器需 `pip install alembic==1.13.1`（见第 2 条），
   且 `.env` 指向生产库（`env.py` 从 `backend_api.config` 取连接串）。

---

## 8. FAQ

**Q：`autogenerate` 出来几百行，能直接提交吗？**
不能。见 §3 坑 3。项目已确认存在 353 处类型层面的伪漂移。请手写受控的 revision。

**Q：为什么 `check` 里 `create_index` 有 160+ 个？**
ORM 里大量字段写了 `index=True`，而当年建表的手写 SQL 没建这些索引。
要不要补是**业务决策**（补上会占磁盘、拖慢写入），不应由 autogenerate 替你做。

**Q：`upgrade` 报了 `DuplicateTable` / `DuplicateColumn`？**
说明该库没打基线（或基线打到了错误版本）就直接跑 `upgrade`。先 `status` 确认，
再用 `stamp` 归位。

**Q：能不能把 `migrations/*.py` 转成 Alembic revision？**
技术上可行，但 84 个脚本已有对应的库状态，转过去只是把"已发生的历史"重写一遍，
不解决任何问题。价值在于**冻结旧的、接管新的**，这也是当前做法。

**Q：`alembic_version` 表能删吗？**
删掉即失去版本账本，下次 `upgrade` 会因无法确定当前版本而报错。
删除后需重新 `stamp` 到正确版本（`python init_db.py` 会自动识别为
"既有库未纳管"并只打标）。

**Q：`python init_db.py` 在全新库上建出来只有 144 张表，生产却有 171 张，正常吗？**
正常，不是引导失败。差额以**采集器运行时自建**的表为主（`weekly_quotes`、
`*_collect_operation_logs`、`industry_board_basic_info` …），首次采集时会自动出现。
详见 §4.1。若确实需要一次性补齐，应把这些表用 Alembic 重写成正式 revision，
而不是去修那 84 个冻结脚本。

**Q：`python init_db.py` 提示历史脚本失败一堆，要处理吗？**
空库引导时约 20/84 会失败，三类原因见 §4.1。它们**不影响** ORM 表与账本的写入，
可以用 `--no-legacy` 完全跳过（代价是 SQL-only 表缺失）。
若要让失败变成硬错误，加 `--strict-legacy`——此时校验不过就中止且**不写账本**。

**Q：为什么 `init_db.py` 要自己算一套决策逻辑，不直接 `alembic upgrade head`？**
因为 `0001_baseline` 是 no-op：直接 `upgrade` 在空库上什么也不会建，
在既有库上又什么都无法确认。引导必须区分"有没有业务表"，才能决定是
**建表后打标**还是**只打标**。

---

## 9. 命令速查

| 目的 | `db_migrate.py` | 等价 alembic 命令 |
|---|---|---|
| **引导/纳管库** | — | **`python init_db.py`** |
| **看库状态（含脱敏连接串）** | — | **`python init_db.py --status`** |
| 查看状态 | `status` | `alembic current` |
| 漂移预览 | `check` | `alembic check`（输出更原始） |
| 历史 | `history` | `alembic history` |
| 升级 | `upgrade [rev]` | `alembic upgrade head` |
| 回滚 | `downgrade [rev]` | `alembic downgrade -1` / `python init_db.py --rollback` |
| 打基线 | `stamp [rev]` | `alembic stamp 0001_baseline` / `python init_db.py --stamp` |
| 新建变更 | `revision -m "说明"` | `alembic revision -m "说明"` |
| 自动比对生成 | `revision -m "说明" --autogenerate` | `alembic revision --autogenerate` |
| 离线 SQL | `sql` | `alembic upgrade head --sql` |

---

## 10. 接入验证记录（2026-10-07）

### 10.1 初次接入（Alembic 脚手架）

| 验证项 | 结果 |
|---|---|
| `alembic heads` / `history` | ✅ `0001_baseline (head)` |
| `stamp 0001_baseline` 对既有库 | ✅ 生成 `alembic_version`，业务表未被动过（171 → 172 张，仅多账本表） |
| `env.py` metadata 合并 | ✅ 125(api) + 5(core-only) = 130，4 张同名取 api 侧 |
| 防误删守卫 | ✅ `upgrade` 段 `drop_table` / `drop_column` 计数为 0 |
| 端到端 upgrade | ✅ 临时 revision 建表成功，版本 → `0002_smoke` |
| 端到端 downgrade | ✅ 表被撤销，版本 → `0001_baseline`，库恢复原状 |
| `db_migrate.py status` | ✅ 口令脱敏为 `postgres:***@…` |

### 10.2 `init_db.py` 改造（同一日在**独立临时库**上实测）

临时库 `stock_analysis_initdb_test`，三条分支各跑一遍：

| 分支 | 场景构造 | 结果 |
|---|---|---|
| 空库引导 | 新建空库 `python init_db.py --no-legacy` | ✅ 建 125 张 ORM 表 → verify 通过 → `stamp 0001_baseline`；退出码 0 |
| 幂等复跑 | 同上库再跑一次 | ✅ 判定「已纳管且最新」→ 无需操作；表数不变 |
| 空库引导（含历史脚本） | 重建空库 `python init_db.py` | ✅ 历史脚本 64/84 成功，业务表 **144** 张 → `stamp 0001_baseline` |
| 既有库纳管 | 删掉 `alembic_version`（留有 125 张表） | ✅ 判定「既有库未纳管」→ 仅 stamp，表数**仍为 125**（未执行任何 DDL） |
| `--dry-run` | 空库 | ✅ 只打印 4 步计划，未创建任何对象 |
| 口令脱敏 | `--status` | ✅ `postgres:***@localhost:5446/…`，且 import 期的明文连接串打印已消除 |

> `__file__` / `__name__` 两个注入缺失是在这次实测中发现的：修复前 84 个脚本
> 「执行」后业务表仍是 125 张（`main()` 从未被调用）；修复后为 144 张。

### 10.3 全新库与既有库的表差异（144 vs 171）

缺失 30 张、多出 3 张。多出的 3 张（`one_yang_three_lines_signals`、
`system_alert_rules`、`system_performance_reports`）是 **ORM 声明了、真实库却没有**
的既有漂移——`create_all` 会把它们建出来，与本次改造无关，已记入 §3 坑 3。
缺失的 30 张以采集器运行时自建表为主，详见 §4.1。

---

## 相关文档

- `migrations/README.md` —— 历史脚本为何冻结
- `alembic/README.md` —— 目录说明
- `docs/design/系统设计.md` —— 系统总体设计
- `docs/prod/环境说明.md` —— 环境变量与端口
