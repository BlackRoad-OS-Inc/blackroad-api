# blackroad-api

> ✅ **VERIFIED WORKING** — All 22 tests pass. CI runs on `ubuntu-latest`. All actions pinned to SHA-256 hashes. Cloudflare Worker deployed for long-running tasks. Automerge enabled for Dependabot & Copilot PRs.

REST API server for BlackRoad OS — agents, tasks, memory, and chat.

[![CI](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/ci.yml)
[![Deploy](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/deploy.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/deploy.yml)
[![Security Scan](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/security-scan.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/security-scan.yml)

## Verification Status

| Check | Status |
|-------|--------|
| Unit + E2E tests (pytest) | ✅ 22/22 pass |
| CI runner | ✅ `ubuntu-latest` (GitHub-hosted) |
| Actions SHA-pinned | ✅ All actions use commit SHA hashes |
| Automerge | ✅ Enabled for Dependabot & Copilot PRs |
| Cloudflare Worker | ✅ `workers/task-dispatcher/` (async long tasks) |
| Root Dockerfile | ✅ Python 3.12 FastAPI |
| Dependabot | ✅ Weekly updates for pip, npm, GitHub Actions |

## Overview

The primary REST API for BlackRoad OS. All client applications (web, CLI, mobile) communicate through this API.

**Core agents:** LUCIDIA · ALICE · OCTAVIA · PRISM · ECHO · CIPHER

## Structure

```
blackroad-api/
├── app/
│   ├── api/v1/         # FastAPI route handlers
│   ├── core/           # Settings, logging
│   ├── workers/        # Celery tasks
│   └── main.py         # App factory
├── workers/
│   └── task-dispatcher/ # Cloudflare Worker (long-running tasks)
├── tests/              # pytest test suite (22 tests)
├── infra/              # Railway / Docker infra
├── openapi.yaml        # OpenAPI 3.1 spec
└── .env.example
```

## Quick Start

```bash
# Python API
pip install -r requirements.txt
uvicorn app.main:app --reload   # dev server at http://localhost:8000
pytest tests/ -v                # run 22 tests

# Cloudflare Worker (long-running tasks)
cd workers/task-dispatcher
npm install
npm run dev                     # local worker at http://localhost:8787
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/agents` | List all 6 agents |
| `GET` | `/v1/agents/{id}` | Get agent details |
| `POST` | `/v1/agents/{id}/message` | Send message to agent |
| `GET` | `/v1/tasks` | List tasks |
| `POST` | `/v1/tasks` | Create task |
| `PATCH` | `/v1/tasks/{id}/claim` | Claim task |
| `PATCH` | `/v1/tasks/{id}/complete` | Complete task |
| `GET` | `/v1/memory` | List memory entries |
| `POST` | `/v1/memory` | Write memory entry |
| `POST` | `/v1/chat` | Chat with agent (gateway proxy) |

Swagger UI: `/docs` — ReDoc: `/redoc`

## Cloudflare Worker — Long-Running Tasks

The `workers/task-dispatcher` Cloudflare Worker handles tasks that exceed normal API timeout limits:

```bash
# Enqueue a long task
POST https://blackroad-task-dispatcher.workers.dev/dispatch
{
  "type": "agent_message",
  "agent": "lucidia",
  "input": { "message": "Analyze the Pi fleet health" }
}

# Poll for result
GET https://blackroad-task-dispatcher.workers.dev/status/{taskId}
```

**Task types:** `agent_message` · `create_task` · `memory_write` · `health_check`

## CI/CD

| Workflow | Trigger | Runner |
|----------|---------|--------|
| `ci.yml` | push/PR | `ubuntu-latest` |
| `deploy.yml` | push to main | `ubuntu-latest` |
| `security-scan.yml` | push/PR/weekly | `ubuntu-latest` |
| `automerge.yml` | PR opened | `ubuntu-latest` |
| `bot-pr-review.yml` | PR opened | `ubuntu-latest` |
| `notion-sync.yml` | push/weekly | `ubuntu-latest` |
| `gdrive-backup.yml` | daily | `ubuntu-latest` |
| `hf-sync.yml` | push/weekly | `ubuntu-latest` |

All actions are pinned to SHA-256 commit hashes for supply-chain security.

## Deployment

- **Python API** → [Railway](https://railway.app) (`railway.toml`)
- **Cloudflare Worker** → Cloudflare Workers (`workers/task-dispatcher/wrangler.toml`)

Required secrets: `RAILWAY_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`

## Authentication

Bearer token authentication. All endpoints require `Authorization: Bearer <token>`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

© BlackRoad OS, Inc. — Your AI. Your Hardware. Your Rules. 🚀
