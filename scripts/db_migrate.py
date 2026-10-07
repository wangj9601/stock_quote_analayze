#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Alembic 便捷入口 —— 股票分析系统（冰枫堂）

为什么要这个脚本，而不是直接用 ``alembic`` 命令：

1. **口令脱敏**：``backend_api.database`` 在 import 时会打印含明文口令的连接串，
   本脚本统一吞掉该输出，并在需要显示时用 ``***`` 替换口令。
2. **漂移预览（``check``）**：本项目 ORM metadata 与真实库结构存在系统性偏差
   （见 ``docs/database/Alembic_guide.md``），直接跑
   ``alembic revision --autogenerate`` 会生成体量巨大、含高危操作的迁移。
   ``check`` 只做**汇总**（按操作类型计数 + 涉及表名），不落任何文件，
   用来判断"这次 autogenerate 能不能用"。
3. **中文帮助**：命令行提示与项目文档口径一致。

用法::

    .venv/Scripts/python.exe scripts/db_migrate.py status
    .venv/Scripts/python.exe scripts/db_migrate.py check
    .venv/Scripts/python.exe scripts/db_migrate.py upgrade
    .venv/Scripts/python.exe scripts/db_migrate.py revision -m "add xxx column"
    .venv/Scripts/python.exe scripts/db_migrate.py revision -m "auto" --autogenerate
    .venv/Scripts/python.exe scripts/db_migrate.py stamp 0001_baseline
    .venv/Scripts/python.exe scripts/db_migrate.py sql

所有非只读命令都会先打印将要执行的动作并要求确认（``--yes`` 跳过）。
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"

# 仅用于 check 的临时 revision 标识，会在 finally 中删除
CHECK_TMP_REV_ID = "check_tmp_zz"


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def suppress_stdout():
    """吞掉 import 期间的 stdout（backend_api.database 会打印含口令的连接串）。"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old


def mask_url(url: str) -> str:
    """把 postgresql+psycopg2://user:pwd@host/db 的口令替换为 ***。"""
    if not url:
        return "(空)"
    return re.sub(r"(//[^:/@]+:)[^@]*(@)", r"\1***\2", url)


def load_db_url() -> str:
    with suppress_stdout():
        from backend_api.config import DATABASE_CONFIG

    return DATABASE_CONFIG["url"]


def alembic_config():
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise SystemExit(f"[ERROR] 未找到 {ALEMBIC_INI}")
    return Config(str(ALEMBIC_INI))


def confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    try:
        return input(f"{prompt} (Y/N): ").strip().upper() == "Y"
    except EOFError:
        print("已取消（无交互输入）。如需无人值守请加 --yes。")
        return False


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect

    cfg = alembic_config()
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    print("=" * 62)
    print(" Alembic 状态")
    print("=" * 62)
    print(f" 配置文件      : {ALEMBIC_INI.relative_to(PROJECT_ROOT)}")
    print(f" 脚本目录      : {VERSIONS_DIR.relative_to(PROJECT_ROOT)}")
    print(f" 连接串(脱敏)  : {mask_url(load_db_url())}")
    print(f" 版本 head     : {', '.join(heads) if heads else '(无)'}")

    # 版本文件清单
    revs = list(script.walk_revisions())
    print(f" 版本数        : {len(revs)}")
    for r in revs:
        print(f"   - {r.revision:<24} {r.doc.splitlines()[0] if r.doc else ''}")

    # 库内状态
    try:
        with suppress_stdout():
            from backend_core.database.db import engine

        with engine.connect() as conn:
            insp = inspect(conn)
            tables = insp.get_table_names()
            if "alembic_version" in tables:
                from sqlalchemy import text

                cur = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                current = ", ".join(r[0] for r in cur) or "(空表)"
            else:
                current = "(未打标：表 alembic_version 不存在)"

        print(f" 数据库当前版本: {current}")
        print(f" 数据库表总数  : {len(tables)}")

        if current == "(空表)" or current.startswith("(未打标"):
            print()
            print(" [!] 该库尚未纳入 Alembic 版本管理。")
            print("     既有库请执行：db_migrate.py stamp 0001_baseline")
            print("     全新库先建表（init_db.py），再 stamp。")
    except Exception as exc:  # pragma: no cover - 连库失败时给友好提示
        print(f" [!] 无法连接数据库：{type(exc).__name__}: {exc}")

    print("=" * 62)
    return 0


