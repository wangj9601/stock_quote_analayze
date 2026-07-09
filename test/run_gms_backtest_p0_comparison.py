#!/usr/bin/env python3
"""
批量创建 GMS 交易回测 P0 三组对比任务。

配置见同目录 gms_backtest_p0_comparison_tasks.json。

用法:
  python test/run_gms_backtest_p0_comparison.py --dry-run
  python test/run_gms_backtest_p0_comparison.py
  python test/run_gms_backtest_p0_comparison.py --pool custom --codes 562500,688001,688002,688006,688008
  python test/run_gms_backtest_p0_comparison.py --export-dir reports

说明:
  命令行默认 **同步执行** 回测（脚本进程内跑完）。若用 --async，仅投递线程任务，
  脚本退出后 daemon 线程会被终止，任务会长期停留在 pending，且不会生成 Excel。
  Excel 在任务 completed 后，于管理端「报告分析」点「下载明细」，或用 --export-dir 导出。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

CONFIG_PATH = Path(__file__).resolve().parent / "gms_backtest_p0_comparison_tasks.json"


def _load_spec() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _resolve_stock_pool(
    db,
    *,
    mode: str,
    market: str,
    cn_seg: str | None,
    custom_codes: List[str] | None,
) -> List[str]:
    from backend_api.admin.gms_admin_routes import (
        _apply_backtest_cn_board_segment,
        _distinct_gms_strategy_stock_codes,
        _normalize_backtest_cn_board_segment,
    )

    mkt = (market or "cn").strip().lower()
    seg = _normalize_backtest_cn_board_segment(cn_seg) if cn_seg else None

    if mode == "gms_watchlist":
        codes = _distinct_gms_strategy_stock_codes(db, market=market)
        if not codes:
            raise RuntimeError("GMS观察股池为空，请先在管理端维护观察股")
        return _apply_backtest_cn_board_segment(codes, mkt, seg) or []

    if mode == "custom":
        if not custom_codes:
            raise RuntimeError("custom 模式需通过 --codes 传入股票列表")
        pool = [str(c).strip() for c in custom_codes if str(c).strip()]
        return _apply_backtest_cn_board_segment(pool, mkt, seg) or []

    raise RuntimeError(f"不支持的 stock_pool_mode: {mode}")


def build_task_configs(
    spec: Dict[str, Any],
    *,
    pool_mode: str,
    custom_codes: List[str] | None,
) -> List[Dict[str, Any]]:
    base = deepcopy(spec["base"])
    pool_mode = pool_mode or base.get("stock_pool_mode") or "gms_watchlist"
    base["stock_pool_mode"] = pool_mode

    configs: List[Dict[str, Any]] = []
    for variant in spec["variants"]:
        cfg = deepcopy(base)
        cfg.update({k: v for k, v in variant.items() if k not in ("key",)})
        cfg["task_name"] = variant["task_name"]
        cfg["_variant_key"] = variant["key"]
        cfg["_custom_codes"] = custom_codes
        configs.append(cfg)
    return configs


def _export_report_xlsx(task_id: str, export_dir: Path) -> Optional[Path]:
    from backend_core.strategies.gms import admin_interface

    payload = admin_interface.download_report(task_id, variant="xlsx")
    if not payload:
        return None
    data, filename, _ctype = payload
    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / filename
    out.write_bytes(data)
    return out


def _execute_task(task_id: str, *, sync: bool) -> None:
    from backend_core.strategies.gms import admin_interface, backtest_worker

    if sync:
        backtest_worker._run_task(task_id)
        task = admin_interface.get_task(task_id) or {}
        if task.get("status") != "completed":
            raise RuntimeError(
                f"任务未成功完成: {task_id}, status={task.get('status')}, error={task.get('error')}"
            )
        return
    backtest_worker.start_backtest(task_id)


def _create_task_config(raw: Dict[str, Any], pool_mode: str) -> tuple[str, str]:
    from backend_api.database import SessionLocal
    from backend_core.strategies.gms import admin_interface, backtest_storage

    db = SessionLocal()
    try:
        cfg = deepcopy(raw)
        variant_key = cfg.pop("_variant_key", "")
        custom = cfg.pop("_custom_codes", None)
        codes = _resolve_stock_pool(
            db,
            mode=pool_mode,
            market=cfg.get("market", "cn"),
            cn_seg=cfg.get("cn_board_segment"),
            custom_codes=custom,
        )
        if not codes:
            raise RuntimeError(f"股票池解析结果为空（variant={variant_key}）")
        cfg["stock_pool"] = codes
        task_name = cfg.pop("task_name", None)
        task_id = backtest_storage.create_task(cfg, name=task_name)
        return task_id, task_name or ""
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 GMS P0 对比回测任务")
    parser.add_argument("--dry-run", action="store_true", help="仅打印任务配置，不提交")
    parser.add_argument(
        "--async",
        dest="run_async",
        action="store_true",
        help="异步投递（需长期运行的后端进程；命令行单独执行请勿用）",
    )
    parser.add_argument(
        "--export-dir",
        default="",
        help="任务完成后将 xlsx 导出到该目录（如 reports）",
    )
    parser.add_argument(
        "--pool",
        choices=["gms_watchlist", "custom"],
        default=None,
        help="覆盖配置中的股票池模式",
    )
    parser.add_argument(
        "--codes",
        default="",
        help="custom 模式股票代码，逗号分隔，如 562500,688001,688008",
    )
    args = parser.parse_args()

    spec = _load_spec()
    custom_codes = [c.strip() for c in args.codes.split(",") if c.strip()] or None
    pool_mode = args.pool or spec["base"].get("stock_pool_mode") or "gms_watchlist"
    task_cfgs = build_task_configs(spec, pool_mode=pool_mode, custom_codes=custom_codes)

    if args.dry_run:
        print(json.dumps(task_cfgs, ensure_ascii=False, indent=2))
        return 0

    sync = not args.run_async
    export_dir = Path(args.export_dir) if args.export_dir else None
    created: List[Dict[str, str]] = []

    for raw in task_cfgs:
        task_id, task_name = _create_task_config(raw, pool_mode)
        print(f"[创建] {task_name} -> {task_id}")
        if sync:
            print(f"[执行] 同步回测中…")
            _execute_task(task_id, sync=True)
            status_msg = "completed"
            if export_dir:
                xlsx = _export_report_xlsx(task_id, export_dir)
                if xlsx:
                    print(f"[导出] {xlsx}")
        else:
            from backend_core.strategies.gms import backtest_worker

            backtest_worker.start_backtest(task_id)
            status_msg = "pending(异步)"
        created.append({"variant": raw.get("_variant_key", ""), "task_id": task_id, "task_name": task_name, "status": status_msg})
        print(f"[OK] {task_name} ({status_msg})")

    print("\n已处理任务:")
    for row in created:
        print(f"  - {row['task_name']}: {row['task_id']} [{row['status']}]")
    if not sync:
        print("\n提示: 使用了 --async，请在管理端等待任务完成，或改用同步模式（默认）。")
    if sync and not export_dir:
        print("\n提示: Excel 可在管理端「GMS 回测 → 报告分析 → 下载明细」获取，或加 --export-dir reports 自动导出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
