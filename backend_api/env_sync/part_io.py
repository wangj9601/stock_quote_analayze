# -*- coding: utf-8 -*-
"""环境同步分片：按日导出并写入 gzip JSON。"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend_api.env_sync import needs_date_range
from backend_api.env_sync.artifacts import write_manifest
from backend_api.env_sync.services import export_modules, normalize_modules


def max_job_parts() -> int:
    try:
        return max(1, int(os.getenv("ENV_SYNC_JOB_MAX_PARTS") or "400"))
    except ValueError:
        return 400


def job_row_chunk() -> int:
    try:
        return max(50, int(os.getenv("ENV_SYNC_JOB_ROW_CHUNK") or "2000"))
    except ValueError:
        return 2000


def _parse_day(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()


def _iter_days(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_part_json(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    with gzip.open(path, "wb") as gz:
        gz.write(raw)
    return sha256_file(path)


def read_part_json(path: Path) -> Dict[str, Any]:
    with gzip.open(path, "rb") as gz:
        return json.loads(gz.read().decode("utf-8"))


def _count_rows(bundles: Dict[str, Any]) -> int:
    n = 0
    for b in (bundles or {}).values():
        items = (b or {}).get("items") or {}
        for v in items.values():
            if isinstance(v, list):
                n += len(v)
    return n


def _split_bundle_by_rows(
    bundle_key: str,
    bundle: Dict[str, Any],
    *,
    chunk_rows: int,
) -> List[Dict[str, Any]]:
    """若单 bundle 行数过大，按 items 中最大 list 切开。"""
    items = (bundle or {}).get("items") or {}
    if not items:
        return [bundle]
    # 找最大 list
    best_k = None
    best_n = 0
    for k, v in items.items():
        if isinstance(v, list) and len(v) > best_n:
            best_k, best_n = k, len(v)
    if best_k is None or best_n <= chunk_rows:
        return [bundle]
    out: List[Dict[str, Any]] = []
    rows = items[best_k]
    for i in range(0, len(rows), chunk_rows):
        part_items = dict(items)
        part_items[best_k] = rows[i : i + chunk_rows]
        # 其它 list 字段仅在第一片保留，避免重复放大；配置类通常单 list
        if i > 0:
            for k, v in list(part_items.items()):
                if k != best_k and isinstance(v, list):
                    part_items[k] = []
        nb = dict(bundle)
        nb["items"] = part_items
        out.append(nb)
    return out


def build_export_parts(
    db: Session,
    modules: Optional[Sequence[str]],
    *,
    start_date: Optional[str],
    end_date: Optional[str],
    dest: Path,
    env_label: str = "local",
) -> Dict[str, Any]:
    """按模块导出到 dest/parts/*.json.gz，并写 manifest.json。"""
    mods = normalize_modules(list(modules) if modules else None)
    dest = Path(dest)
    parts_dir = dest / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    dated = [m for m in mods if needs_date_range([m])]
    undated = [m for m in mods if not needs_date_range([m])]

    part_meta: List[Dict[str, Any]] = []
    seq = 0
    max_parts = max_job_parts()
    row_chunk = job_row_chunk()

    def _emit(payload: Dict[str, Any], *, label: str) -> None:
        nonlocal seq
        seq += 1
        if seq > max_parts:
            raise ValueError(
                f"分片数超过上限 ENV_SYNC_JOB_MAX_PARTS={max_parts}，请缩短日期或减少模块"
            )
        name = f"{seq:04d}.{label}.json.gz"
        path = parts_dir / name
        digest = write_part_json(path, payload)
        bundles = payload.get("bundles") or {}
        part_meta.append(
            {
                "name": name,
                "sha256": digest,
                "rows": _count_rows(bundles),
                "label": label,
                "modules": payload.get("modules") or list(bundles.keys()),
            }
        )

    if undated:
        exported = export_modules(db, undated, start_date=None, end_date=None)
        bundles = exported.get("bundles") or {}
        for bk, bd in bundles.items():
            for piece in _split_bundle_by_rows(bk, bd, chunk_rows=row_chunk):
                _emit(
                    {
                        "bundles": {bk: piece},
                        "modules": undated,
                        "date_range": exported.get("date_range"),
                    },
                    label=f"{bk}",
                )

    if dated:
        sd = _parse_day(start_date)
        ed = _parse_day(end_date)
        if not sd or not ed:
            raise ValueError("含行情/资金流等模块时必须指定 start_date 与 end_date")
        if ed < sd:
            raise ValueError("end_date 不能早于 start_date")
        for day in _iter_days(sd, ed):
            ds = day.isoformat()
            exported = export_modules(db, dated, start_date=ds, end_date=ds)
            bundles = exported.get("bundles") or {}
            if not bundles:
                continue
            for bk, bd in bundles.items():
                for piece in _split_bundle_by_rows(bk, bd, chunk_rows=row_chunk):
                    _emit(
                        {
                            "bundles": {bk: piece},
                            "modules": dated,
                            "date_range": {"start_date": ds, "end_date": ds},
                        },
                        label=f"{bk}.{ds}",
                    )

    manifest = {
        "modules": mods,
        "start_date": start_date,
        "end_date": end_date,
        "part_count": len(part_meta),
        "parts": part_meta,
        "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "env_label": env_label,
    }
    write_manifest(dest, manifest)
    return manifest
