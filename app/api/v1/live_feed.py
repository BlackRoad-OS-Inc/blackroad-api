"""WebSocket/SSE endpoint for live agent feed (issue #5).

Provides real-time agent status streaming for the web dashboard.
SSE for browser compatibility, WebSocket for native clients.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.database import get_db

router = APIRouter(tags=["live-feed"])


def _agent_snapshot() -> list[dict]:
    """Current state of all agents."""
    db = get_db()
    rows = db.execute("SELECT * FROM agents ORDER BY name").fetchall()
    agents = []
    for r in rows:
        a = dict(r)
        a["capabilities"] = json.loads(a.get("capabilities") or "[]")
        agents.append(a)
    return agents


# ── SSE endpoint ─────────────────────────────────────────────────────────────

@router.get("/feed/agents")
async def agent_feed_sse(request: Request) -> StreamingResponse:
    """Server-Sent Events stream of agent status updates.

    Browsers can connect via EventSource:
        const es = new EventSource('/v1/feed/agents');
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            agents = _agent_snapshot()
            data = json.dumps({"agents": agents, "timestamp": int(time.time())})
            yield f"data: {data}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── WebSocket endpoint ───────────────────────────────────────────────────────

@router.websocket("/ws/agents")
async def agent_feed_ws(websocket: WebSocket):
    """WebSocket stream of agent status updates for native clients.

    Connect via ws://host/v1/ws/agents
    Sends JSON frames every 2 seconds with current agent state.
    Client can send {"interval": N} to change the push interval (1-30s).
    """
    await websocket.accept()
    interval = 2.0
    try:
        while True:
            agents = _agent_snapshot()
            await websocket.send_json({
                "agents": agents,
                "timestamp": int(time.time()),
            })
            # Non-blocking wait: check for client messages while sleeping
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=interval)
                if "interval" in msg:
                    interval = max(1.0, min(30.0, float(msg["interval"])))
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
