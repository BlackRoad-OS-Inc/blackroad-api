"""
Tasks endpoint — BlackRoad task marketplace.
Create, claim, complete, and list tasks across the agent mesh.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
import os

router = APIRouter(prefix="/tasks", tags=["tasks"])
GATEWAY = os.getenv("BLACKROAD_GATEWAY_URL", "http://127.0.0.1:8787")


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    tags: list[str] = []
    required_skills: list[str] = []
    assigned_to: str | None = None


class TaskComplete(BaseModel):
    result: str = ""
    summary: str = ""


class TaskClaim(BaseModel):
    agent_id: str


@router.get("")
async def list_tasks(
    status: str | None = Query(None, description="Filter by status"),
    priority: str | None = Query(None),
    tag: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """List tasks from the marketplace."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{GATEWAY}/v1/tasks",
                params={"status": status, "priority": priority, "tag": tag, "limit": limit},
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError:
        # Return empty list if gateway offline
        return {"tasks": [], "total": 0, "gateway": "offline"}


@router.post("", status_code=201)
async def create_task(task: TaskCreate):
    """Post a new task to the marketplace."""
    payload = {
        "task_id": str(uuid.uuid4())[:8],
        "posted_at": datetime.utcnow().isoformat(),
        "status": "available",
        **task.model_dump(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{GATEWAY}/v1/tasks", json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError:
        # Return created payload if gateway offline
        return {"task": payload, "note": "queued (gateway offline)"}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{GATEWAY}/v1/tasks/{task_id}")
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{task_id}/claim")
async def claim_task(task_id: str, req: TaskClaim):
    """Claim a task for an agent to work on."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{GATEWAY}/v1/tasks/{task_id}/claim",
                json={"agent_id": req.agent_id, "claimed_at": datetime.utcnow().isoformat()},
            )
            if r.status_code == 409:
                raise HTTPException(status_code=409, detail="Task already claimed")
            r.raise_for_status()
            return r.json()
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, req: TaskComplete):
    """Mark a task as complete with a result."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{GATEWAY}/v1/tasks/{task_id}/complete",
                json={
                    "result": req.result,
                    "summary": req.summary,
                    "completed_at": datetime.utcnow().isoformat(),
                },
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """Cancel an available task."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(f"{GATEWAY}/v1/tasks/{task_id}")
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="Task not found")
            r.raise_for_status()
            return {"status": "cancelled", "task_id": task_id}
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
