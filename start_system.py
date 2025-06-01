#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统启动脚本
"""

import subprocess
import sys
import os
import time
import webbrowser
from threading import Thread
import logging
import argparse

def start_backend():
    """启动后端服务"""
    try:
        print("🚀 正在启动后端服务...")
        os.chdir('backend')
        result = subprocess.run([sys.executable, 'app.py'], capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 后端启动失败: {e}")
        return False

def start_frontend(args):
    """启动前端服务"""
    try:
        print("🌐 正在启动前端服务...")
        os.chdir('../')
        frontend_cmd = [sys.executable, 'frontend/start_frontend.py', '--port', str(args.frontend_port)]
        if args.debug:
            frontend_cmd.append('--debug')
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
        logging.info('前端服务启动命令: %s', ' '.join(frontend_cmd))
        return True
    except Exception as e:
        print(f"❌ 前端启动失败: {e}")
        return False

def open_browser():
    """延迟打开浏览器"""
    time.sleep(3)  # 等待服务启动
    try:
        webbrowser.open('http://localhost:8000/login.html')
        print("🌐 已在浏览器中打开系统登录页面")
    except Exception as e:
        print(f"⚠️ 自动打开浏览器失败: {e}")
        print("请手动访问: http://localhost:8000/login.html")

def main():
    """主函数"""
    print("=" * 50)
    print("📈 股票分析系统启动器")
    print("=" * 50)
    
    # 检查依赖
    print("🔍 检查依赖包...")
    try:
        import flask
        import flask_cors
        import akshare
        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--frontend_port', type=int, default=8000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    # 启动后端服务（后台运行）
    backend_thread = Thread(target=start_backend, daemon=True)
    backend_thread.start()
    
    # 等待后端启动
    time.sleep(2)
    
    # 延迟打开浏览器
    browser_thread = Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 启动前端服务（主进程）
    print("\n" + "=" * 50)
    print("🎯 系统启动完成!")
    print("📱 登录页面: http://localhost:8000/login.html")
    print("🏠 首页地址: http://localhost:8000/index.html")
    print("🔗 后端API: http://localhost:5000")
    print("⚙️ 管理后台: http://localhost:8000/admin")
    print("=" * 50)
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    try:
        start_frontend()
    except KeyboardInterrupt:
        print("\n👋 系统已停止")

if __name__ == '__main__':
    main() 