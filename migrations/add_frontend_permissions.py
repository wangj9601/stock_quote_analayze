"""
数据库迁移 - 前端三级权限控制表
创建 frontend_roles / frontend_permissions / role_permissions，扩展 users.role_id

生产环境 lock timeout 常见原因：
  - backend/uvicorn 仍在运行，存在 idle in transaction 或并发 DDL
  - 建议：先停止后端服务，或低峰期执行

环境变量：
  MIGRATION_LOCK_TIMEOUT_MS  锁等待毫秒，默认 300000（5 分钟）
  MIGRATION_MAX_RETRIES        遇锁超时重试次数，默认 5
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from backend_api.config import DATABASE_CONFIG
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

LOCK_TIMEOUT_MS = int(os.environ.get("MIGRATION_LOCK_TIMEOUT_MS", "300000"))
MAX_RETRIES = int(os.environ.get("MIGRATION_MAX_RETRIES", "5"))
RETRY_WAIT_SEC = int(os.environ.get("MIGRATION_RETRY_WAIT_SEC", "30"))


def _make_engine():
    return create_engine(
        DATABASE_CONFIG["url"],
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        connect_args={
            "connect_timeout": 15,
            "options": f"-c lock_timeout={LOCK_TIMEOUT_MS} -c statement_timeout=900000",
        },
    )


def _step(label: str):
    logger.info(">>> %s ...", label)
    sys.stdout.flush()


def _done(label: str, elapsed: float):
    logger.info("<<< %s 完成 (%.1fs)", label, elapsed)
    sys.stdout.flush()


def _is_lock_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "lock timeout" in msg or "locknotavailable" in msg or "canceling statement due to lock" in msg


def _run_with_retry(engine, label: str, fn):
    """遇锁超时自动重试（生产环境常见）"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0 = time.time()
            _step(label if attempt == 1 else f"{label} (重试 {attempt}/{MAX_RETRIES})")
            fn()
            _done(label, time.time() - t0)
            return
        except OperationalError as e:
            if _is_lock_error(e) and attempt < MAX_RETRIES:
                logger.warning(
                    "锁等待超时，%ds 后重试 (%d/%d)。可先执行: python migrations/diagnose_db_locks.py",
                    RETRY_WAIT_SEC, attempt, MAX_RETRIES,
                )
                sys.stdout.flush()
                time.sleep(RETRY_WAIT_SEC)
                continue
            raise


