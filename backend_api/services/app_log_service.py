# -*- coding: utf-8 -*-
"""应用日志文件扫描：白名单、尾部窗口、解析、脱敏、筛选分页。"""
from __future__ import annotations

import fnmatch
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend_core.logging_utils import LOG_SCAN_WINDOW_BYTES, get_logs_dir

WHITELIST_EXACT = frozenset({"app.log", "quotes.log"})
WHITELIST_GLOBS = ("akshare_*.log", "enhanced_akshare_*.log")

_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)\s*-\s*"
    r"(?P<logger>.+?)\s*-\s*"
    r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\s*-\s*"
    r"(?:\[(?P<loc>[^\]]+)\]\s*-\s*)?"
    r"(?P<msg>.*)$"
)

_REDACT_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = (
    (
        re.compile(r"(postgresql(?:\+\w+)?://[^:\s/]+:)([^@/\s]+)(@)", re.IGNORECASE),
        r"\1***\3",
    ),
    (
        re.compile(r"((?:password|passwd|pwd)\s*[=:]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1***",
    ),
    (
        re.compile(r"((?:DB_PASSWORD|JWT_SECRET_KEY)\s*[=:]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1***",
    ),
)

_LEVEL_ALIASES = {
    "WARN": "WARNING",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "ERROR",
    "INFO": "INFO",
    "DEBUG": "DEBUG",
    "UNKNOWN": "UNKNOWN",
}


@dataclass
class AppLogRecord:
    timestamp: Optional[datetime]
    timestamp_raw: str
    level: str
    logger: str
    message: str
    source_file: str
    location: str = ""

    def to_dict(self, entry_id: str) -> Dict[str, Any]:
        return {
            "id": entry_id,
            "timestamp": self.timestamp.isoformat(sep=" ") if self.timestamp else self.timestamp_raw,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "source_file": self.source_file,
            "location": self.location,
        }


def redact_secrets(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _REDACT_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def is_whitelist_name(name: str) -> bool:
    base = Path(name).name
    # 轮转备份 app.log.1 → 取主名 app.log
    primary = _primary_log_name(base)
    if primary in WHITELIST_EXACT:
        return True
    return any(fnmatch.fnmatch(primary, g) for g in WHITELIST_GLOBS)


def _primary_log_name(name: str) -> str:
    """app.log.1 / app.log.5 → app.log；akshare_x.log.2 → akshare_x.log。"""
    m = re.match(r"^(.+\.log)(?:\.\d+)?$", name)
    return m.group(1) if m else name


def list_whitelist_files(logs_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = logs_dir or get_logs_dir()
    if not root.exists():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        name = path.name
        # 列表只展示主文件，不含 .1/.2
        if re.search(r"\.log\.\d+$", name):
            continue
        if not is_whitelist_name(name):
            continue
        try:
            st = path.stat()
            items.append(
                {
                    "name": name,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
                }
            )
        except OSError:
            continue
    return items


def _expand_with_rotations(primary: Path) -> List[Path]:
    """主文件 + 轮转备份，按新到旧：primary, .1, .2, ..."""
    paths: List[Path] = []
    if primary.exists() and primary.is_file():
        paths.append(primary)
    for i in range(1, 16):
        rotated = Path(f"{primary}.{i}")
        if rotated.exists() and rotated.is_file():
            paths.append(rotated)
        else:
            break
    return paths


def resolve_scan_targets(
    source_file: Optional[str] = None,
    logs_dir: Optional[Path] = None,
) -> List[Tuple[str, Path]]:
    """
    返回 (展示用主文件名, 实际路径) 列表。
    source_file 为空则扫全部白名单主文件及其轮转备份。
    """
    root = logs_dir or get_logs_dir()
    targets: List[Tuple[str, Path]] = []

    if source_file:
        name = Path(source_file).name
        if not is_whitelist_name(name) or re.search(r"\.log\.\d+$", name):
            return []
        primary = root / name
        for p in _expand_with_rotations(primary):
            targets.append((name, p))
        return targets

    for info in list_whitelist_files(root):
        name = info["name"]
        for p in _expand_with_rotations(root / name):
            targets.append((name, p))
    return targets


def read_tail_text(path: Path, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    try:
        with open(path, "rb") as f:
            if size <= max_bytes:
                data = f.read()
            else:
                f.seek(size - max_bytes)
                data = f.read()
                nl = data.find(b"\n")
                if nl != -1:
                    data = data[nl + 1 :]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _parse_timestamp(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_log_text(text: str, source_file: str) -> List[AppLogRecord]:
    records: List[AppLogRecord] = []
    current: Optional[AppLogRecord] = None

    for line in text.splitlines():
        m = _LOG_LINE_RE.match(line)
        if m:
            if current is not None:
                records.append(current)
            level = _LEVEL_ALIASES.get(m.group("level").upper(), "UNKNOWN")
            ts_raw = m.group("ts")
            current = AppLogRecord(
                timestamp=_parse_timestamp(ts_raw),
                timestamp_raw=ts_raw,
                level=level,
                logger=(m.group("logger") or "").strip(),
                message=redact_secrets(m.group("msg") or ""),
                source_file=source_file,
                location=(m.group("loc") or "").strip(),
            )
        else:
            if current is not None:
                # 无日志头的行并入上一条（堆栈等）
                current.message = redact_secrets(f"{current.message}\n{line}")
            else:
                records.append(
                    AppLogRecord(
                        timestamp=None,
                        timestamp_raw="",
                        level="UNKNOWN",
                        logger="",
                        message=redact_secrets(line),
                        source_file=source_file,
                    )
                )
    if current is not None:
        records.append(current)
    return records


def _parse_levels(levels: Optional[str]) -> Optional[set[str]]:
    if levels is None or str(levels).strip() == "" or str(levels).strip().lower() == "all":
        return None
    out: set[str] = set()
    for part in str(levels).split(","):
        key = part.strip().upper()
        if not key or key == "ALL":
            continue
        out.add(_LEVEL_ALIASES.get(key, key))
    return out or None


def _parse_dt_boundary(value: Optional[str], *, end: bool) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip().replace("T", " ").replace("Z", "")
    if len(value) == 10:
        value = f"{value} 23:59:59" if end else f"{value} 00:00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def scan_app_logs(
    *,
    levels: Optional[str] = "WARNING,ERROR",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    source_file: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    window_bytes: int = LOG_SCAN_WINDOW_BYTES,
    logs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    targets = resolve_scan_targets(source_file, logs_dir)
    # 按 mtime 新到旧分配扫描字节，优先读新内容
    scored: List[Tuple[float, str, Path]] = []
    for display_name, path in targets:
        try:
            scored.append((path.stat().st_mtime, display_name, path))
        except OSError:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)

    remaining = max(0, int(window_bytes))
    bytes_read = 0
    all_records: List[AppLogRecord] = []

    for _, display_name, path in scored:
        if remaining <= 0:
            break
        try:
            size = path.stat().st_size
        except OSError:
            continue
        take = min(remaining, size)
        text = read_tail_text(path, take)
        if not text:
            continue
        # 实际占用按 take 计（解码后长度可能不同）
        bytes_read += take
        remaining -= take
        all_records.extend(parse_log_text(text, display_name))

    level_set = _parse_levels(levels)
    start_dt = _parse_dt_boundary(start_date, end=False)
    end_dt = _parse_dt_boundary(end_date, end=True)
    kw = (keyword or "").strip().lower()

    filtered: List[AppLogRecord] = []
    for rec in all_records:
        if level_set is not None and rec.level not in level_set:
            continue
        if start_dt is not None and rec.timestamp is not None and rec.timestamp < start_dt:
            continue
        if end_dt is not None and rec.timestamp is not None and rec.timestamp > end_dt:
            continue
        # 无时间戳的 UNKNOWN 行：仅在未设时间窗时保留；有时间窗则丢弃
        if (start_dt or end_dt) and rec.timestamp is None:
            continue
        if kw:
            hay = f"{rec.logger} {rec.message} {rec.source_file}".lower()
            if kw not in hay:
                continue
        filtered.append(rec)

    # 时间倒序；无时间戳的排最后
    filtered.sort(
        key=lambda r: r.timestamp or datetime.min,
        reverse=True,
    )

    level_counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0, "UNKNOWN": 0}
    for rec in filtered:
        level_counts[rec.level] = level_counts.get(rec.level, 0) + 1

    total = len(filtered)
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    start_idx = (page - 1) * page_size
    page_rows = filtered[start_idx : start_idx + page_size]

    data = []
    for idx, rec in enumerate(page_rows):
        raw_id = f"{rec.source_file}|{rec.timestamp_raw}|{rec.logger}|{rec.message[:120]}|{start_idx + idx}"
        entry_id = hashlib.sha1(raw_id.encode("utf-8", errors="replace")).hexdigest()[:16]
        data.append(rec.to_dict(entry_id))

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "total": total,
            "error": level_counts.get("ERROR", 0),
            "warning": level_counts.get("WARNING", 0),
            "info": level_counts.get("INFO", 0),
            "debug": level_counts.get("DEBUG", 0),
            "unknown": level_counts.get("UNKNOWN", 0),
            "window_bytes": window_bytes,
            "bytes_read": bytes_read,
            "files_scanned": len({p for _, _, p in scored}),
        },
        "files": list_whitelist_files(logs_dir),
    }
