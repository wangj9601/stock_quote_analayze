-- 修复 stock_basic_info 表结构
-- 解决 ON CONFLICT (code) 错误

-- 1. 检查当前表结构
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'stock_basic_info' 
ORDER BY ordinal_position;

-- 2. 检查约束
SELECT conname, contype, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'stock_basic_info'::regclass;

-- 3. 如果表不存在，创建表
CREATE TABLE IF NOT EXISTS stock_basic_info (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 如果表存在但没有主键约束，添加主键约束
-- 首先删除可能存在的重复数据
DELETE FROM stock_basic_info a USING stock_basic_info b 
WHERE a.ctid < b.ctid AND a.code = b.code;

-- 添加主键约束（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'stock_basic_info_pkey' 
        AND conrelid = 'stock_basic_info'::regclass
    ) THEN
        ALTER TABLE stock_basic_info ADD CONSTRAINT stock_basic_info_pkey PRIMARY KEY (code);
    END IF;
END $$;

-- 5. 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_stock_basic_info_code ON stock_basic_info(code);
CREATE INDEX IF NOT EXISTS idx_stock_basic_info_name ON stock_basic_info(name);

-- 6. 验证修复结果
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'stock_basic_info' 
ORDER BY ordinal_position;

SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint 
WHERE conrelid = 'stock_basic_info'::regclass; 