#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库引导与迁移入口 —— 版本管理权统一交给 Alembic。

本脚本负责把「一个数据库」带到「当前代码应处的 schema 状态」，并按库的现状
自动选择动作。**版本的唯一事实来源是 ``alembic_version`` 表**，不再依赖
``migrations/*.py`` 的文件修改时间或执行顺序。

三种起始状态
------------

====================== ==================================================
库的现状                本脚本的动作
====================== ==================================================
已有 ``alembic_version``  ``alembic upgrade head``（只应用未执行的 revision）
空库（无业务表）          **引导**：``create_all`` → 历史脚本 →
                        ``stamp 0001_baseline`` → ``upgrade head``
有业务表、无账本         **纳管**：**不执行任何 DDL**，仅 ``stamp 0001_baseline``
====================== ==================================================

第三种即本项目引入 Alembic 时既有生产库的情形：schema 早已由历史路径建好，
再跑一遍建表 DDL 会 ``DuplicateTable``；**打标（stamp）即完成纳管**，
业务数据与表结构都不动。

与历史 ``migrations/`` 的边界
----------------------------

``migrations/`` 下 84 个脚本已**冻结**（详见 ``migrations/README.md``）：

* 不再作为日常 schema 变更入口 —— 新变更一律写 ``alembic/versions/``；
* 仅在「空库引导」时作为一次性建库手段保留，可用 ``--no-legacy`` 跳过；
* 它们**不是幂等的**（58/84 带 ``IF NOT EXISTS``，其余是裸
  ``ALTER TABLE ... ADD COLUMN``，重复执行会 ``DuplicateColumn``），
  **绝不要在已有数据的库上重跑**；
* 其中少数脚本（如 ``backfill_missing_adj_factors.py``）会访问外部数据源补数据，
  离线环境请用 ``--no-legacy`` 规避；
* 实测在空库上 **64/84 能成功执行**（约 20 个失败：argparse 脚本缺人工参数、
  依赖采集器运行时建的表、ORM 已建表导致种子数据 NotNull 冲突）。因此
  **空库引导后表数约 144 张，少于既有库的 171 张**——差额多是采集器运行时
  ``_init_db()`` 自建的表，属预期，不是引导失败。

用法
----

::

    python init_db.py                    # 自动判断并执行（推荐）
    python init_db.py --status           # 只看状态，不写任何东西
    python init_db.py --dry-run          # 只打印将要执行的动作
    python init_db.py --stamp            # 只打标，纳管既有库（不动 DDL）
    python init_db.py --rollback         # alembic downgrade -1
    python init_db.py --verify           # 校验关键表结构
    python init_db.py --no-legacy        # 空库引导时跳过历史 migrations/*.py
    python init_db.py --strict-legacy    # 历史脚本任一失败即中止（默认宽松）
    python init_db.py --yes              # 跳过交互确认（CI / 无人值守）
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@contextlib.contextmanager
def _suppress_stdout():
    """临时吞掉 import 期的 stdout。

    ``backend_api.database`` 在模块级会 ``print("数据库连接URL:", ...)``，
    该字符串含明文口令。本脚本难免要 import 到它（经 ``backend_core.database.db``），
    这里把噪声连同口令一起挡在控制台之外。
    """
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        yield
    finally:
        sys.stdout = old


with _suppress_stdout():
    from backend_core.database.db import engine, get_db_session
    from backend_core.logging_utils import resolve_log_file

    from backend_api.models import Base, PushRecord, User, UserPushConfig

from sqlalchemy import inspect

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 基线 revision —— 引入 Alembic 那一刻既有库的 schema 状态（no-op）
BASELINE_REVISION = "0001_baseline"

#: Alembic 的版本账本表名（与 alembic/env.py 的 VERSION_TABLE 保持一致）
VERSION_TABLE = "alembic_version"

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"

#: 历史迁移脚本目录（已冻结，仅空库引导时使用）
DEFAULT_MIGRATION_DIR = "migrations"


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------


def setup_logging(force: bool = False) -> None:
    """配置日志。

    ``force=True`` 用于在调用 Alembic 之后重建 root logger ——
    ``alembic/env.py`` 会执行 ``fileConfig(alembic.ini)``，把 root 级别压到
    WARNING 并换掉 handler，不恢复的话本脚本后续的 INFO 日志会全部消失。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(resolve_log_file("init_db.log")),
            logging.StreamHandler(sys.stdout),
        ],
        force=force,
    )


def _safe_url() -> str:
    """脱敏后的连接串（口令替换为 ***），仅供日志展示。"""
    with _suppress_stdout():
        from backend_api.config import DATABASE_CONFIG

    url = (DATABASE_CONFIG.get("url") or "").strip()
    masked = re.sub(r"(://[^:/@]*:)[^@]*(@)", r"\1***\2", url)
    return masked or "(未配置)"


# ---------------------------------------------------------------------------
# Alembic 桥接
# ---------------------------------------------------------------------------


def _alembic_config():
    """构造 Alembic Config（路径全部绝对化，与 cwd 无关）。"""
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return cfg


def _script_directory():
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic_config())


def _head_revision() -> str | None:
    with contextlib.suppress(Exception):
        return _script_directory().get_current_head()
    return None


def _revision_exists(revision: str) -> bool:
    with contextlib.suppress(Exception):
        return _script_directory().get_revision(revision) is not None
    return False


def _down_revision(revision: str) -> str | None:
    """返回某 revision 的上一步（merge 节点返回 None，此处不涉及）。"""
    with contextlib.suppress(Exception):
        down = _script_directory().get_revision(revision).down_revision
        return down if isinstance(down, str) else None
    return None


def _current_revision() -> str | None:
    """直接读账本表，不经过 env.py（便宜且无日志副作用）。"""
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"version_table": VERSION_TABLE})
        return ctx.get_current_revision()


def _run_alembic(func, *args, **kwargs):
    """执行 Alembic 命令，并在结束后恢复本脚本的日志配置。"""
    setup_logging(force=True)  # 先落定一次，避免 env.py 的 fileConfig 影响本次输出
    cfg = _alembic_config()
    try:
        return func(cfg, *args, **kwargs)
    finally:
        setup_logging(force=True)


# ---------------------------------------------------------------------------
# 库状态探测
# ---------------------------------------------------------------------------


def db_state() -> dict:
    """探测库的现状：是否纳管、当前 revision、业务表数量。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    managed = VERSION_TABLE in tables
    business = tables - {VERSION_TABLE}

    current = None
    if managed:
        with contextlib.suppress(Exception):
            current = _current_revision()

    return {
        "managed": managed,
        "current": current,
        "business_tables": sorted(business),
        "table_count": len(business),
    }


def check_table_exists(table_name: str) -> bool:
    """检查表是否存在。"""
    return table_name in inspect(engine).get_table_names()


# ---------------------------------------------------------------------------
# 建表：ORM 声明的部分
# ---------------------------------------------------------------------------


def create_orm_tables(dry_run: bool = False) -> list[str]:
    """建 ``Base.metadata`` 声明的表（``checkfirst``，已存在的不动）。

    返回「本次新建」的表名。注意：约 44 张纯 SQL 建的表不在 ORM 声明内，
    需由历史 ``migrations/*.py`` 补齐（见 ``--no-legacy``）。
    """
    logger = logging.getLogger(__name__)

    existing = set(inspect(engine).get_table_names())
    missing = [t for t in sorted(Base.metadata.tables) if t not in existing]

    if not missing:
        logger.info("ORM 声明的表已全部存在，无需 create_all。")
        return []

    if dry_run:
        shown = ", ".join(missing[:12]) + (" …" if len(missing) > 12 else "")
        logger.info("【模拟】将创建 %d 张 ORM 表: %s", len(missing), shown)
        return missing

    logger.info("开始创建 %d 张 ORM 表 ...", len(missing))
    Base.metadata.create_all(bind=engine)
    logger.info("ORM 表创建完成。")
    return missing


# ---------------------------------------------------------------------------
# 建表：历史迁移脚本（冻结的一次性建库路径）
# ---------------------------------------------------------------------------


def run_migration(migration_file: str, dry_run: bool = False) -> bool:
    """执行单个历史迁移脚本（``exec`` 注入 engine / Base 等旧环境）。"""
    logger = logging.getLogger(__name__)

    if not os.path.exists(migration_file):
        logger.error("迁移文件不存在: %s", migration_file)
        return False

    if dry_run:
        logger.info("【模拟】将执行迁移脚本 %s", migration_file)
        return True

    logger.info("运行迁移: %s", migration_file)
    try:
        with open(migration_file, "r", encoding="utf-8") as fh:
            migration_code = fh.read()

        script_path = Path(migration_file).resolve()
        exec_globals = {
            # 这两个名字必须注入，否则 84 个脚本全部无法真正执行（历史遗留 bug）：
            #
            # * ``__file__`` —— 82 个脚本靠 ``os.path.dirname(os.path.dirname(
            #   os.path.abspath(__file__)))`` 定位项目根再 sys.path.insert；
            #   另有两个用 ``Path(__file__).parent / "sql" / "*.sql"`` 读同目录 SQL。
            # * ``__name__`` —— **84 个脚本全部**以 ``if __name__ == "__main__":
            #   main()`` 为入口。必须显式设为 ``"__main__"`` 才会真正执行；
            #   用别的值（如模块名）会静默空转，不报错但不建表。
            "__file__": str(script_path),
            "__name__": "__main__",
            "engine": engine,
            "get_db_session": get_db_session,
            "Base": Base,
            "User": User,
            "UserPushConfig": UserPushConfig,
            "PushRecord": PushRecord,
        }
        exec(migration_code, exec_globals)  # noqa: S102 - 历史脚本契约，migrations/ 已冻结
        logger.info("迁移完成: %s", migration_file)
        return True
    except SystemExit as exc:
        # 5 个脚本用 argparse，且形如 ``raise SystemExit(main())``：参数缺失或用法
        # 错误时 argparse 会抛 SystemExit(2)。SystemExit 不是 Exception 的子类，
        # 不单独接住会直接冲出整个引导流程。
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if code == 0:
            logger.info("迁移完成（脚本显式 SystemExit(0)）: %s", script_path.name)
            return True
        logger.error(
            "迁移失败: %s -> SystemExit(%s)（该脚本需人工传参，非建表必需）",
            script_path.name,
            exc.code,
        )
        return False
    except Exception as exc:  # noqa: BLE001 - 单个脚本失败不应中断整批（宽松模式）
        logger.error("迁移失败: %s -> %s: %s", script_path.name, type(exc).__name__, exc)
        return False


def run_all_migrations(
    migration_dir: str | Path = DEFAULT_MIGRATION_DIR,
    dry_run: bool = False,
) -> tuple[bool, int, list[str]]:
    """跑完 ``migration_dir`` 下所有 ``*.py``。

    返回 ``(ok, executed, failures)``。``ok`` 仅在零失败时为 True；
    调用方决定是否因此中止（见 ``--strict-legacy``）。
    """
    logger = logging.getLogger(__name__)

    path = Path(migration_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.is_dir():
        logger.error("迁移目录不存在: %s", path)
        return False, 0, []

    files = sorted(p for p in path.glob("*.py") if not p.name.startswith("__"))
    if not files:
        logger.warning("在 %s 中没有找到迁移文件", path)
        return True, 0, []

    logger.info("发现 %d 个历史迁移脚本（目录 %s）", len(files), path)
    logger.info("提示：这些脚本已冻结、且不保证幂等，只在空库引导时执行。")

    failures: list[str] = []
    executed = 0
    for file in files:
        if run_migration(str(file), dry_run=dry_run):
            executed += 1
        else:
            failures.append(file.name)

    logger.info("历史迁移完成 %d/%d，失败 %d", executed, len(files), len(failures))
    if failures:
        shown = ", ".join(failures[:10]) + (" …" if len(failures) > 10 else "")
        logger.warning("失败脚本: %s", shown)
    return not failures, executed, failures


# ---------------------------------------------------------------------------
# 校验与状态展示
# ---------------------------------------------------------------------------


def verify_tables() -> bool:
    """校验几张关键表及其列是否存在。"""
    logger = logging.getLogger(__name__)
    logger.info("验证数据库表结构 ...")

    required_tables = {
        "users": ["id", "username", "email", "wechat_openid", "wechat_type"],
        "user_push_configs": ["id", "user_id", "enabled", "channels", "push_times", "report_type"],
        "push_records": ["id", "user_id", "push_date", "push_time", "status", "channel_status"],
    }

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    all_valid = True
    for table_name, required_columns in required_tables.items():
        if table_name not in existing:
            logger.error("表不存在: %s", table_name)
            all_valid = False
            continue

        columns = {col["name"] for col in inspector.get_columns(table_name)}
        missing = set(required_columns) - columns
        if missing:
            logger.error("表 %s 缺少列: %s", table_name, ", ".join(sorted(missing)))
            all_valid = False
        else:
            logger.info("✓ 表 %s 结构正确", table_name)

    return all_valid


def print_status() -> None:
    """打印库 + Alembic 账本状态。"""
    logger = logging.getLogger(__name__)
    state = db_state()
    head = _head_revision()

    logger.info("=" * 60)
    logger.info("数据库与 Alembic 状态")
    logger.info("=" * 60)
    logger.info("连接:        %s", _safe_url())
    logger.info("业务表数量:  %d", state["table_count"])
    logger.info(
        "版本账本表:  %s",
        "存在 (%s)" % VERSION_TABLE if state["managed"] else "不存在（尚未纳管）",
    )
    logger.info("当前 revision: %s", state["current"] or "(无)")
    logger.info("代码 head:     %s", head or "(读取失败)")

    if not state["managed"]:
        if state["table_count"] == 0:
            logger.info("判定: 空库 —— 运行 `python init_db.py` 将建表并打标基线。")
        else:
            logger.info(
                "判定: 既有库未纳管（%d 张表）—— 运行 `python init_db.py` 将 stamp %s，不动 DDL。",
                state["table_count"],
                BASELINE_REVISION,
            )
    elif head and state["current"] == head:
        logger.info("判定: ✓ 已纳管且为最新。")
    else:
        logger.info("判定: ⚠ 有待应用的 revision —— 运行 `python init_db.py` 即可 apply。")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# 交互确认
# ---------------------------------------------------------------------------


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{prompt} [非交互环境，默认继续]")
        return True
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# 核心：引导 / 迁移
# ---------------------------------------------------------------------------


def _summarize(state: dict, head: str | None) -> str:
    if not state["managed"]:
        if state["table_count"] == 0:
            return "空库 → 引导（create_all + 历史脚本 + stamp 基线）"
        return f"既有库未纳管（{state['table_count']} 张表）→ 仅打标基线"
    if head and state["current"] == head:
        return f"已纳管且最新（{state['current']}）→ 无需操作"
    return f"已纳管（{state['current']}）→ upgrade head ({head})"


def bootstrap(args: argparse.Namespace) -> int:
    """按库的现状决定动作，并执行。"""
    logger = logging.getLogger(__name__)

    state = db_state()
    head = _head_revision()
    baseline = args.baseline

    logger.info("判定: %s", _summarize(state, head))
    logger.info("-" * 60)

    # ---- 分支 1：已纳管 → 只做增量升级 -------------------------------------
    if state["managed"]:
        if head and state["current"] == head:
            logger.info("✓ 库已是最新 revision（%s），无需操作。", head)
            return 0
        if args.dry_run:
            logger.info("【模拟】将执行: alembic upgrade head (%s → %s)", state["current"], head)
            return 0

        logger.info("执行 alembic upgrade head (%s → %s) ...", state["current"], head)
        _run_alembic(_command().upgrade, "head")
        after = db_state()
        logger.info("✓ 升级完成，当前 revision: %s", after["current"])
        return 0

    # ---- 分支 2：空库 → 引导 ----------------------------------------------
    if state["table_count"] == 0:
        logger.info("检测到空库，开始引导。")

        if args.dry_run:
            existing = set(inspect(engine).get_table_names())
            missing = [t for t in sorted(Base.metadata.tables) if t not in existing]
            logger.info("【模拟】步骤 1: create_all —— 将创建 %d 张 ORM 表", len(missing))
            if args.run_legacy:
                logger.info(
                    "【模拟】步骤 2: 执行历史迁移脚本（目录 %s）", args.migration_dir
                )
            else:
                logger.info("【模拟】步骤 2: 跳过历史迁移脚本（--no-legacy）")
            logger.info("【模拟】步骤 3: stamp %s", baseline)
            if head and head != baseline:
                logger.info("【模拟】步骤 4: alembic upgrade head (%s → %s)", baseline, head)
            return 0

        if not _revision_exists(baseline):
            logger.error("基线 revision %s 不存在于 alembic/versions/，已中止。", baseline)
            return 1

        # 步骤 1：ORM 表
        created = create_orm_tables()

        # 步骤 2：历史脚本补齐 SQL-only 表
        legacy_ok = True
        if args.run_legacy:
            legacy_ok, _executed, failures = run_all_migrations(
                args.migration_dir, dry_run=False
            )
            if not legacy_ok and args.strict_legacy:
                logger.error(
                    "有 %d 个历史脚本失败，--strict-legacy 已开启，中止且不写入账本。",
                    len(failures),
                )
                return 1
            if not legacy_ok:
                logger.warning(
                    "历史脚本有失败项（实测约 20/84）。常见原因三类："
                    "① argparse 脚本缺人工参数（SystemExit）；"
                    "② 依赖的表由采集器运行时创建，此时尚不存在（UndefinedTable）；"
                    "③ ORM 已建表导致种子数据 NotNull 冲突。"
                )
                logger.warning("账本仍会写入，但请核对上面列出的失败脚本。")
        else:
            logger.info("已跳过历史迁移脚本（--no-legacy）：SQL-only 表将缺失。")

        # 步骤 3：校验关键表
        if not verify_tables():
            logger.error("关键表结构校验未通过，已中止且未写入账本（避免把异常状态纳管）。")
            return 1

        # 步骤 4：打标基线
        logger.info("写入版本账本: stamp %s ...", baseline)
        _run_alembic(_command().stamp, baseline)

        # 步骤 5：应用基线之后的新 revision
        if head and head != baseline:
            logger.info("应用基线之后的 revision: upgrade head ...")
            _run_alembic(_command().upgrade, "head")

        after = db_state()
        logger.info(
            "✓ 引导完成：新建 ORM 表 %d 张，业务表总数 %d，revision=%s",
            len(created),
            after["table_count"],
            after["current"],
        )
        logger.info(
            "注意：全新库引导后的表数**少于**既有库（实测约 144 张 vs 171 张），这不是失败。"
        )
        logger.info(
            "      差额多为采集器运行时自建的表（weekly_quotes / *_collect_operation_logs 等，"
            "见 backend_core/data_collectors/**/_init_db），首次采集时自动出现；"
        )
        logger.info("      另有 manual_scripts/ 下的手工建表脚本需按需执行。")
        return 0

    # ---- 分支 3：既有库未纳管 → 只打标 -----------------------------------
    logger.warning(
        "库中已有 %d 张业务表但没有 %s 账本：这是「引入 Alembic 时既有库」的情形。",
        state["table_count"],
        VERSION_TABLE,
    )
    logger.warning("将只写入版本账本，**不执行任何建表 / 改表 DDL**，业务数据不受影响。")

    if not _confirm(f"确认将 {baseline} 写入版本账本？", args.yes):
        logger.warning("已取消。")
        return 1

    if args.dry_run:
        logger.info("【模拟】将执行: alembic stamp %s", baseline)
        return 0

    logger.info("执行 alembic stamp %s ...", baseline)
    _run_alembic(_command().stamp, baseline)

    if head and head != baseline:
        logger.info("随后应用更新的 revision: upgrade head ...")
        _run_alembic(_command().upgrade, "head")

    if not verify_tables():
        logger.warning("关键表结构校验未通过 —— 库原本就缺这些表，请人工确认。")

    after = db_state()
    logger.info("✓ 纳管完成，当前 revision: %s（业务表 %d 张）", after["current"], after["table_count"])
    return 0


