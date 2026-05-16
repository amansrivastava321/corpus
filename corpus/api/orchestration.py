"""Orchestration API — multi-product workflow coordination."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


class CreateWorkflowRequest(BaseModel):
    name: str
    initiating_product: str
    subject: dict
    required_capabilities: list[str] | None = None
    tasks: list[dict] | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    initiating_product: str
    status: str
    subject: dict
    tasks: list[dict]
    synthesis: dict | None
    created_at: str
    started_at: str | None
    completed_at: str | None


def _wf_to_resp(workflow) -> WorkflowResponse:
    d = workflow.to_dict()
    return WorkflowResponse(**{k: d[k] for k in WorkflowResponse.model_fields})


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(req: CreateWorkflowRequest, request: Request) -> WorkflowResponse:
    container = request.app.state.container
    workflow = await container.workflow_engine.create_workflow(
        name=req.name,
        initiating_product=req.initiating_product,
        subject=req.subject,
        required_capabilities=req.required_capabilities,
        tasks=req.tasks,
    )
    return _wf_to_resp(workflow)


@router.post("/workflows/{workflow_id}/start", response_model=WorkflowResponse)
async def start_workflow(workflow_id: str, request: Request) -> WorkflowResponse:
    container = request.app.state.container
    try:
        workflow = await container.workflow_engine.start_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _wf_to_resp(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, request: Request) -> WorkflowResponse:
    container = request.app.state.container
    workflow = await container.workflow_engine.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _wf_to_resp(workflow)


@router.get("/workflows/{workflow_id}/state")
async def get_workflow_state(workflow_id: str, request: Request) -> dict:
    container = request.app.state.container
    workflow = await container.workflow_engine.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "id": workflow.id,
        "status": workflow.status.value,
        "task_count": len(workflow.tasks),
        "synthesis": workflow.synthesis.to_dict() if workflow.synthesis else None,
    }


@router.post("/workflows/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(workflow_id: str, request: Request) -> WorkflowResponse:
    container = request.app.state.container
    try:
        workflow = await container.workflow_engine.cancel_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _wf_to_resp(workflow)


@router.get("/workflows")
async def list_workflows(
    request: Request,
    product: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    container = request.app.state.container
    workflows = await container.workflow_engine.list_workflows(
        initiating_product=product, status=status, limit=limit
    )
    return {"workflows": [w.to_dict() for w in workflows], "count": len(workflows)}


@router.get("/products/graph")
async def get_product_graph(request: Request) -> dict:
    container = request.app.state.container
    return container.product_graph.to_dict()