# ---------------------------------------------------------------------------
# check —— 漂移预览（不落文件）
# ---------------------------------------------------------------------------

_OP_PATTERNS = {
    "create_table": r"op\.create_table\(",
    "drop_table": r"op\.drop_table\(",
    "add_column": r"op\.add_column\(",
    "drop_column": r"op\.drop_column\(",
    "create_index": r"op\.create_index\(",
    "drop_index": r"op\.drop_index\(",
    "alter_column": r"op\.alter_column\(",
    "create_foreign_key": r"op\.create_foreign_key\(",
    "create_unique_constraint": r"op\.create_unique_constraint\(",
    "drop_constraint": r"op\.drop_constraint\(",
    "execute": r"op\.execute\(",
}

# 结构性删除：真的会丢表 / 丢列（数据不可逆），必须人工复核
STRUCTURAL_DROPS = ("drop_table", "drop_column")

_UPGRADE_HEAD = re.compile(r"^def upgrade\([^\n]*\)[^\n]*:", re.M)
_DOWNGRADE_HEAD = re.compile(r"^def downgrade\([^\n]*\)[^\n]*:", re.M)


def _clean_stale_check_files() -> list[Path]:
    removed = []
    if not VERSIONS_DIR.is_dir():
        return removed
    for p in VERSIONS_DIR.glob(f"*{CHECK_TMP_REV_ID}*"):
        with contextlib.suppress(OSError):
            p.unlink()
            removed.append(p)
    return removed


def _upgrade_body(text: str) -> str:
    """只取 ``def upgrade()`` 与 ``def downgrade()`` 之间的函数体。

    必须这样切两刀，否则统计会失真：

    * **后半刀（到 downgrade 为止）**：Alembic 生成的 ``downgrade()`` 会自动镜像
      ``upgrade()``（create_table → drop_table、create_index → drop_index …）。
      整文件统计会把"回滚语句"误报成高危 DROP。
    * **前半刀（从 upgrade 开始）**：跳过模块 docstring。``script.py.mako`` 的
      约定说明里写了 ``op.execute(sa.text("..."))`` 这行字面量，整文件 grep 会
      把它误数成一次原生 SQL 调用。
    """
    m_up = _UPGRADE_HEAD.search(text)
    if not m_up:
        return text
    m_down = _DOWNGRADE_HEAD.search(text, m_up.end())
    return text[m_up.end(): m_down.start() if m_down else len(text)]


def _summarize_revision_text(text: str) -> dict:
    body = _upgrade_body(text)

    counts: dict[str, int] = {}
    for name, pat in _OP_PATTERNS.items():
        n = len(re.findall(pat, body))
        if n:
            counts[name] = n

    tables: dict[str, list[str]] = {}
    for op_name in ("create_table", "add_column", "drop_column", "create_index", "create_unique_constraint"):
        found = re.findall(rf"op\.{op_name}\(\s*(?:op\.f\()?[\"']([^\"']+)[\"']", body)
        if found:
            tables[op_name] = sorted(set(found))

    # 索引「删除后又重建同名」= 定义变更（如补 unique、改列组合），不是丢结构
    dropped_idx = set(re.findall(r"op\.drop_index\(\s*(?:op\.f\()?[\"']([^\"']+)[\"']", body))
    created_idx = set(re.findall(r"op\.create_index\(\s*(?:op\.f\()?[\"']([^\"']+)[\"']", body))

    return {
        "counts": counts,
        "tables": tables,
        "redefined_indexes": sorted(dropped_idx & created_idx),
        "lost_indexes": sorted(dropped_idx - created_idx),
    }


