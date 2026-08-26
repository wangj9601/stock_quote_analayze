"""采集流程自动化 API。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_core.data_collectors.workflow.engine import workflow_engine
from backend_core.data_collectors.workflow.mutex import get_active, is_busy, list_active
from backend_core.data_collectors.workflow.node_registry import get_node, list_nodes_meta
from backend_core.models.collection_workflow import (
    CollectionWorkflow,
    CollectionWorkflowNode,
    CollectionWorkflowNodeRun,
    CollectionWorkflowRun,
)

logger = logging.getLogger(__name__)

# 管理端 apiService baseURL 为 /api/admin，须与此前缀一致
router = APIRouter(prefix="/api/admin/collection-workflows", tags=["采集流程"])


# ---------- Pydantic ----------


class WorkflowNodeIn(BaseModel):
    order_index: int
    node_key: str
    display_name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    on_failure: str = "stop"
    retry_count: int = 0
    wait_seconds: int = 0
    enabled: bool = True


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    enabled: bool = True
    trigger_type: str = "manual"  # manual | cron
    cron_dow: Optional[str] = "mon-fri"
    cron_hour: Optional[str] = "15"
    cron_minute: Optional[int] = 35
    skip_on_holiday: str = "NONE"
    nodes: List[WorkflowNodeIn] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_type: Optional[str] = None
    cron_dow: Optional[str] = None
    cron_hour: Optional[str] = None
    cron_minute: Optional[int] = None
    skip_on_holiday: Optional[str] = None


class WorkflowNodesReplace(BaseModel):
    nodes: List[WorkflowNodeIn]


class WorkflowRunRequest(BaseModel):
    override_params: Optional[Dict[str, Any]] = None


def _node_out(n: CollectionWorkflowNode) -> dict:
    return {
        "id": n.id,
        "order_index": n.order_index,
        "node_key": n.node_key,
        "display_name": n.display_name,
        "params": n.params or {},
        "on_failure": n.on_failure or "stop",
        "retry_count": n.retry_count or 0,
        "wait_seconds": n.wait_seconds or 0,
        "enabled": bool(n.enabled),
    }


def _workflow_out(wf: CollectionWorkflow, include_nodes: bool = True) -> dict:
    data = {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "enabled": bool(wf.enabled),
        "trigger_type": wf.trigger_type,
        "cron_dow": wf.cron_dow,
        "cron_hour": wf.cron_hour,
        "cron_minute": wf.cron_minute,
        "skip_on_holiday": wf.skip_on_holiday or "NONE",
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }
    if include_nodes:
        nodes = sorted(wf.nodes or [], key=lambda x: x.order_index)
        data["nodes"] = [_node_out(n) for n in nodes]
    return data


def _run_out(run: CollectionWorkflowRun, include_nodes: bool = False) -> dict:
    data = {
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "trigger_source": run.trigger_source,
        "current_node_index": run.current_node_index,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        "context": run.context or {},
    }
    if include_nodes:
        nrs = sorted(run.node_runs or [], key=lambda x: x.order_index)
        data["node_runs"] = [
            {
                "id": nr.id,
                "node_key": nr.node_key,
                "order_index": nr.order_index,
                "status": nr.status,
                "progress": nr.progress or 0,
                "message": nr.message,
                "error": nr.error,
                "started_at": nr.started_at.isoformat() if nr.started_at else None,
                "finished_at": nr.finished_at.isoformat() if nr.finished_at else None,
                "result": nr.result or {},
            }
            for nr in nrs
        ]
    return data


def _validate_nodes(nodes: List[WorkflowNodeIn]) -> None:
    if not nodes:
        return
    orders = [n.order_index for n in nodes]
    if len(orders) != len(set(orders)):
        raise HTTPException(status_code=400, detail="节点 order_index 不可重复")
    for n in nodes:
        if not get_node(n.node_key):
            raise HTTPException(status_code=400, detail=f"未知节点: {n.node_key}")
        if n.on_failure not in ("stop", "continue"):
            raise HTTPException(status_code=400, detail="on_failure 仅支持 stop|continue")


def _replace_nodes(db: Session, workflow_id: int, nodes: List[WorkflowNodeIn]) -> None:
    _validate_nodes(nodes)
    db.query(CollectionWorkflowNode).filter(
        CollectionWorkflowNode.workflow_id == workflow_id
    ).delete()
    for n in sorted(nodes, key=lambda x: x.order_index):
        db.add(
            CollectionWorkflowNode(
                workflow_id=workflow_id,
                order_index=n.order_index,
                node_key=n.node_key,
                display_name=n.display_name or (get_node(n.node_key).name if get_node(n.node_key) else n.node_key),
                params=n.params or {},
                on_failure=n.on_failure or "stop",
                retry_count=max(0, int(n.retry_count or 0)),
                wait_seconds=max(0, int(n.wait_seconds or 0)),
                enabled=bool(n.enabled),
            )
        )


# ---------- Routes ----------


@router.get("/nodes")
async def api_list_nodes():
    """节点注册表（供前端选型）。"""
    return {"success": True, "data": list_nodes_meta()}


@router.get("/active-execution")
async def api_active_execution():
    kind, eid = get_active()
    items = list_active()
    return {
        "success": True,
        "data": {
            "kind": kind,
            "id": eid,
            "busy": is_busy(),
            "active_count": len(items),
            "active": items,
        },
    }


@router.get("")
async def api_list_workflows(db: Session = Depends(get_db)):
    rows = db.query(CollectionWorkflow).order_by(CollectionWorkflow.id.asc()).all()
    # 最近运行状态
    out = []
    for wf in rows:
        item = _workflow_out(wf, include_nodes=False)
        last = (
            db.query(CollectionWorkflowRun)
            .filter(CollectionWorkflowRun.workflow_id == wf.id)
            .order_by(CollectionWorkflowRun.started_at.desc())
            .first()
        )
        item["last_run"] = _run_out(last) if last else None
        item["node_count"] = len(wf.nodes or [])
        out.append(item)
    return {"success": True, "data": out}


@router.post("")
async def api_create_workflow(body: WorkflowCreate, db: Session = Depends(get_db)):
    if body.trigger_type not in ("manual", "cron"):
        raise HTTPException(status_code=400, detail="trigger_type 仅支持 manual|cron")
    _validate_nodes(body.nodes)
    wf = CollectionWorkflow(
        name=body.name.strip(),
        description=body.description,
        enabled=body.enabled,
        trigger_type=body.trigger_type,
        cron_dow=body.cron_dow,
        cron_hour=body.cron_hour,
        cron_minute=body.cron_minute,
        skip_on_holiday=(body.skip_on_holiday or "NONE").upper(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(wf)
    db.flush()
    _replace_nodes(db, wf.id, body.nodes)
    db.commit()
    db.refresh(wf)
    return {"success": True, "data": _workflow_out(wf)}


@router.get("/runs")
async def api_list_runs(
    workflow_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(CollectionWorkflowRun)
    if workflow_id is not None:
        q = q.filter(CollectionWorkflowRun.workflow_id == workflow_id)
    rows = q.order_by(CollectionWorkflowRun.started_at.desc()).limit(min(200, max(1, limit))).all()
    return {"success": True, "data": [_run_out(r) for r in rows]}


@router.get("/runs/{run_id}")
async def api_get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    # 确保加载 node_runs
    _ = run.node_runs
    return {"success": True, "data": _run_out(run, include_nodes=True)}


@router.post("/runs/{run_id}/cancel")
async def api_cancel_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(CollectionWorkflowRun).filter(CollectionWorkflowRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    ok = workflow_engine.cancel(run_id)
    return {"success": True, "data": {"cancelled": ok, "run_id": run_id}}


@router.get("/{workflow_id}")
async def api_get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    return {"success": True, "data": _workflow_out(wf)}


@router.put("/{workflow_id}")
async def api_update_workflow(
    workflow_id: int, body: WorkflowUpdate, db: Session = Depends(get_db)
):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    data = body.dict(exclude_unset=True)
    if "trigger_type" in data and data["trigger_type"] not in ("manual", "cron"):
        raise HTTPException(status_code=400, detail="trigger_type 仅支持 manual|cron")
    if "skip_on_holiday" in data and data["skip_on_holiday"]:
        data["skip_on_holiday"] = str(data["skip_on_holiday"]).upper()
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(wf, k, v)
    wf.updated_at = datetime.now()
    db.commit()
    db.refresh(wf)
    return {"success": True, "data": _workflow_out(wf)}


@router.delete("/{workflow_id}")
async def api_delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    db.delete(wf)
    db.commit()
    return {"success": True, "message": "已删除"}


@router.put("/{workflow_id}/nodes")
async def api_replace_nodes(
    workflow_id: int, body: WorkflowNodesReplace, db: Session = Depends(get_db)
):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    _replace_nodes(db, workflow_id, body.nodes)
    wf.updated_at = datetime.now()
    db.commit()
    db.refresh(wf)
    return {"success": True, "data": _workflow_out(wf)}


@router.post("/{workflow_id}/run")
async def api_run_workflow(
    workflow_id: int,
    body: Optional[WorkflowRunRequest] = None,
    db: Session = Depends(get_db),
):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    try:
        run_id = workflow_engine.start(
            workflow_id,
            trigger_source="manual",
            override_params=(body.override_params if body else None),
            background=True,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "data": {"run_id": run_id}}


@router.post("/{workflow_id}/duplicate")
async def api_duplicate_workflow(workflow_id: int, db: Session = Depends(get_db)):
    wf = db.query(CollectionWorkflow).filter(CollectionWorkflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="流程不存在")
    new_wf = CollectionWorkflow(
        name=f"{wf.name} (副本)",
        description=wf.description,
        enabled=False,
        trigger_type="manual",
        cron_dow=wf.cron_dow,
        cron_hour=wf.cron_hour,
        cron_minute=wf.cron_minute,
        skip_on_holiday=wf.skip_on_holiday,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(new_wf)
    db.flush()
    for n in sorted(wf.nodes or [], key=lambda x: x.order_index):
        db.add(
            CollectionWorkflowNode(
                workflow_id=new_wf.id,
                order_index=n.order_index,
                node_key=n.node_key,
                display_name=n.display_name,
                params=dict(n.params or {}),
                on_failure=n.on_failure,
                retry_count=n.retry_count,
                wait_seconds=n.wait_seconds,
                enabled=n.enabled,
            )
        )
    db.commit()
    db.refresh(new_wf)
    return {"success": True, "data": _workflow_out(new_wf)}
