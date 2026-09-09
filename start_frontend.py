#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统前端启动脚本
"""

import os
import sys
import webbrowser
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import socket
import urllib.parse
from pathlib import Path


def _reconfigure_stdio_utf8() -> None:
    """Windows 服务 / GBK 控制台下避免 print 特殊 Unicode 触发 UnicodeEncodeError。"""
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
    """NSSM / Start-Process 重定向 stdout 时可能仍为 GBK；避免任意字符触发 UnicodeEncodeError。"""
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
    """轻量读取 .env 文件并写入 os.environ（不覆盖已存在的环境变量）。
    只支持 KEY=VALUE 形式，忽略空行与 # 注释行。
    """
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
        # 读取失败时不影响启动
        return


def is_production_env() -> bool:
    """判断是否生产环境。"""
    v = (os.getenv("ENVIRONMENT") or os.getenv("VITE_ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return v in ("prod", "production", "release")

# nginx / 浏览器提前断开时常见；不应打成 ERROR 刷屏
_CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
    TimeoutError,
)


class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""

    def __init__(self, *args, **kwargs):
        # 始终相对本脚本所在项目根下的 frontend，避免 cwd 不对时端上旧页面
        self._project_root = str(Path(__file__).resolve().parent)
        frontend_dir = str(Path(self._project_root) / "frontend")
        super().__init__(*args, directory=frontend_dir, **kwargs)

    def handle_one_request(self):
        """捕获客户端断开，避免 ThreadingHTTPServer 刷 Exception occurred..."""
        try:
            super().handle_one_request()
        except _CLIENT_DISCONNECT_ERRORS as exc:
            _print_safe(f"[WARN] client disconnected: {type(exc).__name__}: {exc}")

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        # 根路径重定向到登录页（nginx 反代看到的 301 属正常）
        if parsed_path.path == "/" or parsed_path.path == "":
            self.send_response(302)
            self.send_header("Location", "/login.html")
            self.end_headers()
            return
        # /admin* 从项目根提供（管理端静态资源；生产通常由 nginx 直转 8001）
        if parsed_path.path.startswith("/admin"):
            self.path = parsed_path.path
            self.directory = self._project_root
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def log_message(self, format, *args):
        # 与原有 access log 格式兼容，统一走可安全编码的输出
        _print_safe("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))


class _QuietClientDisconnectServer:
    """Mixin: 忽略客户端断开类异常的默认 traceback 噪音。"""

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, _CLIENT_DISCONNECT_ERRORS):
            _print_safe(
                f"[WARN] client disconnected from {client_address}: {type(exc).__name__}: {exc}"
            )
            return
        # 其它异常保留完整堆栈，便于生产排障
        super().handle_error(request, client_address)


class FrontendHTTPServer(_QuietClientDisconnectServer, HTTPServer):
    pass


class FrontendThreadingHTTPServer(_QuietClientDisconnectServer, ThreadingHTTPServer):
    pass


def check_port(port):
    """检查端口是否可用（Windows兼容版本）"""
    try:
        # 创建一个socket并尝试绑定端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 尝试绑定到端口
            sock.bind(("0.0.0.0", port))
            # 如果绑定成功，说明端口可用
            return True
    except OSError:
        # 端口已被占用
        return False
    except Exception:
        # 其他错误，认为端口不可用
        return False


def find_available_port(start_port=8000, max_attempts=100):
    """查找可用端口"""
    port = start_port
    attempts = 0
    while attempts < max_attempts:
        if check_port(port):
            return port
        port += 1
        attempts += 1
    return None


def start_server(port):
    _reconfigure_stdio_utf8()
    try:
        server_cls = FrontendThreadingHTTPServer if is_production_env() else FrontendHTTPServer
        with server_cls(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
            _print_safe("[OK] frontend HTTP server started")
            _print_safe(f"[OK] URL: http://localhost:{port}")
            _print_safe(f"[OK] login: http://localhost:{port}/login.html")
            _print_safe(f"[OK] index: http://localhost:{port}/index.html")
            _print_safe(f"[OK] admin path: http://localhost:{port}/admin")
            _print_safe(f"[OK] mode: {'production(threaded)' if is_production_env() else 'development'}")
            _print_safe("-" * 60)
            _print_safe("Press Ctrl+C to stop")
            _print_safe("-" * 60)
            def open_browser():
                time.sleep(1)
                webbrowser.open(f"http://localhost:{port}/login.html")
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            httpd.serve_forever()
    except KeyboardInterrupt:
        _print_safe("\n[STOP] frontend server stopped")
    except Exception as e:
        _print_safe(f"[ERROR] server start failed: {e}")
        sys.exit(1)

def _resolve_listen_port() -> int:
    """
    监听端口：
    - 若设置 FRONTEND_PORT / STOCK_FRONTEND_PORT，则使用该端口（须空闲）；
    - 否则固定尝试 8000（与 nginx upstream 一致）；
    - 仅当显式 ALLOW_FRONTEND_PORT_FALLBACK=1 时，8000 占用才递增找空闲口；
      生产禁止静默换端口，否则 nginx 仍反代 8000 会出现 10061。
    """
    raw = (os.getenv("FRONTEND_PORT") or os.getenv("STOCK_FRONTEND_PORT") or "").strip()
    if not raw and is_production_env():
        raw = "8000"
        _print_safe("[OK] production default FRONTEND_PORT=8000 (match nginx upstream)")

    if raw:
        try:
            port = int(raw)
        except ValueError:
            _print_safe("[ERROR] FRONTEND_PORT / STOCK_FRONTEND_PORT must be an integer")
            sys.exit(1)
        if not (1 <= port <= 65535):
            _print_safe("[ERROR] FRONTEND_PORT out of range 1-65535")
            sys.exit(1)
        if not check_port(port):
            _print_safe(f"[ERROR] port {port} is already in use (free it or set FRONTEND_PORT)")
            sys.exit(1)
        _print_safe(f"[OK] listen port from env: {port}")
        return port

    if check_port(8000):
        return 8000

    allow_fallback = (os.getenv("ALLOW_FRONTEND_PORT_FALLBACK") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    if not allow_fallback:
        _print_safe("[ERROR] port 8000 is already in use")
        _print_safe("[ERROR] nginx expects 127.0.0.1:8000; refuse silent port fallback")
        _print_safe("[ERROR] free 8000, or set FRONTEND_PORT / ALLOW_FRONTEND_PORT_FALLBACK=1")
        sys.exit(1)

    port = find_available_port(8001)
    if not port:
        _print_safe("[ERROR] no free port found from 8001")
        sys.exit(1)
    _print_safe(f"[WARN] port 8000 busy, fallback to {port} (ALLOW_FRONTEND_PORT_FALLBACK=1)")
    return port


def main():
    _reconfigure_stdio_utf8()
    _print_safe("=" * 60)
    _print_safe("stock frontend launcher")
    _print_safe("=" * 60)
    # 尝试读取项目根目录 .env（不覆盖已存在环境变量）
    project_root = Path(__file__).resolve().parent
    load_dotenv_file(str(project_root / ".env"))
    # 生产常见：DeployRoot\shared\.env（current 的上一级）
    load_dotenv_file(str(project_root.parent / "shared" / ".env"))
    port = _resolve_listen_port()
    start_server(port)

if __name__ == "__main__":
    main() 