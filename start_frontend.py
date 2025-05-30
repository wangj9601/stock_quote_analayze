#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统前端启动脚本
"""

import os
import sys
import webbrowser
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import TCPServer
import threading
import urllib.parse

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
    try:
        with TCPServer(("0.0.0.0", port), None) as server:
            return True
    except OSError:
        return False

def find_available_port(start_port=8000):
    port = start_port
    while port < start_port + 100:
        if check_port(port):
            return port
        port += 1
    return None

def start_server(port):
    try:
        with HTTPServer(("0.0.0.0", port), CustomHTTPRequestHandler) as httpd:
            print(f"✓ 前端服务器启动成功")
            print(f"✓ 服务地址: http://localhost:{port}")
            print(f"✓ 登录页面: http://localhost:{port}/login.html")
            print(f"✓ 首页: http://localhost:{port}/index.html")
            print(f"✓ 管理后台: http://localhost:{port}/admin")
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
    port = find_available_port(8000)
    if not port:
        print("❌ 无法找到可用端口")
        sys.exit(1)
    start_server(port)

if __name__ == "__main__":
    main() 