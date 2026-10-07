"""Alembic 运行环境 —— 股票分析系统（冰枫堂）

设计要点（改动前请先读完整段）：

1. **口令不落配置文件**
   连接串统一从 ``backend_api.config.DATABASE_CONFIG`` 读取，其来源是项目根 ``.env``
   的 ``DATABASE_URL`` 或 ``DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD``。
   ``alembic.ini`` 里的 ``sqlalchemy.url`` 只是空占位符。
   可用 ``alembic -x db_url=postgresql+psycopg2://... upgrade head`` 临时覆盖。

2. **target_metadata 由两套独立 Base 合并成单一 MetaData**
   本项目历史上存在两个互不相干的 ``declarative_base()``：

   * ``backend_api.models.Base``      → 125 张表（主 ORM，定义在 ``models.py``；
     注意 ``backend_api/models`` 是**包**，``Base`` 由包内 importlib 载入 ``models.py``）
   * ``backend_core.database.db.Base`` → 9 张表（采集流程 / watchlist 等历史 ORM）

   二者都必须纳入，否则 autogenerate 会认为是"多余对象"而想要删表。

   **但不能直接传 ``target_metadata=[api_md, core_md]``**：Alembic 的
   ``AutogenContext.table_key_to_table``（``alembic/autogenerate/api.py``）明确
   "Duplicate table keys across multiple MetaData objects" 会抛 ``ValueError``。
   本项目恰有 4 张同名表（``watchlist`` / ``historical_quotes`` /
   ``ma_indicators`` / ``macd_indicators``）两边都有，直接传列表必挂。

   因此这里用 ``MetaData.to_metadata()`` 深拷贝合并成一个 MetaData，
   **以 backend_api 侧定义为准**（先拷 api，再补 core 中不重名的表）。

3. **防误删守卫（本文件最重要的部分）**
   库里现有 171 张表，而两套 ORM 合计只声明了 130 张。差额的 40+ 张
   （``historical_quotes``、``market_daily_review``、龙虎榜、财报季频表……）
   是**由 ``migrations/*.py`` 手写 SQL 创建**、并无 ORM 声明的表。
   若不做处理，``alembic revision --autogenerate`` 会生成一堆 ``op.drop_table``，
   一旦执行即**不可逆丢数据**。

   因此默认策略是「**只增不减**」：
   ``include_object`` 会跳过所有「库中存在但 metadata 未声明」的对象
   （表 / 列 / 索引 / 约束），即 autogenerate 永远不会生成 DROP。
   确实需要删除时，显式设置 ``ALEMBIC_ALLOW_DROP=1`` 再跑。

4. **对比项取舍**
   ``compare_type=True``  —— 改列类型能被识别（PG 下有效）。
   ``compare_server_default`` 保持关闭 —— PG 的 ``CURRENT_TIMESTAMP`` /
   ``now()`` 表达差异会制造大量假阳性，噪声大于收益。
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import MetaData

# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------

# alembic.ini 已设 prepend_sys_path = .；此处再兜底一次，保证从任意 cwd 调用都能 import
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Alembic Config 对象（alembic.ini 的值）
config = context.config

# 标准日志初始化
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


@contextlib.contextmanager
def _suppress_stdout():
    """临时吞掉 import 期间的 stdout。

    ``backend_api.database`` 在模块级会 ``print("数据库连接URL:", ...)``，
    该字符串含明文口令。env.py 需要 import 到它（经 backend_core.database.db），
    这里把噪声与口令一并挡在控制台之外。
    """
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        yield
    finally:
        sys.stdout = old


def _load_metadata():
    """加载并合并两套 ORM metadata，返回 (merged_metadata, db_url, report)。"""
    with _suppress_stdout():
        import backend_api.models as api_models  # noqa: F401  (触发包内 importlib 载入)
        import backend_core.database.db as core_db

        # backend_core/models/ 下各模块需显式 import 才会把表注册进 core metadata
        try:
            import importlib
            import pkgutil

            import backend_core.models as core_models

            for mod in pkgutil.iter_modules(core_models.__path__):
                with contextlib.suppress(Exception):
                    importlib.import_module(f"backend_core.models.{mod.name}")
        except Exception:  # pragma: no cover - 缺失该包时不影响主 metadata
            pass

        from backend_api.config import DATABASE_CONFIG

        db_url = DATABASE_CONFIG["url"]

    api_md = api_models.Base.metadata
    core_md = core_db.Base.metadata

    # --- 合并为单一 MetaData（api 侧优先）--------------------------------
    merged = MetaData()
    for table in api_md.sorted_tables:
        table.to_metadata(merged)

    skipped: list[str] = []
    copied_from_core = 0
    for table in core_md.sorted_tables:
        if table.key in merged.tables:
            skipped.append(table.key)
            continue
        table.to_metadata(merged)
        copied_from_core += 1

    report = {
        "api_tables": len(api_md.tables),
        "core_tables": len(core_md.tables),
        "core_only_copied": copied_from_core,
        "overlap_taken_from_api": sorted(skipped),
        "merged_tables": len(merged.tables),
    }
    return merged, db_url, report


TARGET_METADATA, DB_URL, METADATA_REPORT = _load_metadata()

# ALEMBIC_VERBOSE=1 时输出 metadata 合并情况，便于排查 autogenerate 结果异常
if (os.getenv("ALEMBIC_VERBOSE") or "").strip().lower() in ("1", "true", "yes"):
    print(f"[alembic] metadata 合并报告: {METADATA_REPORT}", file=sys.stderr)

# 写回 config，供迁移脚本内 `op.get_bind()` 之外的场景与分析工具读取
config.set_main_option("sqlalchemy.url", (DB_URL or "").replace("%", "%%"))

# 是否允许 autogenerate 生成 DROP（默认关闭，见文件头第 3 点）
ALLOW_DROP = (os.getenv("ALEMBIC_ALLOW_DROP") or "").strip().lower() in ("1", "true", "yes")

# Alembic 自身的版本账本表
VERSION_TABLE = "alembic_version"


def include_object(obj, name, type_, reflected, compare_to):
    """autogenerate 对象过滤器。

    默认（ALLOW_DROP 未开）跳过所有「仅存在于数据库、metadata 未声明」的对象，
    使 autogenerate 只输出 CREATE / ADD COLUMN，绝不输出 DROP。
    """
    if not ALLOW_DROP and reflected and compare_to is None:
        return False
    return True


def include_name(name, type_, parent_names):
    """按名称过滤：不参与管理的库内命名空间（schema 等）。"""
    if type_ == "schema":
        # PG 下只处理默认 schema，避免把 pg_catalog / information_schema 拉进来
        return name in (None, "public")
    return True


def _configure_kwargs() -> dict:
    return dict(
        target_metadata=TARGET_METADATA,
        include_object=include_object,
        include_name=include_name,
        compare_type=True,
        # 见文件头第 4 点：关闭 server default 对比，避免 PG 假阳性
        compare_server_default=False,
        version_table=VERSION_TABLE,
        render_as_batch=False,  # PostgreSQL 无需 batch 模式
    )


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库（alembic upgrade head --sql）。"""
    context.configure(
        url=DB_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连库执行。

    整个 ``upgrade`` 跑在单个事务里（``transaction_per_migration`` 保持默认 False），
    PG 的 DDL 可回滚，任一 revision 失败即整体回退，不会留下半迁移状态。
    """
    with _suppress_stdout():
        from backend_api.database import engine

    with engine.connect() as connection:
        context.configure(connection=connection, **_configure_kwargs())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
