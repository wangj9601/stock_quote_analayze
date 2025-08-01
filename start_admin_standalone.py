#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的管理后台启动脚本
完全独立于frontend目录运行
"""

import http.server
import socketserver
import os
import webbrowser
import threading
import time
import sys
from pathlib import Path

def check_admin_resources():
    """检查admin目录资源完整性"""
    admin_dir = Path('admin')
    required_files = [
        'index.html',
        'css/admin.css',
        'js/common.js',
        'js/admin.js',
        'js/quotes.js',
        'js/dashboard.js'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (admin_dir / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ 缺少必要的admin资源文件:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ admin资源文件检查通过")
    return True

def start_standalone_admin_server():
    """启动独立的管理后台服务"""
    print("=" * 60)
    print("           股票分析系统 - 独立管理后台")
    print("=" * 60)
    
    # 检查admin资源
    if not check_admin_resources():
        print("❌ 无法启动管理后台，缺少必要资源")
        sys.exit(1)
    
    # 确保在项目根目录
    if not Path('admin').exists():
        print("❌ 请在项目根目录运行此脚本")
        sys.exit(1)
    
    PORT = 8001
    
    # 检查端口是否可用
    try:
        with socketserver.TCPServer(("", PORT), None) as server:
            pass
    except OSError:
        print(f"❌ 端口 {PORT} 已被占用")
        sys.exit(1)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    # 自定义请求处理器，专门为admin目录服务
    class AdminRequestHandler(Handler):
        def __init__(self, *args, **kwargs):
            # 设置admin目录为根目录
            super().__init__(*args, directory="admin", **kwargs)
        
        def end_headers(self):
            # 添加CORS和缓存控制头部
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            super().end_headers()
        
        def do_OPTIONS(self):
            # 处理预检请求
            self.send_response(200)
            self.end_headers()
        
        def do_GET(self):
            # 如果访问根路径，重定向到index.html
            if self.path == "/" or self.path == "":
                self.path = "/index.html"
            super().do_GET()
    
    try:
        with socketserver.TCPServer(("", PORT), AdminRequestHandler) as httpd:
            print(f"🚀 独立管理后台已启动")
            print(f"📱 访问地址: http://localhost:{PORT}")
            print(f"👤 默认账号: admin")
            print(f"🔑 默认密码: 123456")
            print(f"🔗 后端API: http://localhost:5000")
            print(f"📖 功能说明:")
            print(f"   - 用户管理：创建、编辑、禁用/启用用户")
            print(f"   - 数据统计：查看系统运行状态")
            print(f"   - 行情数据：实时和历史行情管理")
            print(f"   - 系统监控：系统运行状态监控")
            print(f"   - 权限管控：管理用户访问权限")
            print("=" * 60)
            print("💡 提示：此管理后台完全独立运行，不依赖frontend目录")
            print("=" * 60)
            
            def open_browser():
                time.sleep(1)
                webbrowser.open(f'http://localhost:{PORT}')
            
            threading.Thread(target=open_browser, daemon=True).start()
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n👋 管理后台服务已停止")
                
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_standalone_admin_server() 