def _table_exists(conn, name: str) -> bool:
    r = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = :name
    """), {"name": name})
    return r.fetchone() is not None


def upgrade():
    engine = _make_engine()
    logger.info(
        "数据库: %s | lock_timeout=%dms | max_retries=%d",
        DATABASE_CONFIG["url"].split("@")[-1] if "@" in DATABASE_CONFIG["url"] else "(hidden)",
        LOCK_TIMEOUT_MS,
        MAX_RETRIES,
    )
    sys.stdout.flush()

    try:
        from backend_api.permission_registry_data import PERMISSION_REGISTRY, DEFAULT_ROLES
    except ModuleNotFoundError as e:
        logger.error("缺少 backend_api/permission_registry_data.py，请先部署完整代码。")
        raise SystemExit(1) from e

    def create_frontend_roles():
        with engine.begin() as conn:
            if _table_exists(conn, "frontend_roles"):
                logger.info("    frontend_roles 已存在，跳过 CREATE")
                return
            conn.execute(text("""
                CREATE TABLE frontend_roles (
                    id          SERIAL PRIMARY KEY,
                    code        VARCHAR(50) UNIQUE NOT NULL,
                    name        VARCHAR(100) NOT NULL,
                    description TEXT,
                    is_system   BOOLEAN DEFAULT FALSE,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """))

    def create_frontend_permissions():
        with engine.begin() as conn:
            if _table_exists(conn, "frontend_permissions"):
                logger.info("    frontend_permissions 已存在，跳过 CREATE")
                return
            conn.execute(text("""
                CREATE TABLE frontend_permissions (
                    id           SERIAL PRIMARY KEY,
                    code         VARCHAR(200) UNIQUE NOT NULL,
                    name         VARCHAR(100) NOT NULL,
                    level        SMALLINT NOT NULL,
                    parent_code  VARCHAR(200),
                    channel_code VARCHAR(50),
                    sort_order   INT DEFAULT 0,
                    is_active    BOOLEAN DEFAULT TRUE,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """))

    def create_role_permissions():
        with engine.begin() as conn:
            if _table_exists(conn, "role_permissions"):
                logger.info("    role_permissions 已存在，跳过 CREATE")
                return
            conn.execute(text("""
                CREATE TABLE role_permissions (
                    role_id       INT NOT NULL REFERENCES frontend_roles(id) ON DELETE CASCADE,
                    permission_id INT NOT NULL REFERENCES frontend_permissions(id) ON DELETE CASCADE,
                    PRIMARY KEY (role_id, permission_id)
                )
            """))

    _run_with_retry(engine, "1/8 创建 frontend_roles", create_frontend_roles)
    _run_with_retry(engine, "2/8 创建 frontend_permissions", create_frontend_permissions)
    _run_with_retry(engine, "3/8 创建 role_permissions", create_role_permissions)

    def alter_users_role_id():
        with engine.begin() as conn:
            _step("4/8 检查 users.role_id")
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'role_id'
            """))
            has_col = result.fetchone() is not None
            if has_col:
                logger.info("    users.role_id 已存在，跳过")
                return
            logger.info("    ALTER TABLE users ADD COLUMN role_id（需 users 表锁，建议已停 backend）")
            sys.stdout.flush()
            conn.execute(text("ALTER TABLE users ADD COLUMN role_id INTEGER"))
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_role_id_fkey') THEN
                        ALTER TABLE users ADD CONSTRAINT users_role_id_fkey
                            FOREIGN KEY (role_id) REFERENCES frontend_roles(id);
                    END IF;
                END $$
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id)"))
            _done("4/8 users.role_id", 0)

    _run_with_retry(engine, "4/8 扩展 users.role_id", alter_users_role_id)

    def seed_data():
        with engine.begin() as conn:
            for role in DEFAULT_ROLES:
                conn.execute(text("""
                    INSERT INTO frontend_roles (code, name, description, is_system)
                    VALUES (:code, :name, :description, :is_system)
                    ON CONFLICT (code) DO NOTHING
                """), role)
            for i, perm in enumerate(PERMISSION_REGISTRY, 1):
                conn.execute(text("""
                    INSERT INTO frontend_permissions (code, name, level, parent_code, channel_code, sort_order)
                    VALUES (:code, :name, :level, :parent_code, :channel_code, :sort_order)
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name, level = EXCLUDED.level,
                        parent_code = EXCLUDED.parent_code, channel_code = EXCLUDED.channel_code,
                        sort_order = EXCLUDED.sort_order, is_active = TRUE
                """), perm)
                if i % 10 == 0 or i == len(PERMISSION_REGISTRY):
                    logger.info("    权限进度 %d/%d", i, len(PERMISSION_REGISTRY))
            conn.execute(text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM frontend_roles r
                CROSS JOIN frontend_permissions p
                WHERE r.code IN ('standard', 'admin') AND p.is_active = TRUE
                ON CONFLICT DO NOTHING
            """))

    _run_with_retry(engine, "5/8 写入角色与权限 seed", seed_data)

    def backfill_users():
        with engine.begin() as conn:
            r1 = conn.execute(text("""
                UPDATE users u SET role_id = r.id FROM frontend_roles r
                WHERE u.role_id IS NULL AND (
                    (u.role = 'admin' AND r.code = 'admin') OR
                    (u.role = 'guest' AND r.code = 'guest') OR
                    ((u.role IS NULL OR u.role IN ('user', 'standard')) AND r.code = 'standard')
                )
            """))
            r2 = conn.execute(text("""
                UPDATE users u SET role_id = r.id FROM frontend_roles r
                WHERE u.role_id IS NULL AND r.code = 'standard'
            """))
            logger.info("    回填行数: %s + %s", getattr(r1, "rowcount", "?"), getattr(r2, "rowcount", "?"))

    _run_with_retry(engine, "6/8 回填 users.role_id", backfill_users)

    logger.info("✅ 前端权限控制表迁移全部完成")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        upgrade()
    except Exception as e:
        logger.error("❌ 迁移失败: %s", e)
        if _is_lock_error(e):
            logger.error(
                "数据库锁被占用。请按顺序操作:\n"
                "  1. 停止 backend/uvicorn 服务\n"
                "  2. python migrations/diagnose_db_locks.py  查看阻塞 pid\n"
                "  3. 必要时 SELECT pg_terminate_backend(<pid>);\n"
                "  4. 重跑: python migrations/add_frontend_permissions.py\n"
                "  或加大等待: set MIGRATION_LOCK_TIMEOUT_MS=600000 && python migrations/add_frontend_permissions.py"
            )
        raise SystemExit(1) from e
