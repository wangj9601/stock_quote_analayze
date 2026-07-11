-- 前端三级权限控制表（可 psql 手工执行）
-- 用法: psql -h HOST -p PORT -U postgres -d stock_analysis -f migrations/sql/add_frontend_permissions.sql

\set ON_ERROR_STOP on
SET lock_timeout = '120s';
SET statement_timeout = '600s';

BEGIN;
CREATE TABLE IF NOT EXISTS frontend_roles (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    is_system   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
COMMIT;

BEGIN;
CREATE TABLE IF NOT EXISTS frontend_permissions (
    id           SERIAL PRIMARY KEY,
    code         VARCHAR(200) UNIQUE NOT NULL,
    name         VARCHAR(100) NOT NULL,
    level        SMALLINT NOT NULL,
    parent_code  VARCHAR(200),
    channel_code VARCHAR(50),
    sort_order   INT DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW()
);
COMMIT;

BEGIN;
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INT NOT NULL REFERENCES frontend_roles(id) ON DELETE CASCADE,
    permission_id INT NOT NULL REFERENCES frontend_permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
COMMIT;

-- users.role_id：若应用占用 users 表，此步可能等待锁
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
COMMIT;

BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_role_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_role_id_fkey
            FOREIGN KEY (role_id) REFERENCES frontend_roles(id);
    END IF;
END $$;
COMMIT;

BEGIN;
INSERT INTO frontend_roles (code, name, description, is_system) VALUES
    ('standard', '标准用户', '默认角色，含全部已注册权限', TRUE),
    ('admin', '前台管理员', '前台管理员，含全部权限', TRUE),
    ('guest', '访客', '预留角色，本阶段不启用', TRUE)
ON CONFLICT (code) DO NOTHING;
COMMIT;

-- 权限 seed 由 Python 脚本 migrations/add_frontend_permissions.py 同步（含完整列表）
-- 部署后可在管理端「权限资源 -> 从注册表同步」完成
