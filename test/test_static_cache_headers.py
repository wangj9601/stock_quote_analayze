"""静态资源 Cache-Control 策略（公网首屏优化第一波）。"""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_frontend_cache_control_production():
    mod = _load("start_frontend_mod", "start_frontend.py")
    assert mod.cache_control_for_path("/js/echarts.min.js", production=True) == (
        "public, max-age=604800"
    )
    assert mod.cache_control_for_path("/css/common.css", production=True).startswith(
        "public, max-age="
    )
    assert mod.cache_control_for_path("/fonts/x.woff2", production=True).startswith(
        "public, max-age="
    )
    assert mod.cache_control_for_path("/login.html", production=True) == "no-cache"
    assert mod.cache_control_for_path("/", production=True) == "no-cache"


def test_frontend_cache_control_dev_no_store():
    mod = _load("start_frontend_mod2", "start_frontend.py")
    assert "no-store" in mod.cache_control_for_path("/js/a.js", production=False)


def test_admin_cache_control_assets_immutable():
    mod = _load("start_admin_mod", "start_admin.py")
    assert mod.cache_control_for_admin_path(
        "/assets/index-abc.js", production=True
    ) == "public, max-age=31536000, immutable"
    assert mod.cache_control_for_admin_path("/index.html", production=True) == "no-cache"
    assert mod.cache_control_for_admin_path("/login", production=True) == "no-cache"
