"""
为写入 stdout/stderr 的每一行增加本地时间前缀，便于 NSSM 重定向到 shared/logs 后检索。
格式: YYYY-mm-dd HH:MM:SS | 原行内容
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, TextIO

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_installed = False


class _TimestampPrefixedStream:
    __slots__ = ("_stream", "_buf")

    def __init__(self, stream: TextIO) -> None:
        object.__setattr__(self, "_stream", stream)
        object.__setattr__(self, "_buf", "")

    def write(self, s: str) -> int:
        if s is None:
            return 0
        if not isinstance(s, str):
            s = str(s)
        buf: str = self._buf + s
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            ts = datetime.now().strftime(_TS_FMT)
            self._stream.write(f"{ts} | {line}\n")
        self._buf = buf
        try:
            return len(s.encode("utf-8", errors="replace"))
        except Exception:
            return len(s)

    def flush(self) -> None:
        buf: str = self._buf
        if buf:
            ts = datetime.now().strftime(_TS_FMT)
            self._stream.write(f"{ts} | {buf}")
            self._buf = ""
        self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_stream"), name)


def install_timestamp_prefix_stdio() -> None:
    """在 UTF-8 reconfigure 之后调用：包装 sys.stdout / sys.stderr。"""
    global _installed
    if _installed:
        return
    _installed = True
    sys.stdout = _TimestampPrefixedStream(sys.stdout)
    sys.stderr = _TimestampPrefixedStream(sys.stderr)
