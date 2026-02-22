"""v1 API router — agents, memory, tasks, chat, health."""

from time import perf_counter
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel

router = APIRouter()


# ──────────────────────────────────────────────
# Health & Version
# ──────────────────────────────────────────────

@router.get("/health")
def health(request: Request) -> dict:
    """Return liveness information with uptime."""
    start_time: float = request.app.state.start_time
    uptime = perf_counter() - start_time
    return {"status": "ok", "uptime": round(uptime, 3)}


@router.get("/version")
def version(request: Request) -> dict:
    """Return the running application version metadata."""
    app_settings = request.app.state.settings
    return {"version": app_settings.version, "commit": app_settings.git_sha}


# ──────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────

@router.get("/agents")
async def list_agents(request: Request) -> dict:
    """List available agents from the gateway."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{gw_url}/agents")
            return resp.json()
    except Exception as e:
        return {"agents": [], "error": str(e)}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request) -> dict:
    """Get a specific agent by ID."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{gw_url}/agents/{agent_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Agent not found")
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ──────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────

class MemoryEntry(BaseModel):
    content: str
    type: str = "fact"
    truth_state: int = 1
    metadata: Optional[dict] = None


@router.post("/memory")
async def store_memory(entry: MemoryEntry, request: Request) -> dict:
    """Store a memory entry in the PS-SHA∞ journal."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{gw_url}/memory", json=entry.dict())
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


@router.get("/memory")
async def recall_memory(query: str, limit: int = 10, request: Request = None) -> dict:
    """Recall memories matching query."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{gw_url}/memory", params={"query": query, "limit": limit})
            return resp.json()
    except Exception as e:
        return {"memories": [], "error": str(e)}


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    agent: str = "lucidia"
    model: str = "qwen2.5:7b"
    session_id: Optional[str] = None
    use_memory: bool = True


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request) -> dict:
    """Send a message to an agent via the gateway."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{gw_url}/chat", json=payload.dict())
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ──────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"
    assigned_to: Optional[str] = None
    tags: list[str] = []


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, request: Request = None) -> dict:
    """List tasks from the task marketplace."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            params = {"status": status} if status else {}
            resp = await client.get(f"{gw_url}/tasks", params=params)
            return resp.json()
    except Exception as e:
        return {"tasks": [], "error": str(e)}


@router.post("/tasks")
async def create_task(task: TaskCreate, request: Request) -> dict:
    """Create a new task in the marketplace."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{gw_url}/tasks", json=task.dict())
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.patch("/tasks/{task_id}/claim")
async def claim_task(task_id: str, request: Request) -> dict:
    """Claim a task for execution."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.patch(f"{gw_url}/tasks/{task_id}/claim")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.patch("/tasks/{task_id}/complete")
async def complete_task(task_id: str, summary: str = Body(..., embed=True),
                        request: Request = None) -> dict:
    """Mark a task as complete with a summary."""
    import httpx
    gw_url = getattr(request.app.state.settings, "gateway_url", "http://127.0.0.1:8787")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.patch(
                f"{gw_url}/tasks/{task_id}/complete",
                json={"summary": summary}
            )
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
