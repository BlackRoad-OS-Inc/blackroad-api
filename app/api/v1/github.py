"""GitHub integration endpoints (issue #3).

Provides repository listing, workflow status, issue creation,
and pull request listing for the configured GitHub organization.
Requires GITHUB_TOKEN environment variable.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/github", tags=["github"])

GH_API = "https://api.github.com"
GH_ORG = os.getenv("GITHUB_ORG", "BlackRoad-OS-Inc")


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise HTTPException(503, "GITHUB_TOKEN not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@router.get("/repos")
async def list_repos(
    per_page: int = Query(30, le=100),
    page: int = Query(1, ge=1),
) -> dict:
    """List organization repos with latest commit info."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GH_API}/orgs/{GH_ORG}/repos",
                headers=_headers(),
                params={"per_page": per_page, "page": page, "sort": "updated"},
            )
            resp.raise_for_status()
            repos = []
            for r in resp.json():
                repos.append({
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "description": r.get("description"),
                    "default_branch": r.get("default_branch"),
                    "updated_at": r.get("updated_at"),
                    "language": r.get("language"),
                    "open_issues": r.get("open_issues_count", 0),
                    "url": r.get("html_url"),
                })
            return {"repos": repos, "total": len(repos), "org": GH_ORG}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"GitHub API error: {e}")


@router.get("/actions/{repo}")
async def get_workflow_status(repo: str) -> dict:
    """Get workflow execution status for a specific repository."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GH_API}/repos/{GH_ORG}/{repo}/actions/runs",
                headers=_headers(),
                params={"per_page": 10},
            )
            resp.raise_for_status()
            data = resp.json()
            runs = []
            for r in data.get("workflow_runs", []):
                runs.append({
                    "id": r["id"],
                    "name": r.get("name"),
                    "status": r["status"],
                    "conclusion": r.get("conclusion"),
                    "branch": r.get("head_branch"),
                    "created_at": r.get("created_at"),
                    "url": r.get("html_url"),
                })
            return {"repo": repo, "runs": runs, "total_count": data.get("total_count", 0)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"GitHub API error: {e}")


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    body: str = ""
    repo: str = Field(..., min_length=1)
    labels: list[str] = []
    assignees: list[str] = []


@router.post("/issues", status_code=201)
async def create_issue(issue: IssueCreate) -> dict:
    """Create a new issue in a repository."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GH_API}/repos/{GH_ORG}/{issue.repo}/issues",
                headers=_headers(),
                json={
                    "title": issue.title,
                    "body": issue.body,
                    "labels": issue.labels,
                    "assignees": issue.assignees,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data["id"],
                "number": data["number"],
                "title": data["title"],
                "url": data["html_url"],
                "state": data["state"],
            }
    except httpx.HTTPError as e:
        raise HTTPException(502, f"GitHub API error: {e}")


@router.get("/prs")
async def list_pull_requests(
    repo: Optional[str] = Query(None),
    state: str = Query("open"),
    per_page: int = Query(30, le=100),
) -> dict:
    """List open pull requests across the organization or for a specific repo."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if repo:
                resp = await client.get(
                    f"{GH_API}/repos/{GH_ORG}/{repo}/pulls",
                    headers=_headers(),
                    params={"state": state, "per_page": per_page},
                )
                resp.raise_for_status()
                prs = _format_prs(resp.json())
                return {"repo": repo, "prs": prs, "total": len(prs)}
            else:
                # Search across org
                resp = await client.get(
                    f"{GH_API}/search/issues",
                    headers=_headers(),
                    params={
                        "q": f"org:{GH_ORG} is:pr is:{state}",
                        "per_page": per_page,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                prs = []
                for item in data.get("items", []):
                    prs.append({
                        "number": item["number"],
                        "title": item["title"],
                        "state": item["state"],
                        "user": item["user"]["login"],
                        "created_at": item["created_at"],
                        "url": item["html_url"],
                        "repo": item["repository_url"].split("/")[-1],
                    })
                return {"prs": prs, "total_count": data.get("total_count", 0), "org": GH_ORG}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"GitHub API error: {e}")


def _format_prs(raw: list) -> list:
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "user": pr["user"]["login"],
            "created_at": pr["created_at"],
            "url": pr["html_url"],
            "draft": pr.get("draft", False),
        }
        for pr in raw
    ]
