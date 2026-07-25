"""Type stub for backend_api.models package.

Runtime symbols are loaded dynamically from backend_api/models.py via importlib
(see __init__.py). Declaring __getattr__ keeps static checkers from treating
exports as ``T | None`` (from getattr(..., None) / except placeholders), which
otherwise falsely flags attribute access like ``StockBasicInfo.code`` across the codebase.
"""
from typing import Any

def __getattr__(name: str) -> Any: ...
