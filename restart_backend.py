#!/usr/bin/env python3
"""重启后端服务"""
import subprocess
import time
import requests
import sys
import os

def restart_backend():
    """重启后端服务"""
    
    print("🔄 重启后端服务...")
    
    # 查找并终止现有的后端进程
    try:
        # 查找运行在5000端口的Python进程
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            if ':5000' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    print(f"找到后端进程 PID: {pid}")
                    
                    # 终止进程
                    try:
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                        print(f"✅ 已终止进程 {pid}")
                    except Exception as e:
                        print(f"❌ 终止进程失败: {e}")
                        
        # 等待端口释放
        print("等待端口释放...")
        time.sleep(2)
        
    except Exception as e:
        print(f"查找进程时出错: {e}")
    
    # 启动新的后端服务
    try:
        backend_dir = os.path.join(os.path.dirname(__file__), 'backend_api')
        
        print(f"启动后端服务...")
        print(f"工作目录: {backend_dir}")
        
        # 启动后端服务
        process = subprocess.Popen([
            sys.executable, 'main.py'
        ], cwd=backend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print(f"✅ 后端服务已启动，PID: {process.pid}")
        
        # 等待服务启动
        print("等待服务启动...")
        for i in range(30):
            try:
                response = requests.get('http://localhost:5000/', timeout=2)
                if response.status_code == 200:
                    print("✅ 后端服务启动成功！")
                    
                    # 测试股票分析API
                    print("测试股票分析API...")
                    test_response = requests.get('http://localhost:5000/api/analysis/stock/000001', timeout=5)
                    print(f"股票分析API状态: {test_response.status_code}")
                    
                    if test_response.status_code == 200:
                        print("✅ 股票分析API正常工作！")
                    else:
                        print("⚠️ 股票分析API返回状态码:", test_response.status_code)
                    
                    return True
                    
            except requests.exceptions.RequestException:
                pass
            
            print(f"等待中... ({i+1}/30)")
            time.sleep(1)
        
        print("❌ 后端服务启动超时")
        return False
        
    except Exception as e:
        print(f"❌ 启动后端服务失败: {e}")
        return False

if __name__ == "__main__":
    success = restart_backend()
    if success:
        print("\n🎉 后端服务重启成功！")
        print("现在前端应该能够正常加载股票分析数据了。")
    else:
        print("\n❌ 后端服务重启失败，请检查日志。")
