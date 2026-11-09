#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重跑 CSB（通道突破）信号预计算，写入 ``csb_signal_trace``。

同步执行（阻塞到结束），口径与日终 ``csb_signals_cn`` / 管理端预计算一致：
只写买点且 ``score≥入库地板分``（默认 50，可用环境变量 ``CSB_PRECOMPUTE_MIN_SCORE``）。

用法（在项目根目录）::

    # 最新交易日，所有「默认或已开预计算」的启用版本
    python scripts/rerun_csb_precompute.py

    # 指定单日
    python scripts/rerun_csb_precompute.py --date 2026-11-06

    # 指定参数版本；先删当日旧 trace 再全市场重算（推荐规则变更后使用）
    python scripts/rerun_csb_precompute.py --date 2026-11-06 --config-id 1 --purge-first

    # 区间补算（一次拉行情按日评点，更快）
    python scripts/rerun_csb_precompute.py --start 2026-11-01 --end 2026-11-06 --purge-first

    # 调试：只扫前 N 只股票
    python scripts/rerun_csb_precompute.py --date 2026-11-06 --limit 200

    # 仅列出将参与的配置，不计算
    python scripts/rerun_csb_precompute.py --list-configs
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("rerun_csb_precompute")


def _parse_ymd(s: str) -> str:
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    raise argparse.ArgumentTypeError(f"日期格式无效: {s!r}，请用 YYYY-MM-DD 或 YYYYMMDD")


def _resolve_config_ids(
    *,
    config_id: Optional[int],
    all_active: bool,
) -> List[int]:
    from backend_api.database import SessionLocal
    from backend_api.models import CSBStrategyConfig
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.scheduled_precompute import list_precompute_config_ids

    db = SessionLocal()
    try:
        CSBConfigManager().ensure_default_row(db)
        if config_id is not None:
            row = (
                db.query(CSBStrategyConfig.id)
                .filter(CSBStrategyConfig.id == int(config_id))
                .first()
            )
            if not row:
                raise SystemExit(f"找不到 CSB 参数版本 config_id={config_id}")
            return [int(config_id)]
        if all_active:
            rows = (
                db.query(CSBStrategyConfig.id)
                .filter(CSBStrategyConfig.is_active.is_(True))
                .order_by(CSBStrategyConfig.id.asc())
                .all()
            )
            return [int(r[0]) for r in rows]
        return list_precompute_config_ids(db)
    finally:
        db.close()


def _list_configs() -> None:
    from backend_api.database import SessionLocal
    from backend_api.models import CSBStrategyConfig
    from backend_core.strategies.csb.config import CSBConfigManager
    from backend_core.strategies.csb.scheduled_precompute import (
        list_precompute_config_ids,
        resolve_csb_precompute_storage_min_score,
    )

    db = SessionLocal()
    try:
        cm = CSBConfigManager()
        cm.ensure_default_row(db)
        pre_ids = set(list_precompute_config_ids(db))
        rows = db.query(CSBStrategyConfig).order_by(CSBStrategyConfig.id.asc()).all()
        print("id\tactive\tdefault\tprecompute\tname\tmin_score\tstorage_floor")
        for r in rows:
            cfg = cm.get_config(int(r.id), db=db)
            flag = "Y" if int(r.id) in pre_ids else ""
            print(
                f"{r.id}\t{bool(r.is_active)}\t{bool(r.is_default)}\t"
                f"{bool(r.precompute_enabled)}/{flag}\t{r.name or ''}\t"
                f"{cfg.get('min_score')}\t{resolve_csb_precompute_storage_min_score(cfg)}"
            )
        print("说明: precompute 列 = 配置开关 / 是否纳入默认日终集合(Y)")
    finally:
        db.close()


def _purge_day(config_id: int, trade_date: str) -> int:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.trace_store import delete_trace_for_config_in_range

    db = SessionLocal()
    try:
        n = delete_trace_for_config_in_range(
            db,
            config_id=int(config_id),
            start_date=str(trade_date)[:10],
            end_date=str(trade_date)[:10],
        )
        logger.info("已删除 config_id=%s %s 区间内旧 trace %s 行", config_id, trade_date, n)
        return int(n or 0)
    finally:
        db.close()


def _resolve_effective_date(trade_date: Optional[str]) -> str:
    from backend_api.database import SessionLocal
    from backend_core.strategies.csb.data_loader import CSBDataLoader
    from backend_core.strategies.csb.scheduled_precompute import resolve_csb_trade_date

    db = SessionLocal()
    try:
        loader = CSBDataLoader(db)
        date_s = trade_date or resolve_csb_trade_date(db)
        return loader.resolve_effective_trade_date(date_s)
    finally:
        db.close()