def _command():
    """延迟导入 alembic.command（避免无谓的 import 开销与副作用）。"""
    from alembic import command

    return command


def cmd_stamp_only(args: argparse.Namespace) -> int:
    """只打标，不动 DDL。"""
    logger = logging.getLogger(__name__)

    state = db_state()
    if state["managed"] and state["current"]:
        logger.warning("库已纳管（revision=%s），无需重复打标。", state["current"])
        return 0

    if state["table_count"] == 0:
        logger.error("库中没有任何业务表，对空库打标没有意义。")
        logger.error("请直接运行 `python init_db.py` 进行完整引导。")
        return 1

    if not _revision_exists(args.baseline):
        logger.error("revision %s 不存在于 alembic/versions/。", args.baseline)
        return 1

    logger.info("将对 %d 张业务表打标 %s（不执行 DDL）。", state["table_count"], args.baseline)
    if not _confirm("确认？", args.yes):
        logger.warning("已取消。")
        return 1
    if args.dry_run:
        logger.info("【模拟】将执行: alembic stamp %s", args.baseline)
        return 0

    _run_alembic(_command().stamp, args.baseline)
    logger.info("✓ 已打标，当前 revision: %s", db_state()["current"])
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    """回退一步（alembic downgrade -1）。"""
    logger = logging.getLogger(__name__)

    state = db_state()
    if not state["managed"]:
        logger.error("库未纳管（无 %s 表），没有可回退的 revision。", VERSION_TABLE)
        return 1

    current = state["current"]
    if not current:
        logger.error("账本为空，没有可回退的 revision。")
        return 1

    target = _down_revision(current)
    if target is None:
        logger.warning("revision=%s 已是基线/起点，回退不会改变 schema。", current)
        return 1

    logger.info("将回退: %s → %s", current, target)
    if not _confirm("确认回退？该操作会执行 downgrade 中的 DDL。", args.yes):
        logger.warning("已取消。")
        return 1
    if args.dry_run:
        logger.info("【模拟】将执行: alembic downgrade -1")
        return 0

    _run_alembic(_command().downgrade, "-1")
    logger.info("✓ 回退完成，当前 revision: %s", db_state()["current"])
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="数据库引导与迁移（Alembic 统一入口）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--migration-dir",
        default=DEFAULT_MIGRATION_DIR,
        help=f"历史迁移脚本目录（默认 {DEFAULT_MIGRATION_DIR}，仅空库引导时使用）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅显示将要执行的操作，不实际执行")
    parser.add_argument(
        "--force",
        action="store_true",
        help="【已废弃】引导逻辑现按库的现状自动决策，此参数不再改变行为",
    )
    parser.add_argument("--rollback", action="store_true", help="回退一步（alembic downgrade -1）")
    parser.add_argument("--status", action="store_true", help="显示数据库与 Alembic 状态")
    parser.add_argument("--verify", action="store_true", help="校验关键表结构")
    parser.add_argument("--stamp", action="store_true", help="只打标基线，不建表/不跑脚本")
    parser.add_argument(
        "--baseline",
        default=BASELINE_REVISION,
        help=f"基线 revision id（默认 {BASELINE_REVISION}）",
    )
    parser.add_argument(
        "--no-legacy",
        dest="run_legacy",
        action="store_false",
        help="空库引导时跳过历史 migrations/*.py（SQL-only 表将缺失）",
    )
    parser.add_argument(
        "--strict-legacy",
        action="store_true",
        help="历史脚本任一失败即中止（默认宽松：记录失败并继续）",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="跳过交互确认")
    parser.set_defaults(run_legacy=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    setup_logging(force=True)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("数据库引导与迁移工具（Alembic 统一入口）")
    logger.info("=" * 60)

    try:
        if args.status:
            print_status()
            return 0

        if args.verify:
            ok = verify_tables()
            logger.info("✓ 关键表结构验证通过" if ok else "✗ 关键表结构验证失败")
            return 0 if ok else 1

        if args.rollback:
            return cmd_rollback(args)

        if args.stamp:
            return cmd_stamp_only(args)

        if args.force:
            logger.warning("--force 已废弃：请改用 `--stamp` 或直接运行本脚本（自动决策）。")

        return bootstrap(args)

    except KeyboardInterrupt:
        logger.warning("已中断。")
        return 130
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证退出码语义
        logger.error("执行失败: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
