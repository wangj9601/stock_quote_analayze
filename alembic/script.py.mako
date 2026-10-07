"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

迁移脚本约定（本项目）：
  * upgrade()   写正向变更；downgrade() 尽量写可逆操作，确实不可逆时留 pass 并注明原因。
  * 优先用 op.* 高层 API；确需原生 SQL 时用 op.execute(sa.text("..."))。
  * 建表请带 IF NOT EXISTS 语义判断（op.create_table 由 Alembic 管理，无需重复判断）。
  * 数据回填与 DDL 尽量拆成两个 revision，便于失败时只回退一步。
  * 手写 SQL 建的旧表请勿在 autogenerate 里删除（env.py 默认已拦截 DROP）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Alembic 版本标识
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
