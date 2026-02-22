"""
Memory endpoint — PS-SHA∞ hash-chain memory store and recall.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
import httpx
import os

router = APIRouter(prefix="/memory", tags=["memory"])
GATEWAY = os.getenv("BLACKROAD_GATEWAY_URL", "http://127.0.0.1:8787")


class MemoryStoreRequest(BaseModel):
    content: str
    type: Literal["fact", "observation", "inference", "commitment"] = "fact"
    truth_state: Literal[1, 0, -1] = 1
    agent_id: str | None = None


class MemoryRecallRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    type: str | None = None


@router.post("/store", status_code=201)
async def store_memory(req: MemoryStoreRequest):
    """Store a new memory entry in PS-SHA∞ journal."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{GATEWAY}/v1/memory/store", json=req.model_dump())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/recall")
async def recall_memory(req: MemoryRecallRequest):
    """Search memory by keyword."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{GATEWAY}/v1/memory/recall", json=req.model_dump())
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/verify")
async def verify_chain():
    """Verify PS-SHA∞ memory chain integrity."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{GATEWAY}/v1/memory/verify")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/context")
async def export_context(max_entries: int = 20):
    """Export recent memory as AI context string."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{GATEWAY}/v1/memory/context",
                params={"max_entries": max_entries},
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
