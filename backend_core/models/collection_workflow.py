"""采集流程 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend_core.database.db import Base


class CollectionWorkflow(Base):
    __tablename__ = "collection_workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True, nullable=False)
    trigger_type = Column(String(20), nullable=False, default="manual")  # manual | cron
    cron_dow = Column(String(32))
    cron_hour = Column(String(32))
    cron_minute = Column(Integer)
    skip_on_holiday = Column(String(10), default="NONE")  # CN | HK | BOTH | NONE
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    nodes = relationship(
        "CollectionWorkflowNode",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="CollectionWorkflowNode.order_index",
    )


class CollectionWorkflowNode(Base):
    __tablename__ = "collection_workflow_nodes"
    __table_args__ = (UniqueConstraint("workflow_id", "order_index", name="uq_wf_node_order"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("collection_workflows.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    node_key = Column(String(64), nullable=False)
    display_name = Column(String(120))
    params = Column(JSONB, default=dict)
    on_failure = Column(String(20), default="stop")  # stop | continue
    retry_count = Column(Integer, default=0)
    wait_seconds = Column(Integer, default=0)
    enabled = Column(Boolean, default=True, nullable=False)

    workflow = relationship("CollectionWorkflow", back_populates="nodes")


class CollectionWorkflowRun(Base):
    __tablename__ = "collection_workflow_runs"

    run_id = Column(String(64), primary_key=True)
    workflow_id = Column(Integer, nullable=False, index=True)
    workflow_name = Column(String(120))
    status = Column(String(20), nullable=False, default="pending")
    # pending|running|completed|failed|cancelled|skipped
    trigger_source = Column(String(20), nullable=False)  # manual|cron
    current_node_index = Column(Integer)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_message = Column(Text)
    context = Column(JSONB, default=dict)

    node_runs = relationship(
        "CollectionWorkflowNodeRun",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CollectionWorkflowNodeRun.order_index",
    )


class CollectionWorkflowNodeRun(Base):
    __tablename__ = "collection_workflow_node_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        String(64),
        ForeignKey("collection_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_key = Column(String(64), nullable=False)
    order_index = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    # pending|running|completed|failed|skipped|cancelled
    progress = Column(Integer, default=0)
    message = Column(Text)
    error = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    result = Column(JSONB, default=dict)

    run = relationship("CollectionWorkflowRun", back_populates="node_runs")