def cmd_check(args: argparse.Namespace) -> int:
    from alembic import command
    from alembic.util import CommandError

    cfg = alembic_config()

    stale = _clean_stale_check_files()
    if stale:
        print(f"[i] 清理上次残留的临时文件：{[p.name for p in stale]}")

    print("=" * 62)
    print(" 漂移预览：ORM metadata  vs  真实数据库")
    print("=" * 62)
    print(" 说明：结果来自一次临时 autogenerate，**不会**落任何迁移文件。")
    print()

    try:
        command.revision(
            cfg,
            message="temp",
            autogenerate=True,
            rev_id=CHECK_TMP_REV_ID,
        )
    except CommandError as exc:
        print(f" [!] 无法生成对比：{exc}")
        _clean_stale_check_files()
        return 1

    try:
        files = sorted(VERSIONS_DIR.glob(f"*{CHECK_TMP_REV_ID}*"))
        if not files:
            print(" [!] 未找到临时 revision 文件，无法汇总。")
            return 1

        text = files[0].read_text(encoding="utf-8")
        summary = _summarize_revision_text(text)
        counts = summary["counts"]
        tables = summary["tables"]

        if not counts:
            print(" ✓ 无漂移：库结构与 ORM metadata 一致。")
            return 0

        print(" 按操作类型统计（仅 upgrade 段）：")
        for name in _OP_PATTERNS:
            if name in counts:
                if name in STRUCTURAL_DROPS:
                    flag = "   ⚠ 结构性删除"
                elif name == "drop_index":
                    flag = "   (多为索引重定义，见下)"
                else:
                    flag = ""
                print(f"   {name:<26} {counts[name]:>4}{flag}")

        if summary["redefined_indexes"]:
            print()
            print(f" 索引重定义（drop + 同名 create，属定义变更，非丢结构）"
                  f" {len(summary['redefined_indexes'])} 个：")
            for n in summary["redefined_indexes"]:
                print(f"   - {n}")

        if summary["lost_indexes"]:
            print()
            print(f" ⚠ 索引被删除且未重建 {len(summary['lost_indexes'])} 个：")
            for n in summary["lost_indexes"]:
                print(f"   - {n}")

        if tables:
            print()
            print(" 涉及的表：")
            for op_name, names in tables.items():
                shown = ", ".join(names[:10]) + (" …" if len(names) > 10 else "")
                print(f"   [{op_name}] ({len(names)}) {shown}")

        print()
        print("-" * 62)
        print(" 判读建议：")
        structural = {k: counts[k] for k in STRUCTURAL_DROPS if k in counts}
        if structural:
            print("  ✗✗ 出现**结构性删除**（丢表/丢列，数据不可逆）：")
            for k, v in structural.items():
                print(f"       {k} × {v}")
            print("      默认守卫（env.py include_object）本应拦截"
                  "「库中有、metadata 没有」的对象。此处仍有，")
            print("      说明 metadata 声明的对象与库中同名但不匹配（或已开启"
                  " ALEMBIC_ALLOW_DROP）。**必须逐条人工核对**。")
        else:
            print("  ✓ 无结构性删除（无 drop_table / drop_column），守卫工作正常。")

        print("  · 本项目 ORM 覆盖不全，TEXT↔String / BIGINT↔Integer / JSONB↔JSON")
        print("    等类型差异会产生大量「伪漂移」（体现在 alter_column 上），属预期。")
        print("  · 规范做法：**手写 revision**（op.add_column / op.create_table …），")
        print("    把 autogenerate 仅当作线索。详见 docs/database/Alembic_guide.md。")
        print("-" * 62)
        print()
        print(" 若要查看完整生成内容，可手动执行：")
        print('   alembic revision --autogenerate -m "draft"')
        print("   然后审阅 alembic/versions/ 下新文件，确认后删除草稿。")
        return 0
    finally:
        removed = _clean_stale_check_files()
        if removed:
            print(f"[i] 已删除临时文件：{[p.name for p in removed]}")


# ---------------------------------------------------------------------------
# 透传命令
# ---------------------------------------------------------------------------


def cmd_upgrade(args: argparse.Namespace) -> int:
    from alembic import command

    rev = args.revision or "head"
    print(f"即将执行：alembic upgrade {rev}")
    print(f"   目标库：{mask_url(load_db_url())}")
    if not confirm("确认执行？", args.yes):
        return 0
    command.upgrade(alembic_config(), rev)
    print("✓ upgrade 完成")
    return 0


