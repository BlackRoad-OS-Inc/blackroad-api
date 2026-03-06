"""Cloudflare integration endpoint (issue #6).

Exposes Cloudflare Worker deploy status, Pages deployments,
and R2 storage metrics via /api/cloudflare.
Requires CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID environment variables.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/cloudflare", tags=["cloudflare"])

CF_API = "https://api.cloudflare.com/client/v4"


def _headers() -> dict:
    token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    if not token:
        raise HTTPException(503, "CLOUDFLARE_API_TOKEN not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _account_id() -> str:
    acct = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if not acct:
        raise HTTPException(503, "CLOUDFLARE_ACCOUNT_ID not configured")
    return acct


@router.get("/workers")
async def list_workers() -> dict:
    """List Cloudflare Workers and their deploy status."""
    acct = _account_id()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CF_API}/accounts/{acct}/workers/scripts",
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            workers = []
            for w in data.get("result", []):
                workers.append({
                    "id": w.get("id"),
                    "name": w.get("id"),
                    "modified_on": w.get("modified_on"),
                    "created_on": w.get("created_on"),
                })
            return {"workers": workers, "total": len(workers)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Cloudflare API error: {e}")


@router.get("/pages")
async def list_pages_projects(
    per_page: int = Query(25, le=100),
) -> dict:
    """List Cloudflare Pages deployments."""
    acct = _account_id()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CF_API}/accounts/{acct}/pages/projects",
                headers=_headers(),
                params={"per_page": per_page},
            )
            resp.raise_for_status()
            data = resp.json()
            projects = []
            for p in data.get("result", []):
                latest = p.get("latest_deployment", {})
                projects.append({
                    "name": p.get("name"),
                    "subdomain": p.get("subdomain"),
                    "production_branch": p.get("production_branch"),
                    "latest_deployment": {
                        "id": latest.get("id"),
                        "url": latest.get("url"),
                        "environment": latest.get("environment"),
                        "created_on": latest.get("created_on"),
                    } if latest else None,
                })
            return {"projects": projects, "total": len(projects)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Cloudflare API error: {e}")


@router.get("/r2")
async def list_r2_buckets() -> dict:
    """List R2 storage buckets and basic metrics."""
    acct = _account_id()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CF_API}/accounts/{acct}/r2/buckets",
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            buckets = []
            for b in data.get("result", {}).get("buckets", []):
                buckets.append({
                    "name": b.get("name"),
                    "creation_date": b.get("creation_date"),
                    "location": b.get("location"),
                })
            return {"buckets": buckets, "total": len(buckets)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Cloudflare API error: {e}")


@router.get("/health")
async def cloudflare_health() -> dict:
    """Check connectivity to Cloudflare API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{CF_API}/user/tokens/verify",
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": "ok" if data.get("success") else "degraded",
                "provider": "cloudflare",
            }
    except (httpx.HTTPError, HTTPException):
        return {"status": "degraded", "provider": "cloudflare", "error": "Unable to verify token"}
