import os
import sys
import subprocess
from pathlib import Path

root_dir = os.path.dirname(os.path.abspath(__file__))


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

# 轻量读取 .env 文件并写入 env（不覆盖已存在环境变量）
def _load_dotenv_into_env(env: dict, dotenv_path: str) -> None:
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
            if k and k not in env:
                env[k] = v
    except Exception:
        return


def _is_production_env(env: dict) -> bool:
    v = (env.get("ENVIRONMENT") or env.get("VITE_ENVIRONMENT") or env.get("APP_ENV") or "").strip().lower()
    return v in ("prod", "production", "release")


# Ensure PYTHONPATH includes root and backend_api
env = os.environ.copy()
_load_dotenv_into_env(env, os.path.join(root_dir, ".env"))
current_path = env.get("PYTHONPATH", "")
# Add root dir and backend_api dir to PYTHONPATH
env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{os.path.join(root_dir, 'backend_api')}{os.pathsep}{current_path}"

if __name__ == "__main__":
    _reconfigure_stdio_utf8()
    # Windows 服务/NSSM 下 stdout 常为 GBK，勿用 emoji，否则 UnicodeEncodeError 会直接退出
    print("[START] 启动股票分析系统后端服务...")
    print(f"[PATH] Working Directory: {root_dir}")
    print(f"[PATH] PYTHONPATH 已包含: {root_dir} 与 backend_api")
    is_prod = _is_production_env(env)
    port = str(env.get("BACKEND_PORT") or env.get("PORT") or "5000")
    workers = int(env.get("UVICORN_WORKERS") or env.get("BACKEND_WORKERS") or (os.cpu_count() or 2))
    if workers < 1:
        workers = 1
    print(f"[ENV] 运行环境: {'production(多worker)' if is_prod else 'development(--reload)'}")
    print(f"[ENV] 端口: {port}")
    
    # Use -m uvicorn to avoid import issues and let uvicorn handle reloading properly
    cmd = [sys.executable, "-m", "uvicorn", "backend_api.main:app",
           "--host", "0.0.0.0", "--port", port]
    if is_prod:
        # 生产环境用多 worker 提升并发；注意 workers>1 为多进程（uvicorn 机制）
        cmd += ["--workers", str(workers)]
    else:
        cmd += ["--reload"]
    
    try:
        subprocess.run(cmd, env=env, cwd=root_dir)
    except KeyboardInterrupt:
        print("\n[STOP] Service stopped")
    except Exception as e:
        print(f"[ERROR] Failed to start service: {e}")