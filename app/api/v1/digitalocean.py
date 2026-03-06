"""DigitalOcean Droplet management API (issue #7).

Provides endpoints to list, snapshot, and manage DigitalOcean droplets.
Requires DIGITALOCEAN_TOKEN environment variable.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/digitalocean", tags=["digitalocean"])

DO_API = "https://api.digitalocean.com/v2"


def _headers() -> dict:
    token = os.getenv("DIGITALOCEAN_TOKEN", "")
    if not token:
        raise HTTPException(503, "DIGITALOCEAN_TOKEN not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@router.get("/droplets")
async def list_droplets(
    per_page: int = Query(25, le=200),
    page: int = Query(1, ge=1),
) -> dict:
    """List all DigitalOcean droplets."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{DO_API}/droplets",
                headers=_headers(),
                params={"per_page": per_page, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            droplets = []
            for d in data.get("droplets", []):
                networks = d.get("networks", {})
                ipv4 = [n["ip_address"] for n in networks.get("v4", []) if n.get("type") == "public"]
                droplets.append({
                    "id": d["id"],
                    "name": d["name"],
                    "status": d["status"],
                    "region": d.get("region", {}).get("slug"),
                    "size": d.get("size_slug"),
                    "image": d.get("image", {}).get("slug"),
                    "ip_address": ipv4[0] if ipv4 else None,
                    "created_at": d.get("created_at"),
                    "tags": d.get("tags", []),
                })
            meta = data.get("meta", {}).get("total", len(droplets))
            return {"droplets": droplets, "total": meta}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"DigitalOcean API error: {e}")


@router.get("/droplets/{droplet_id}")
async def get_droplet(droplet_id: int) -> dict:
    """Get details for a specific droplet."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{DO_API}/droplets/{droplet_id}",
                headers=_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("droplet", {})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"DigitalOcean API error: {e}")


@router.post("/droplets/{droplet_id}/snapshot", status_code=201)
async def snapshot_droplet(droplet_id: int, name: str | None = None) -> dict:
    """Create a snapshot of a DigitalOcean droplet."""
    snapshot_name = name or f"blackroad-snap-{droplet_id}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{DO_API}/droplets/{droplet_id}/actions",
                headers=_headers(),
                json={"type": "snapshot", "name": snapshot_name},
            )
            resp.raise_for_status()
            action = resp.json().get("action", {})
            return {
                "action_id": action.get("id"),
                "droplet_id": droplet_id,
                "status": action.get("status"),
                "type": "snapshot",
                "name": snapshot_name,
            }
    except httpx.HTTPError as e:
        raise HTTPException(502, f"DigitalOcean API error: {e}")


@router.get("/snapshots")
async def list_snapshots(
    per_page: int = Query(25, le=200),
) -> dict:
    """List all droplet snapshots."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{DO_API}/snapshots",
                headers=_headers(),
                params={"per_page": per_page, "resource_type": "droplet"},
            )
            resp.raise_for_status()
            data = resp.json()
            snapshots = []
            for s in data.get("snapshots", []):
                snapshots.append({
                    "id": s["id"],
                    "name": s["name"],
                    "regions": s.get("regions", []),
                    "size_gigabytes": s.get("size_gigabytes"),
                    "created_at": s.get("created_at"),
                })
            return {"snapshots": snapshots, "total": len(snapshots)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"DigitalOcean API error: {e}")
