#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server
import socketserver
import os
import webbrowser
import threading
import time

def start_admin_server():
    """启动admin前端服务"""
    # 切换到admin目录
    os.chdir('admin')
    
    PORT = 8001
    Handler = http.server.SimpleHTTPRequestHandler
    
    # 添加CORS头部支持
    class CORSRequestHandler(Handler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            super().end_headers()
        
        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()
    
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        print(f"🚀 Admin管理端已启动")
        print(f"📱 访问地址: http://localhost:{PORT}")
        print(f"👤 默认账号: admin")
        print(f"🔑 默认密码: 123456")
        print(f"📖 功能说明:")
        print(f"   - 用户管理：创建、编辑、禁用/启用用户")
        print(f"   - 数据统计：查看系统运行状态")
        print(f"   - 权限管控：管理用户访问权限")
        print("=" * 50)
        
        def open_browser():
            time.sleep(1)
            webbrowser.open(f'http://localhost:{PORT}')
        
        threading.Thread(target=open_browser).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Admin服务已停止")

if __name__ == '__main__':
    start_admin_server() 