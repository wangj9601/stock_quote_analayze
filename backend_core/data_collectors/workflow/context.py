"""流程运行上下文与节点结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional


@dataclass
class NodeResult:
    """单节点执行结果。"""

    success: bool
    skipped: bool = False
    message: str = ""
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, message: str = "完成", data: Optional[Dict[str, Any]] = None) -> "NodeResult":
        return cls(success=True, message=message, data=data or {})

    @classmethod
    def skip(cls, message: str) -> "NodeResult":
        return cls(success=True, skipped=True, message=message)

    @classmethod
    def fail(cls, error: str, message: str = "失败") -> "NodeResult":
        return cls(success=False, message=message, error=error)


@dataclass
class WorkflowContext:
    """节点间共享的运行上下文。"""

    run_id: str
    workflow_id: int
    trigger_source: str  # manual | cron
    trade_date: Optional[date] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)  # 流程级覆盖参数
    node_params: Dict[str, Any] = field(default_factory=dict)  # 当前节点参数
    node_outputs: Dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False

    def merge_dates_from_params(self) -> None:
        """从流程/节点参数补充日期。"""
        for src in (self.params, self.node_params):
            if not self.start_date and src.get("start_date"):
                self.start_date = str(src["start_date"])
            if not self.end_date and src.get("end_date"):
                self.end_date = str(src["end_date"])
        if not self.trade_date:
            self.trade_date = datetime.now().date()
        if not self.end_date:
            self.end_date = self.trade_date.isoformat()
        if not self.start_date:
            self.start_date = self.end_date

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "trigger_source": self.trigger_source,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "params": self.params,
            "node_outputs": self.node_outputs,
        }
