# Alembic 迁移指南

> 适用范围：`stock_quote_analayze`（冰枫堂「股票分析」平台）全部数据库结构变更。
> 引入日期：2026-10-07 ｜ Alembic 版本：1.13.1 ｜ 数据库：PostgreSQL 17

---

## 1. 一句话上手

```bash
# 看状态（当前版本 / 是否已纳管）
.venv/Scripts/python.exe scripts/db_migrate.py status

# 看漂移（ORM metadata vs 真实库，只汇总不落文件）
.venv/Scripts/python.exe scripts/db_migrate.py check

# 建一个变更
.venv/Scripts/python.exe scripts/db_migrate.py revision -m "add xxx column to yyy"
#  → 编辑 alembic/versions/ 下新文件，写 op.add_column / op.create_table ...

# 执行 / 回滚
.venv/Scripts/python.exe scripts/db_migrate.py upgrade
.venv/Scripts/python.exe scripts/db_migrate.py downgrade      # 默认撤销一步
```

`db_migrate.py` 是 `alembic` 命令的封装（口令脱敏 + 漂移汇总 + 交互确认），
直接用 `.venv/Scripts/alembic.exe` 也完全可以。

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
scripts/db_migrate.py            # 便捷入口（status/check/upgrade/…）
migrations/                      # 历史手写脚本，**已冻结**（见其 README.md）
```

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
| **既有库**（已在跑，171 张表） | `db_migrate.py stamp 0001_baseline` —— 只写账本，不执行任何 DDL |
| **全新空库** | 先 `python init_db.py`（`create_all` + 历史脚本）建出等同现状的结构，再 `stamp 0001_baseline` |
| 之后所有变更 | 从 `0002` 起写进 `alembic/versions/`，`upgrade head` 增量应用 |

`stamp` 与 `upgrade` 的区别：`stamp` **只改 `alembic_version` 表**，
不会碰业务表；`upgrade` 会真的执行 DDL。既有库**千万不要**用 `upgrade` 代替 `stamp`。

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
   确认 `alembic_version` 表的内容，必要时 `stamp` 到正确版本即可。

4. `versions/` 内的 revision 文件是**版本账本的一部分，必须入 git**，
   不要加进 `.gitignore`。

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
删除后需重新 `stamp` 到正确版本。

---

## 9. 命令速查

| 目的 | `db_migrate.py` | 等价 alembic 命令 |
|---|---|---|
| 查看状态 | `status` | `alembic current` |
| 漂移预览 | `check` | `alembic check`（输出更原始） |
| 历史 | `history` | `alembic history` |
| 升级 | `upgrade [rev]` | `alembic upgrade head` |
| 回滚 | `downgrade [rev]` | `alembic downgrade -1` |
| 打基线 | `stamp [rev]` | `alembic stamp 0001_baseline` |
| 新建变更 | `revision -m "说明"` | `alembic revision -m "说明"` |
| 自动比对生成 | `revision -m "说明" --autogenerate` | `alembic revision --autogenerate` |
| 离线 SQL | `sql` | `alembic upgrade head --sql` |

---

## 10. 接入验证记录（2026-10-07）

| 验证项 | 结果 |
|---|---|
| `alembic heads` / `history` | ✅ `0001_baseline (head)` |
| `stamp 0001_baseline` 对既有库 | ✅ 生成 `alembic_version`，业务表未被动过（171 → 172 张，仅多账本表） |
| `env.py` metadata 合并 | ✅ 125(api) + 5(core-only) = 130，4 张同名取 api 侧 |
| 防误删守卫 | ✅ `upgrade` 段 `drop_table` / `drop_column` 计数为 0 |
| 端到端 upgrade | ✅ 临时 revision 建表成功，版本 → `0002_smoke` |
| 端到端 downgrade | ✅ 表被撤销，版本 → `0001_baseline`，库恢复原状 |
| `db_migrate.py status` | ✅ 口令脱敏为 `postgres:***@…` |

---

## 相关文档

- `migrations/README.md` —— 历史脚本为何冻结
- `alembic/README.md` —— 目录说明
- `docs/design/系统设计.md` —— 系统总体设计
- `docs/prod/环境说明.md` —— 环境变量与端口
