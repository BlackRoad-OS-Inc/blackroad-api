"""BlackRoad API — Tasks Router"""
from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .database import db

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    agent: str
    priority: int = 5
    payload: dict = {}


class TaskUpdate(BaseModel):
    status: str | None = None
    result: str | None = None


@router.get("/")
async def list_tasks(status: str | None = None, agent: str | None = None, limit: int = 50):
    rows = db.execute(
        "SELECT * FROM tasks WHERE 1=1"
        + (" AND status = ?" if status else "")
        + (" AND agent = ?" if agent else "")
        + " ORDER BY created_at DESC LIMIT ?",
        [x for x in [status, agent, limit] if x is not None]
    ).fetchall()
    return {"tasks": [dict(r) for r in rows], "count": len(rows)}


@router.post("/", status_code=201)
async def create_task(body: TaskCreate):
    task_id = f"task_{int(time.time() * 1000)}"
    db.execute(
        "INSERT INTO tasks (id, title, agent, priority, payload, status, created_at) VALUES (?,?,?,?,?,?,?)",
        [task_id, body.title, body.agent, body.priority, str(body.payload), "pending", int(time.time())]
    )
    db.commit()
    return {"task_id": task_id, "status": "pending"}


@router.get("/{task_id}")
async def get_task(task_id: str):
    row = db.execute("SELECT * FROM tasks WHERE id = ?", [task_id]).fetchone()
    if not row:
        raise HTTPException(404, f"Task {task_id} not found")
    return dict(row)


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    row = db.execute("SELECT id FROM tasks WHERE id = ?", [task_id]).fetchone()
    if not row:
        raise HTTPException(404, f"Task {task_id} not found")
    if body.status:
        db.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                   [body.status, int(time.time()), task_id])
    if body.result:
        db.execute("UPDATE tasks SET result = ? WHERE id = ?", [body.result, task_id])
    db.commit()
    return {"task_id": task_id, "updated": True}


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str):
    db.execute("DELETE FROM tasks WHERE id = ?", [task_id])
    db.commit()
