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

class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""
    def __init__(self, *args, **kwargs):
        # 设置 frontend 目录为根目录
        super().__init__(*args, directory="frontend", **kwargs)
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        # 如果访问根路径，重定向到 login.html
        if parsed_path.path == "/" or parsed_path.path == "":
            self.send_response(301)
            self.send_header('Location', '/login.html')
            self.end_headers()
            return
        # 如果访问 admin 路径，重定向到 admin 目录
        if parsed_path.path.startswith("/admin"):
            self.path = parsed_path.path
            self.directory = "."  # 项目根目录
        super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def check_port(port):
    """检查端口是否可用（Windows兼容版本）"""
    try:
        # 创建一个socket并尝试绑定端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 尝试绑定到端口
            result = sock.bind(('0.0.0.0', port))
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
    try:
        server_cls = ThreadingHTTPServer if is_production_env() else HTTPServer
        with server_cls(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
            print(f"✓ 前端服务器启动成功")
            print(f"✓ 服务地址: http://localhost:{port}")
            print(f"✓ 登录页面: http://localhost:{port}/login.html")
            print(f"✓ 首页: http://localhost:{port}/index.html")
            print(f"✓ 管理后台: http://localhost:{port}/admin")
            print(f"✓ 运行环境: {'production(多线程)' if is_production_env() else 'development(单线程)'}")
            print("-" * 60)
            print("按 Ctrl+C 停止服务")
            print("-" * 60)
            def open_browser():
                time.sleep(1)
                webbrowser.open(f'http://localhost:{port}/login.html')
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n前端服务已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("           股票分析系统前端启动器")
    print("=" * 60)
    # 尝试读取项目根目录 .env（不覆盖已存在环境变量）
    project_root = Path(__file__).resolve().parent
    load_dotenv_file(str(project_root / ".env"))
    port = find_available_port(8000)
    if not port:
        print("❌ 无法找到可用端口")
        sys.exit(1)
    start_server(port)

if __name__ == "__main__":
    main() 