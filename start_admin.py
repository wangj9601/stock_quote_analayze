#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理端静态资源 HTTP（admin/dist），带生产缓存头。

替代 `python -m http.server`：hashed `/assets/*` 长期缓存，HTML 不缓存。
"""

from __future__ import annotations

import os
import socket
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _reconfigure_stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for _stream in (sys.stdout, sys.stderr):
        _fn = getattr(_stream, "reconfigure", None)
        if callable(_fn):
            try:
                _fn(encoding="utf-8", errors="replace")
            except Exception:
                pass


_reconfigure_stdio_utf8()


def _print_safe(*args, **kwargs) -> None:
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    try:
        print(*args, sep=sep, end=end, **kwargs)
    except UnicodeEncodeError:
        msg = sep.join(str(a) for a in args) + end
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(msg.encode("utf-8", errors="replace"))
            buf.flush()
        else:
            sys.stdout.write(msg.encode("ascii", errors="replace").decode("ascii"))


def load_dotenv_file(dotenv_path: str) -> None:
    try:
        p = Path(dotenv_path)
        if not p.exists() or not p.is_file():
            return
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return


def is_production_env() -> bool:
    v = (
        os.getenv("ENVIRONMENT")
        or os.getenv("VITE_ENVIRONMENT")
        or os.getenv("APP_ENV")
        or ""
    ).strip().lower()
    return v in ("prod", "production", "release")


def cache_control_for_admin_path(path: str, *, production: bool) -> str:
    """Vite hashed assets 长期缓存；HTML 始终 no-cache。"""
    raw = (path or "/").split("?", 1)[0]
    ext = Path(raw).suffix.lower()
    if ext in (".html", ".htm") or raw.endswith("/") or ext == "":
        return "no-cache"
    if raw.startswith("/assets/") or "/assets/" in raw:
        # 文件名含 content hash，可 immutable
        return "public, max-age=31536000, immutable" if production else "no-store, no-cache, must-revalidate"
    if ext in {
        ".js",
        ".css",
        ".woff",
        ".woff2",
        ".ttf",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".ico",
        ".webp",
        ".map",
    }:
        return "public, max-age=604800" if production else "no-store, no-cache, must-revalidate"
    return "no-cache"


_CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
    TimeoutError,
)


class AdminHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        path = urllib.parse.urlparse(self.path).path
        self.send_header(
            "Cache-Control",
            cache_control_for_admin_path(path, production=is_production_env()),
        )
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        _print_safe(
            "%s - - [%s] %s"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except _CLIENT_DISCONNECT_ERRORS as exc:
            _print_safe(f"[WARN] client disconnected: {type(exc).__name__}: {exc}")


class AdminThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, _CLIENT_DISCONNECT_ERRORS):
            _print_safe(
                f"[WARN] client disconnected from {client_address}: {type(exc).__name__}"
            )
            return
        super().handle_error(request, client_address)


def _listen_host() -> str:
    host = (os.getenv("BIND_HOST") or "").strip()
    # 生产默认只听本机，由 nginx 反代
    if not host:
        return "127.0.0.1" if is_production_env() else "0.0.0.0"
    return host


def check_port(port: int, host: str) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def main() -> None:
    _reconfigure_stdio_utf8()
    project_root = Path(__file__).resolve().parent
    load_dotenv_file(str(project_root / ".env"))
    load_dotenv_file(str(project_root.parent / "shared" / ".env"))

    dist = project_root / "admin" / "dist"
    if not dist.is_dir():
        _print_safe(f"[ERROR] admin dist missing: {dist}")
        sys.exit(1)

    raw_port = (os.getenv("ADMIN_PORT") or "8001").strip()
    try:
        port = int(raw_port)
    except ValueError:
        _print_safe("[ERROR] ADMIN_PORT must be an integer")
        sys.exit(1)

    host = _listen_host()
    if not check_port(port, host):
        _print_safe(f"[ERROR] port {port} already in use on {host}")
        sys.exit(1)

    os.chdir(dist)
    _print_safe("[OK] admin static HTTP started")
    _print_safe(f"[OK] root: {dist}")
    _print_safe(f"[OK] listen: http://{host}:{port}")
    _print_safe(f"[OK] mode: {'production' if is_production_env() else 'development'}")
    with AdminThreadingHTTPServer((host, port), AdminHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _print_safe("\n[STOP] admin server stopped")


if __name__ == "__main__":
    main()
