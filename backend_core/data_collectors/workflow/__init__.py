"""采集流程引擎：节点注册、串行执行、状态持久化。"""

from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext
from backend_core.data_collectors.workflow.engine import CollectionWorkflowEngine
from backend_core.data_collectors.workflow.node_registry import (
    get_node,
    list_node_defs,
    list_nodes_meta,
)

__all__ = [
    "CollectionWorkflowEngine",
    "WorkflowContext",
    "NodeResult",
    "get_node",
    "list_node_defs",
    "list_nodes_meta",
]
