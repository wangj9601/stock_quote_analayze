#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行业板块基本信息 + 成分股：开发/测试库 → 生产库 迁移脚本。

支持两种用法：
1) 直连双库同步（推荐内网可互访时）：
   set SOURCE_DATABASE_URL=postgresql+psycopg2://user:pass@dev-host:5432/stock_analysis
   set TARGET_DATABASE_URL=postgresql+psycopg2://user:pass@prod-host:5432/stock_analysis
   python manual_scripts/sync_industry_board_to_production.py

2) 导出文件后在生产机导入（生产库不可从开发机直连时）：
   python manual_scripts/sync_industry_board_to_production.py --dump industry_board_sync.json
   # 将 JSON 拷到生产机后：
   python manual_scripts/sync_industry_board_to_production.py --load industry_board_sync.json --target-url %TARGET_DATABASE_URL%

默认模式 upsert（ON CONFLICT 更新）；--replace 会先清空生产侧两张表再写入（需 --yes）。

迁移前请在目标库执行（若尚未执行）：
   python migrations/add_industry_board_constituents.py
   python migrations/add_board_trade_observe_flag.py
   python migrations/normalize_industry_board_codes.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TABLE_BASIC = "industry_board_basic_info"
TABLE_CONST = "industry_board_constituents"
BASIC_COLS = ("board_code", "board_name", "create_date", "trade_observe_flag")
CONST_COLS = ("board_code", "stock_code", "stock_name", "updated_at")


def _mask_db_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r":([^:@/]+)@", r":***@", url)


def _resolve_url(explicit: Optional[str], env_key: str, fallback_env: str = "DATABASE_URL") -> str:
    u = (explicit or os.getenv(env_key) or "").strip()
    if u:
        return u
    if env_key != fallback_env:
        u = (os.getenv(fallback_env) or "").strip()
    if not u:
        raise ValueError(
            f"缺少数据库 URL：请传 --{env_key.lower().replace('_database_url', '')}-url "
            f"或设置环境变量 {env_key}（源库可回退 {fallback_env}）"
        )
    return u


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, future=True)


def ensure_target_schema(conn) -> None:
    """确保目标库存在行业板块表及 trade_observe_flag 列。"""
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_BASIC} (
                board_code VARCHAR(20) PRIMARY KEY,
                board_name VARCHAR(100),
                create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE {TABLE_BASIC}
            ADD COLUMN IF NOT EXISTS trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_CONST} (
                board_code VARCHAR(20) NOT NULL,
                stock_code VARCHAR(20) NOT NULL,
                stock_name VARCHAR(100),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                PRIMARY KEY (board_code, stock_code)
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_stock_code
            ON {TABLE_CONST} (stock_code)
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_board_code
            ON {TABLE_CONST} (board_code)
            """
        )
    )


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, bool):
        return v
    return v


def _parse_ts(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt[: len(s) if len(s) < 19 else 19])
        except ValueError:
            continue
    return s


def load_basic_rows(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            f"""
            SELECT board_code, board_name, create_date, trade_observe_flag
            FROM {TABLE_BASIC}
            ORDER BY board_code
            """
        )
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "board_code": str(r[0]).strip(),
                "board_name": r[1],
                "create_date": _serialize_value(r[2]),
                "trade_observe_flag": bool(r[3]) if r[3] is not None else False,
            }
        )
    return out


def iter_constituent_rows(conn, batch_size: int = 2000) -> Iterator[List[Dict[str, Any]]]:
    offset = 0
    while True:
        chunk = conn.execute(
            text(
                f"""
                SELECT board_code, stock_code, stock_name, updated_at
                FROM {TABLE_CONST}
                ORDER BY board_code, stock_code
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": batch_size, "offset": offset},
        ).fetchall()
        if not chunk:
            break
        batch = [
            {
                "board_code": str(r[0]).strip(),
                "stock_code": str(r[1]).strip(),
                "stock_name": r[2],
                "updated_at": _serialize_value(r[3]),
            }
            for r in chunk
        ]
        yield batch
        offset += len(chunk)
        if len(chunk) < batch_size:
            break


def count_constituents(conn) -> int:
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_CONST}")).scalar() or 0)


def truncate_target_tables(conn) -> None:
    conn.execute(text(f"TRUNCATE TABLE {TABLE_CONST}"))
    conn.execute(text(f"DELETE FROM {TABLE_BASIC}"))


def upsert_basic_rows(conn, rows: Iterable[Dict[str, Any]], dry_run: bool) -> int:
    n = 0
    for row in rows:
        n += 1
        if dry_run:
            continue
        conn.execute(
            text(
                f"""
                INSERT INTO {TABLE_BASIC}
                    (board_code, board_name, create_date, trade_observe_flag)
                VALUES
                    (:board_code, :board_name, :create_date, :trade_observe_flag)
                ON CONFLICT (board_code) DO UPDATE SET
                    board_name = EXCLUDED.board_name,
                    create_date = COALESCE(EXCLUDED.create_date, {TABLE_BASIC}.create_date),
                    trade_observe_flag = EXCLUDED.trade_observe_flag
                """
            ),
            {
                "board_code": row["board_code"],
                "board_name": row.get("board_name"),
                "create_date": _parse_ts(row.get("create_date")),
                "trade_observe_flag": bool(row.get("trade_observe_flag", False)),
            },
        )
    return n