def cmd_downgrade(args: argparse.Namespace) -> int:
    from alembic import command

    rev = args.revision or "-1"
    print(f"即将执行：alembic downgrade {rev}  （会撤销 schema 变更）")
    print(f"   目标库：{mask_url(load_db_url())}")
    if not confirm("确认执行？", args.yes):
        return 0
    command.downgrade(alembic_config(), rev)
    print("✓ downgrade 完成")
    return 0


def cmd_stamp(args: argparse.Namespace) -> int:
    from alembic import command

    rev = args.revision or "head"
    print(f"即将执行：alembic stamp {rev}  （只写版本账本，不执行任何 DDL）")
    print(f"   目标库：{mask_url(load_db_url())}")
    if not confirm("确认执行？", args.yes):
        return 0
    command.stamp(alembic_config(), rev)
    print("✓ stamp 完成（库结构未被触碰）")
    return 0


def cmd_revision(args: argparse.Namespace) -> int:
    from alembic import command

    if not args.message:
        raise SystemExit("[ERROR] revision 需要 -m/--message")

    if args.autogenerate:
        print("[!] --autogenerate 会依据 ORM metadata 与库的差异生成脚本。")
        print("    本项目存在已知的系统性类型差异，生成结果**必须逐条人工复核**。")
        print("    建议先跑：db_migrate.py check")

    command.revision(
        alembic_config(),
        message=args.message,
        autogenerate=args.autogenerate,
        rev_id=args.rev_id,
    )
    print("✓ revision 已生成，请检查 alembic/versions/ 下的新文件")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    from alembic import command

    command.history(alembic_config(), verbose=args.verbose)
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    """离线输出升级 SQL（不连库、不执行）。"""
    from alembic import command

    rev = args.revision or "head"
    print(f"-- 离线 SQL：upgrade {rev}（range 视当前版本而定，仅作审阅）", file=sys.stderr)
    command.upgrade(alembic_config(), rev, sql=True)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Alembic 便捷入口（股票分析系统）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # --yes 同时挂在顶层与各子命令下，`db_migrate.py -y upgrade` 与
    # `db_migrate.py upgrade -y` 都可用
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--yes", "-y", action="store_true", help="跳过交互确认")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="查看版本账本与库连接状态", parents=[common]).set_defaults(func=cmd_status)
    sub.add_parser("check", help="漂移预览（临时 autogenerate 汇总，不落文件）", parents=[common]).set_defaults(
        func=cmd_check
    )
    p = sub.add_parser("history", help="查看迁移历史", parents=[common])
    p.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("upgrade", help="升级到指定版本（默认 head）", parents=[common])
    p.add_argument("revision", nargs="?", default="head")
    p.set_defaults(func=cmd_upgrade)

    p = sub.add_parser("downgrade", help="回退（默认 -1，即撤销一步）", parents=[common])
    p.add_argument("revision", nargs="?", default="-1")
    p.set_defaults(func=cmd_downgrade)

    p = sub.add_parser("stamp", help="只写版本账本，不执行 DDL（默认 head）", parents=[common])
    p.add_argument("revision", nargs="?", default="head")
    p.set_defaults(func=cmd_stamp)

    p = sub.add_parser("revision", help="生成新迁移脚本", parents=[common])
    p.add_argument("-m", "--message", required=True, help="变更说明")
    p.add_argument("--autogenerate", action="store_true", help="自动比对生成（需人工复核）")
    p.add_argument("--rev-id", default=None, help="自定义 revision id")
    p.set_defaults(func=cmd_revision)

    p = sub.add_parser("sql", help="离线输出升级 SQL（不连库、不执行）", parents=[common])
    p.add_argument("revision", nargs="?", default="head")
    p.set_defaults(func=cmd_sql)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 顶层未提供 --yes 时兜底
    if not hasattr(args, "yes"):
        args.yes = False

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    # 抑制 import 期噪声：保证含口令的连接串不外泄
    raise SystemExit(main())
