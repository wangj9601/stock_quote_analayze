"""
数据库管理器（兼容旧代码）

项目当前数据库连接与 Session 工厂定义在 `backend_core.database.db`。
一些旧模块（如 CSV 报告/调度器）依赖 `DatabaseManager.query()` 这种简化接口，
因此在此提供轻量封装，避免改动大量调用方。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from sqlalchemy import text

from .db import SessionLocal

Params = Union[Dict[str, Any], Sequence[Any], Tuple[Any, ...]]


class DatabaseManager:
    """基于 SQLAlchemy Session 的简化查询接口。"""

    def query(self, sql: str, params: Optional[Params] = None) -> List[Dict[str, Any]]:
        """
        执行查询并返回 list[dict]。

        - 若 params 为 dict：按具名参数执行（:name）
        - 若 params 为序列/元组：按位置参数执行（依赖 DBAPI 方言）
        - 若 params 为 None：无参数
        """
        db = SessionLocal()
        try:
            stmt = text(sql)
            if params is None:
                result = db.execute(stmt)
            else:
                result = db.execute(stmt, params)  # type: ignore[arg-type]
            rows = result.mappings().all()
            return [dict(r) for r in rows]
        finally:
            db.close()