def upsert_constituent_batch(conn, batch: List[Dict[str, Any]], dry_run: bool) -> int:
    if dry_run or not batch:
        return len(batch)
    for row in batch:
        conn.execute(
            text(
                f"""
                INSERT INTO {TABLE_CONST}
                    (board_code, stock_code, stock_name, updated_at)
                VALUES
                    (:board_code, :stock_code, :stock_name, COALESCE(:updated_at, NOW()))
                ON CONFLICT (board_code, stock_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "board_code": row["board_code"],
                "stock_code": row["stock_code"],
                "stock_name": row.get("stock_name"),
                "updated_at": _parse_ts(row.get("updated_at")),
            },
        )
    return len(batch)


def dump_to_file(path: Path, source_engine: Engine, batch_size: int) -> Dict[str, int]:
    stats = {"basic": 0, "constituents": 0}
    payload: Dict[str, Any] = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "basic": [],
        "constituents": [],
    }
    with source_engine.connect() as src:
        payload["basic"] = load_basic_rows(src)
        stats["basic"] = len(payload["basic"])
        for batch in iter_constituent_rows(src, batch_size=batch_size):
            payload["constituents"].extend(batch)
        stats["constituents"] = len(payload["constituents"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已导出到 %s（basic=%s, constituents=%s）", path, stats["basic"], stats["constituents"])
    return stats


def load_from_file(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    basic = data.get("basic") or []
    constituents = data.get("constituents") or []
    return basic, constituents


def sync_to_target(
    target_engine: Engine,
    basic_rows: List[Dict[str, Any]],
    constituent_rows: Iterable[List[Dict[str, Any]]],
    *,
    dry_run: bool,
    replace: bool,
    batch_size: int,
) -> Dict[str, int]:
    stats = {"basic_upserted": 0, "constituents_upserted": 0}
    with target_engine.begin() as tgt:
        ensure_target_schema(tgt)
        if replace and not dry_run:
            truncate_target_tables(tgt)
            logger.warning("已清空目标库 %s / %s", TABLE_BASIC, TABLE_CONST)
        stats["basic_upserted"] = upsert_basic_rows(tgt, basic_rows, dry_run)
        if isinstance(constituent_rows, list):
            for i in range(0, len(constituent_rows), batch_size):
                batch = constituent_rows[i : i + batch_size]
                stats["constituents_upserted"] += upsert_constituent_batch(tgt, batch, dry_run)
        else:
            for batch in constituent_rows:
                stats["constituents_upserted"] += upsert_constituent_batch(tgt, batch, dry_run)
    return stats


def run_direct_sync(
    source_url: str,
    target_url: str,
    *,
    dry_run: bool,
    replace: bool,
    batch_size: int,
) -> Dict[str, int]:
    src_engine = make_engine(source_url)
    tgt_engine = make_engine(target_url)
    logger.info("源库: %s", _mask_db_url(source_url))
    logger.info("目标库: %s", _mask_db_url(target_url))

    with src_engine.connect() as src:
        basic_rows = load_basic_rows(src)
        cons_total = count_constituents(src)
        logger.info("源库统计: basic=%s, constituents=%s", len(basic_rows), cons_total)

    def _const_iter() -> Iterator[List[Dict[str, Any]]]:
        with src_engine.connect() as src:
            yield from iter_constituent_rows(src, batch_size=batch_size)

    stats = sync_to_target(
        tgt_engine,
        basic_rows,
        _const_iter(),
        dry_run=dry_run,
        replace=replace,
        batch_size=batch_size,
    )
    return stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="行业板块 basic + 成分股 迁移到生产环境（直连或 JSON 文件）",
    )
    p.add_argument("--source-url", help="源库 DATABASE_URL（默认 SOURCE_DATABASE_URL 或 .env DATABASE_URL）")
    p.add_argument("--target-url", help="目标库 URL（默认 TARGET_DATABASE_URL）")
    p.add_argument("--dump", metavar="FILE", help="仅从源库导出 JSON，不写入目标库")
    p.add_argument("--load", metavar="FILE", help="从 JSON 导入目标库（需 --target-url）")
    p.add_argument(
        "--mode",
        choices=("upsert", "replace"),
        default="upsert",
        help="upsert=合并更新；replace=先清空目标表再写入",
    )
    p.add_argument("--dry-run", action="store_true", help="只统计，不写入目标库")
    p.add_argument("--yes", action="store_true", help="replace 模式跳过交互确认")
    p.add_argument("--batch-size", type=int, default=2000, help="成分股分批大小")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    replace = args.mode == "replace"

    if args.dump and args.load:
        logger.error("不能同时指定 --dump 与 --load")
        return 2

    if replace and not args.dry_run and not args.yes:
        ans = input("replace 模式将清空生产库行业板块表，确认继续？[yes/N]: ").strip().lower()
        if ans not in ("yes", "y"):
            logger.info("已取消")
            return 0

    try:
        if args.dump:
            source_url = _resolve_url(args.source_url, "SOURCE_DATABASE_URL")
            dump_path = Path(args.dump)
            dump_to_file(dump_path, make_engine(source_url), args.batch_size)
            return 0

        if args.load:
            target_url = _resolve_url(args.target_url, "TARGET_DATABASE_URL")
            basic, constituents = load_from_file(Path(args.load))
            logger.info("JSON: basic=%s, constituents=%s", len(basic), len(constituents))
            stats = sync_to_target(
                make_engine(target_url),
                basic,
                constituents,
                dry_run=args.dry_run,
                replace=replace,
                batch_size=args.batch_size,
            )
            logger.info("导入完成: %s", stats)
            return 0

        source_url = _resolve_url(args.source_url, "SOURCE_DATABASE_URL")
        target_url = _resolve_url(args.target_url, "TARGET_DATABASE_URL")
        if source_url == target_url:
            logger.error("源库与目标库 URL 相同，已拒绝执行")
            return 2

        stats = run_direct_sync(
            source_url,
            target_url,
            dry_run=args.dry_run,
            replace=replace,
            batch_size=args.batch_size,
        )
        logger.info("同步完成: %s", stats)
        return 0
    except Exception as e:
        logger.exception("迁移失败: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
