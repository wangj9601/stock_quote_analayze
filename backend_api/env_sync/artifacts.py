# -*- coding: utf-8 -*-
"""环境同步异步任务产物目录（本机磁盘）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def resolve_artifact_root() -> Path:
    """解析产物根目录。

    优先级：ENV_SYNC_ARTIFACT_ROOT → /opt/stock_quote/shared/env_sync → 仓库 shared/env_sync。
    """
    override = (os.getenv("ENV_SYNC_ARTIFACT_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    opt = Path("/opt/stock_quote/shared")
    if opt.is_dir():
        return (opt / "env_sync").resolve()

    # backend_api/env_sync/artifacts.py → 仓库根
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / "shared" / "env_sync").resolve()


def job_dir(job_id: str, *, root: Optional[Path] = None) -> Path:
    base = root or resolve_artifact_root()
    safe = "".join(c for c in (job_id or "") if c.isalnum() or c in "-_")
    if not safe or safe != job_id:
        raise ValueError(f"非法 job_id: {job_id!r}")
    return base / safe


def ensure_job_dirs(job_id: str, *, root: Optional[Path] = None) -> Path:
    d = job_dir(job_id, root=root)
    (d / "parts").mkdir(parents=True, exist_ok=True)
    return d


def write_manifest(dest: Path, data: Dict[str, Any]) -> Path:
    path = dest / "manifest.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def read_manifest(dest: Path) -> Dict[str, Any]:
    path = dest / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"缺少 manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_ttl_days() -> int:
    try:
        return max(1, int(os.getenv("ENV_SYNC_ARTIFACT_TTL_DAYS") or "7"))
    except ValueError:
        return 7