def _run_single_day(
    config_ids: List[int],
    *,
    trade_date: Optional[str],
    limit: Optional[int],
    purge_first: bool,
) -> int:
    from backend_core.strategies.csb.scheduled_precompute import run_csb_precompute_for_config

    date_s = _resolve_effective_date(trade_date)
    logger.info("单日有效交易日=%s", date_s)
    failed = 0
    for cid in config_ids:
        if purge_first:
            _purge_day(cid, date_s)
        t0 = time.time()
        out = run_csb_precompute_for_config(
            cid, trade_date=date_s, limit=limit
        )
        ok = bool(out.get("success"))
        if not ok:
            failed += 1
        logger.info(
            "单日结果 config_id=%s success=%s date=%s hits=%s written=%s "
            "floor=%s selection=%s elapsed=%.1fs err=%s",
            cid,
            ok,
            out.get("trade_date"),
            out.get("hits"),
            out.get("written"),
            out.get("storage_min_score"),
            out.get("selection_min_score"),
            time.time() - t0,
            out.get("error"),
        )
    return failed


def _run_range(
    config_ids: List[int],
    *,
    start: str,
    end: str,
    purge_first: bool,
) -> int:
    from backend_core.strategies.csb.scheduled_precompute import (
        begin_csb_trace_refresh_status,
        run_csb_trace_refresh_range,
    )

    failed = 0
    for cid in config_ids:
        status, already = begin_csb_trace_refresh_status(
            cid, start_date=start, end_date=end, purge_first=purge_first
        )
        if already:
            logger.error(
                "config_id=%s 区间刷新仍在运行（同进程），跳过。status=%s",
                cid,
                status,
            )
            failed += 1
            continue
        t0 = time.time()
        out = run_csb_trace_refresh_range(
            cid,
            start_date=start,
            end_date=end,
            purge_first=purge_first,
        )
        ok = bool(out.get("success"))
        if not ok:
            failed += 1
        logger.info(
            "区间结果 config_id=%s success=%s %s~%s purged=%s days=%s hits=%s "
            "elapsed=%.1fs err=%s",
            cid,
            ok,
            start,
            end,
            out.get("purged_rows"),
            out.get("precomputed_days"),
            out.get("precompute_hits"),
            time.time() - t0,
            out.get("error"),
        )
    return failed


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="重跑 CSB 信号预计算（写入 csb_signal_trace）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--date", type=_parse_ymd, help="单日 YYYY-MM-DD；空则行情最新日")
    p.add_argument("--start", type=_parse_ymd, help="区间起始（含）")
    p.add_argument("--end", type=_parse_ymd, help="区间结束（含）")
    p.add_argument("--config-id", type=int, help="只跑指定参数版本；空则跑日终覆盖集合")
    p.add_argument(
        "--all-active",
        action="store_true",
        help="跑全部 is_active 版本（不仅默认/预计算开关）",
    )
    p.add_argument(
        "--purge-first",
        action="store_true",
        help="先删除目标日期/区间内旧 trace 再重算（规则变更后建议打开）",
    )
    p.add_argument("--limit", type=int, help="候选股上限（仅单日模式，调试用）")
    p.add_argument("--list-configs", action="store_true", help="列出参数版本后退出")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_configs:
        _list_configs()
        return 0

    if (args.start and not args.end) or (args.end and not args.start):
        logger.error("--start 与 --end 需同时提供")
        return 2
    if args.date and (args.start or args.end):
        logger.error("--date 与 --start/--end 不要同时使用")
        return 2
    if args.limit is not None and args.limit <= 0:
        logger.error("--limit 须为正整数")
        return 2
    if args.limit is not None and args.start:
        logger.error("--limit 仅支持单日模式，区间请去掉 --limit")
        return 2

    try:
        config_ids = _resolve_config_ids(
            config_id=args.config_id, all_active=bool(args.all_active)
        )
    except SystemExit as e:
        logger.error("%s", e)
        return 2

    if not config_ids:
        logger.error("没有可运行的 CSB 参数版本（检查 is_active / is_default / precompute_enabled）")
        return 2

    mode = "range" if args.start else "single"
    start_s = args.start
    end_s = args.end
    date_s = args.date

    logger.info(
        "计划: mode=%s configs=%s date=%s range=%s~%s purge_first=%s limit=%s",
        mode,
        config_ids,
        date_s or "(latest)",
        start_s,
        end_s,
        bool(args.purge_first),
        args.limit,
    )
    if args.dry_run:
        logger.info("dry-run，退出")
        return 0

    t0 = time.time()
    if mode == "range":
        assert start_s and end_s
        if start_s > end_s:
            logger.error("start_date 不能晚于 end_date")
            return 2
        failed = _run_range(
            config_ids,
            start=start_s,
            end=end_s,
            purge_first=bool(args.purge_first),
        )
    else:
        failed = _run_single_day(
            config_ids,
            trade_date=date_s,
            limit=args.limit,
            purge_first=bool(args.purge_first),
        )

    logger.info("全部结束 elapsed=%.1fs failed=%s", time.time() - t0, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
