#!/usr/bin/env python3
"""检查后端启动时的路由注册情况"""
import subprocess
import time
import requests
import sys
import os

def check_backend_startup():
    """检查后端启动时的路由注册情况"""
    
    print("🔍 检查后端启动时的路由注册情况...")
    
    # 启动后端并捕获输出
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend_api')
    
    try:
        print(f"启动后端服务...")
        print(f"工作目录: {backend_dir}")
        
        # 启动后端服务并捕获输出
        process = subprocess.Popen([
            sys.executable, 'main.py'
        ], cwd=backend_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        print(f"后端服务已启动，PID: {process.pid}")
        
        # 读取启动日志
        startup_lines = []
        start_time = time.time()
        
        while time.time() - start_time < 10:  # 等待10秒
            if process.poll() is not None:
                break
                
            # 读取可用的输出
            try:
                line = process.stdout.readline()
                if line:
                    startup_lines.append(line.strip())
                    print(f"日志: {line.strip()}")
                    
                    # 检查关键信息
                    if 'stock_analysis_router' in line:
                        print(f"🎯 找到股票分析路由: {line.strip()}")
                    elif '路由注册成功' in line and '分析' in line:
                        print(f"🎯 找到分析路由注册: {line.strip()}")
                    elif '❌' in line and 'stock_analysis' in line:
                        print(f"❌ 股票分析路由错误: {line.strip()}")
                        
            except:
                pass
                
            time.sleep(0.1)
        
        # 等待服务完全启动
        print("等待服务完全启动...")
        time.sleep(3)
        
        # 测试服务是否可用
        try:
            response = requests.get('http://localhost:5000/', timeout=5)
            if response.status_code == 200:
                print("✅ 后端服务可用")
                
                # 检查路由
                routes_response = requests.get('http://localhost:5000/debug/routes', timeout=5)
                if routes_response.status_code == 200:
                    routes = routes_response.json()
                    analysis_routes = [r for r in routes if '/api/analysis' in str(r)]
                    
                    print(f"\n📊 分析路由检查:")
                    if analysis_routes:
                        print(f"✅ 找到 {len(analysis_routes)} 个分析路由:")
                        for route in analysis_routes:
                            print(f"  - {route}")
                    else:
                        print(f"❌ 没有找到分析路由")
                        
                    # 测试股票分析API
                    print(f"\n🧪 测试股票分析API:")
                    test_response = requests.get('http://localhost:5000/api/analysis/stock/000001', timeout=5)
                    print(f"状态码: {test_response.status_code}")
                    
                    if test_response.status_code == 200:
                        print("✅ 股票分析API正常工作")
                    elif test_response.status_code == 404:
                        print("❌ 股票分析API返回404")
                    else:
                        print(f"⚠️ 股票分析API返回: {test_response.status_code}")
                        
                else:
                    print("❌ 无法获取路由信息")
            else:
                print("❌ 后端服务不可用")
                
        except Exception as e:
            print(f"❌ 测试服务时出错: {e}")
        
        # 保持服务运行
        print(f"\n📝 启动日志摘要:")
        for line in startup_lines[:20]:  # 显示前20行
            if any(keyword in line for keyword in ['stock_analysis', '分析', '路由', '导入', '注册']):
                print(f"  {line}")
        
        print(f"\n✅ 检查完成。后端服务正在运行中...")
        print(f"如需停止服务，请按 Ctrl+C")
        
        # 保持服务运行
        try:
            process.wait()
        except KeyboardInterrupt:
            print(f"\n🛑 停止后端服务...")
            process.terminate()
            process.wait()
            print(f"✅ 后端服务已停止")
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")

if __name__ == "__main__":
    check_backend_startup()
