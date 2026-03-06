"""Railway integration endpoints (issue #2).

Provides deployment management, service listing, log tailing,
and health aggregation for Railway-hosted services.
Requires RAILWAY_TOKEN environment variable.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/railway", tags=["railway"])

RAILWAY_API = "https://backboard.railway.app/graphql/v2"


def _headers() -> dict:
    token = os.getenv("RAILWAY_TOKEN", "")
    if not token:
        raise HTTPException(503, "RAILWAY_TOKEN not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _gql(query: str, variables: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            RAILWAY_API,
            json={"query": query, "variables": variables or {}},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise HTTPException(502, f"Railway API error: {data['errors']}")
        return data.get("data", {})


@router.get("/services")
async def list_services() -> dict:
    """List all Railway services and their status."""
    query = """
    query {
      me {
        projects { edges { node {
          id name
          services { edges { node { id name } } }
        } } }
      }
    }
    """
    try:
        data = await _gql(query)
        projects = data.get("me", {}).get("projects", {}).get("edges", [])
        services = []
        for proj in projects:
            p = proj["node"]
            for svc in p.get("services", {}).get("edges", []):
                s = svc["node"]
                services.append({
                    "id": s["id"],
                    "name": s["name"],
                    "project": p["name"],
                    "project_id": p["id"],
                })
        return {"services": services, "total": len(services)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Railway connection error: {e}")


@router.post("/deploy")
async def trigger_deploy(
    service_id: str,
    environment_id: Optional[str] = None,
) -> dict:
    """Trigger a deployment for a Railway service."""
    query = """
    mutation($serviceId: String!) {
      serviceInstanceRedeploy(serviceId: $serviceId)
    }
    """
    try:
        await _gql(query, {"serviceId": service_id})
        return {"ok": True, "service_id": service_id, "status": "deploying"}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Railway deploy error: {e}")


@router.get("/logs/{service_id}")
async def tail_logs(
    service_id: str,
    limit: int = Query(100, le=500),
) -> dict:
    """Tail logs for a Railway service."""
    query = """
    query($serviceId: String!, $limit: Int!) {
      deploymentLogs(serviceId: $serviceId, limit: $limit) {
        message timestamp severity
      }
    }
    """
    try:
        data = await _gql(query, {"serviceId": service_id, "limit": limit})
        logs = data.get("deploymentLogs", [])
        return {"service_id": service_id, "logs": logs, "count": len(logs)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Railway logs error: {e}")


@router.get("/health")
async def aggregate_health() -> dict:
    """Aggregate health status across all Railway services."""
    try:
        query = """
        query {
          me {
            projects { edges { node {
              id name
              services { edges { node { id name } } }
            } } }
          }
        }
        """
        data = await _gql(query)
        projects = data.get("me", {}).get("projects", {}).get("edges", [])
        total = sum(
            len(p["node"].get("services", {}).get("edges", []))
            for p in projects
        )
        return {
            "status": "ok",
            "provider": "railway",
            "projects": len(projects),
            "services": total,
        }
    except HTTPException:
        return {"status": "degraded", "provider": "railway", "error": "Unable to reach Railway API"}
