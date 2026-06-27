"""
行业板块基本信息 + 成分股：导出/导入生产环境。

数据库连接与 migrations 其它脚本一致，默认使用 backend_core.database.db.engine（读取项目根 .env 的 DB_*）。

用法：
  # 开发机：从当前 .env 库导出
  python migrations/sync_industry_board_to_production.py --dump industry_board_sync.json

  # 生产机：导入到当前 .env 指向的库
  python migrations/sync_industry_board_to_production.py --load industry_board_sync.json

  # 双库直连（可选 TARGET_DATABASE_URL 或 --target-url）
  python migrations/sync_industry_board_to_production.py --target-url postgresql+psycopg2://...

默认 upsert；--mode replace 先清空再写入（需 --yes）。
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
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE_BASIC = "industry_board_basic_info"
TABLE_CONST = "industry_board_constituents"


def _mask_db_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r":([^:@/]+)@", r":***@", url)


def _engine_url(eng: Engine) -> str:
    try:
        return str(eng.url)
    except Exception:
        return ""


def get_target_engine(explicit_url: Optional[str] = None) -> Engine:
    """目标库：显式 URL / TARGET_DATABASE_URL；否则与 migrations 相同用默认 engine。"""
    url = (explicit_url or os.getenv("TARGET_DATABASE_URL") or "").strip()
    if url:
        return create_engine(url, pool_pre_ping=True)
    return engine


def ensure_target_schema(conn) -> None:
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
    return [
        {
            "board_code": str(r[0]).strip(),
            "board_name": r[1],
            "create_date": _serialize_value(r[2]),
            "trade_observe_flag": bool(r[3]) if r[3] is not None else False,
        }
        for r in rows
    ]


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


def dump_to_file(path: Path, src_engine: Engine | None = None, batch_size: int = 2000) -> Dict[str, int]:
    eng = src_engine or engine
    stats = {"basic": 0, "constituents": 0}
    payload: Dict[str, Any] = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "basic": [],
        "constituents": [],
    }
    logger.info("源库: %s", _mask_db_url(_engine_url(eng)))
    with eng.connect() as conn:
        payload["basic"] = load_basic_rows(conn)
        stats["basic"] = len(payload["basic"])
        for batch in iter_constituent_rows(conn, batch_size=batch_size):
            payload["constituents"].extend(batch)
        stats["constituents"] = len(payload["constituents"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已导出到 %s（basic=%s, constituents=%s）", path, stats["basic"], stats["constituents"])
    return stats


def load_from_file(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("basic") or [], data.get("constituents") or []


def sync_to_target(
    tgt_engine: Engine,
    basic_rows: List[Dict[str, Any]],
    constituent_rows: Union[List[Dict[str, Any]], Iterable[List[Dict[str, Any]]]],
    *,
    dry_run: bool,
    replace: bool,
    batch_size: int,
) -> Dict[str, int]:
    stats = {"basic_upserted": 0, "constituents_upserted": 0}
    logger.info("目标库: %s", _mask_db_url(_engine_url(tgt_engine)))
    with tgt_engine.connect() as conn:
        ensure_target_schema(conn)
        if replace and not dry_run:
            truncate_target_tables(conn)
            logger.warning("已清空目标库 %s / %s", TABLE_BASIC, TABLE_CONST)
        stats["basic_upserted"] = upsert_basic_rows(conn, basic_rows, dry_run)
        if isinstance(constituent_rows, list):
            for i in range(0, len(constituent_rows), batch_size):
                stats["constituents_upserted"] += upsert_constituent_batch(
                    conn, constituent_rows[i : i + batch_size], dry_run
                )
        else:
            for batch in constituent_rows:
                stats["constituents_upserted"] += upsert_constituent_batch(conn, batch, dry_run)
        if not dry_run:
            conn.commit()
    return stats


def run_direct_sync(
    target_url: Optional[str],
    *,
    dry_run: bool,
    replace: bool,
    batch_size: int,
) -> Dict[str, int]:
    tgt_engine = get_target_engine(target_url)
    src_url = _engine_url(engine)
    tgt_url = _engine_url(tgt_engine)
    if src_url and tgt_url and src_url == tgt_url:
        logger.error("源库与目标库相同，已拒绝执行")
        raise ValueError("源库与目标库相同")

    logger.info("源库: %s", _mask_db_url(src_url))
    with engine.connect() as src:
        basic_rows = load_basic_rows(src)
        cons_total = count_constituents(src)
        logger.info("源库统计: basic=%s, constituents=%s", len(basic_rows), cons_total)

    def _const_iter() -> Iterator[List[Dict[str, Any]]]:
        with engine.connect() as src:
            yield from iter_constituent_rows(src, batch_size=batch_size)

    return sync_to_target(
        tgt_engine,
        basic_rows,
        _const_iter(),
        dry_run=dry_run,
        replace=replace,
        batch_size=batch_size,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="行业板块 basic + 成分股 迁移（默认使用 .env 数据库）")
    p.add_argument("--target-url", help="目标库 URL（可选；不设则用 engine，双库同步时必填或使用 TARGET_DATABASE_URL）")
    p.add_argument("--dump", metavar="FILE", help="从当前 .env 库导出 JSON")
    p.add_argument("--load", metavar="FILE", help="导入 JSON 到目标库（默认当前 .env 库）")
    p.add_argument("--mode", choices=("upsert", "replace"), default="upsert")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--batch-size", type=int, default=2000)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    replace = args.mode == "replace"

    if args.dump and args.load:
        logger.error("不能同时指定 --dump 与 --load")
        return 2

    if replace and not args.dry_run and not args.yes and args.load:
        ans = input("replace 模式将清空行业板块表，确认继续？[yes/N]: ").strip().lower()
        if ans not in ("yes", "y"):
            logger.info("已取消")
            return 0

    try:
        if args.dump:
            dump_to_file(Path(args.dump), batch_size=args.batch_size)
            return 0

        if args.load:
            basic, constituents = load_from_file(Path(args.load))
            logger.info("JSON: basic=%s, constituents=%s", len(basic), len(constituents))
            stats = sync_to_target(
                get_target_engine(args.target_url),
                basic,
                constituents,
                dry_run=args.dry_run,
                replace=replace,
                batch_size=args.batch_size,
            )
            logger.info("导入完成: %s", stats)
            return 0

        if not args.target_url and not os.getenv("TARGET_DATABASE_URL"):
            logger.error("双库同步请设置 TARGET_DATABASE_URL 或 --target-url")
            return 2

        stats = run_direct_sync(
            args.target_url,
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
