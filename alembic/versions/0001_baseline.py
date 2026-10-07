"""baseline: 引入 Alembic 时的既有 schema 基线（no-op）

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-07

## 这个 revision 做什么

**什么都不做** —— ``upgrade()`` / ``downgrade()`` 均为 ``pass``。

它的唯一作用是给版本账本定一个起点。原因：本项目在引入 Alembic 之前，
schema 已经由两条历史路径建好：

1. ``backend_api.models.Base.metadata.create_all()``（见 ``init_db.py``）—— 130 张表；
2. ``migrations/*.py`` 里 84 个手写 SQL 脚本 —— 其中约 44 张表只有 SQL、没有 ORM 声明。

既有库（引入时 171 张表）因此 **不需要、也不能** 再执行一遍建表 DDL，否则会
``DuplicateTable`` 报错。正确做法是「打标」而非「升级」：

    .venv/Scripts/alembic.exe stamp 0001_baseline

打标后 ``alembic_version`` 表记录 ``0001_baseline``，后续所有变更从 ``0002`` 起
以增量方式接管。全新空库则是：先 ``python init_db.py`` 建好现状，再 stamp 本基线。

## 为什么不做成"一次性建全表"的基线

那需要把 171 张表全部收进 ORM metadata 或生成长度数千行的 ``op.create_table``，
而当前 44 张 SQL 建的表并无 ORM 定义，autogenerate 无法可信地表达它们。
在 ORM 覆盖度补齐之前，把基线做成 no-op 更诚实：不会产生"看起来能建库、
实际建不全"的假象。

## 校验基线是否正确

``alembic/schema_snapshot_0001.json`` 是打标时刻的结构快照（171 张表，逐表记录列数
与主键），用于审计"当时库里到底有什么"。它只是归档参考，Alembic 不会读取它。

要判断**当前**库相对 ORM metadata 有哪些差异，用：

    .venv/Scripts/python.exe scripts/db_migrate.py check
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Alembic 版本标识
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """基线：既有 schema 已就绪，此处不执行任何 DDL。"""
    pass


def downgrade() -> None:
    """基线之前无版本可回退；如需清空版本账本请手动 DROP TABLE alembic_version。"""
    pass
