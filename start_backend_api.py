import os
import sys
import subprocess

root_dir = os.path.dirname(os.path.abspath(__file__))

# Ensure PYTHONPATH includes root and backend_api
env = os.environ.copy()
current_path = env.get("PYTHONPATH", "")
# Add root dir and backend_api dir to PYTHONPATH
env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{os.path.join(root_dir, 'backend_api')}{os.pathsep}{current_path}"

if __name__ == "__main__":
    print("🚀 启动股票分析系统后端服务...")
    print(f"📁 Working Directory: {root_dir}")
    print(f"🐍 PYTHONPATH set to include: {root_dir} and backend_api")
    
    # Use -m uvicorn to avoid import issues and let uvicorn handle reloading properly
    cmd = [sys.executable, "-m", "uvicorn", "backend_api.main:app", 
           "--host", "0.0.0.0", "--port", "5000", "--reload"]
    
    try:
        subprocess.run(cmd, env=env, cwd=root_dir)
    except KeyboardInterrupt:
        print("\n🛑 Service stopped")
    except Exception as e:
        print(f"❌ Failed to start service: {e}")