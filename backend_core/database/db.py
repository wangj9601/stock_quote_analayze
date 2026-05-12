"""
数据库会话与引擎 — 兼容层。

历史上采集器、脚本从 `backend_core.database.db` 导入 `SessionLocal` / `engine`。
实现统一委托到 `backend_api.database`，与 FastAPI 应用共用同一套连接池与配置。

`Base`：供 `backend_core.models.*` 等旧 ORM 定义使用，保持独立 metadata，勿与
`backend_api.models.Base` 混用。
"""

from __future__ import annotations

from sqlalchemy.ext.declarative import declarative_base

from backend_api.database import SessionLocal, engine, get_db

Base = declarative_base()


def get_db_session():
    """供 init_db、migrations 等脚本使用：返回新 Session（调用方负责 close/commit）。"""
    return SessionLocal()


__all__ = ["SessionLocal", "engine", "get_db", "get_db_session", "Base"]
