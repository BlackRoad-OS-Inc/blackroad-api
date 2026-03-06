# blackroad-api

> **39 tests passing** — CI on `ubuntu-latest`. All actions SHA-256 pinned. Cloudflare Worker deployed. JWT + API key auth. SSE/WebSocket live feed. Integration endpoints for Railway, GitHub, Cloudflare, DigitalOcean, and RoadChain ledger.

REST API server for BlackRoad OS — agents, tasks, memory, chat, and infrastructure integrations.

[![CI](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/ci.yml)
[![Deploy](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/deploy.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/deploy.yml)
[![Security Scan](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/security-scan.yml/badge.svg)](https://github.com/BlackRoad-OS-Inc/blackroad-api/actions/workflows/security-scan.yml)

## Verification Status

| Check | Status |
|-------|--------|
| Unit + E2E + integration tests (pytest) | 39 pass |
| CI runner | `ubuntu-latest` (GitHub-hosted) |
| Actions SHA-pinned | All actions use commit SHA hashes |
| Authentication | JWT Bearer + X-BR-KEY API key |
| Rate limiting | Per agent/user via slowapi |
| Live feed | SSE + WebSocket for agent status |
| Automerge | Enabled for Dependabot & Copilot PRs |
| Cloudflare Worker | `workers/task-dispatcher/` (async long tasks) |
| Root Dockerfile | Python 3.12 FastAPI |
| Dependabot | Weekly updates for pip, npm, GitHub Actions |

## Overview

The primary REST API for BlackRoad OS. All client applications (web, CLI, mobile) communicate through this API.

**Core agents:** LUCIDIA · ALICE · OCTAVIA · PRISM · ECHO · CIPHER

## Structure

```
blackroad-api/
├── app/
│   ├── api/v1/             # FastAPI route handlers
│   │   ├── router.py       # Core: agents, tasks, memory, chat
│   │   ├── railway.py      # Railway integration (issue #2)
│   │   ├── github.py       # GitHub integration (issue #3)
│   │   ├── roadchain.py    # RoadChain ledger (issue #4)
│   │   ├── live_feed.py    # SSE/WebSocket feed (issue #5)
│   │   ├── cloudflare.py   # Cloudflare integration (issue #6)
│   │   └── digitalocean.py # DigitalOcean integration (issue #7)
│   ├── middleware/
│   │   ├── auth.py         # X-BR-KEY authentication
│   │   ├── jwt_auth.py     # JWT + API key auth (issue #1)
│   │   └── response_headers.py
│   ├── core/               # Settings, logging
│   ├── workers/            # Celery tasks
│   └── main.py             # App factory
├── workers/
│   └── task-dispatcher/    # Cloudflare Worker (long-running tasks)
├── tests/                  # pytest test suite (39 tests)
├── infra/                  # Railway / Docker infra
├── openapi.yaml            # OpenAPI 3.1 spec
└── .env.example
```

## Quick Start

```bash
# Python API
pip install -r requirements.txt
uvicorn app.main:app --reload   # dev server at http://localhost:8000
pytest tests/ -v                # run 39 tests

# Cloudflare Worker (long-running tasks)
cd workers/task-dispatcher
npm install
npm run dev                     # local worker at http://localhost:8787
```

## API Endpoints

### Core (v1)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/agents` | List all 6 agents |
| `GET` | `/v1/agents/{id}` | Get agent details |
| `POST` | `/v1/agents/{id}/message` | Send message to agent |
| `POST` | `/v1/agents/{id}/wake` | Wake agent |
| `POST` | `/v1/agents/{id}/sleep` | Sleep agent |
| `GET` | `/v1/tasks` | List tasks |
| `POST` | `/v1/tasks` | Create task |
| `GET` | `/v1/tasks/{id}` | Get task details |
| `PATCH` | `/v1/tasks/{id}/claim` | Claim task |
| `PATCH` | `/v1/tasks/{id}/complete` | Complete task |
| `GET` | `/v1/memory` | List memory entries |
| `POST` | `/v1/memory` | Write memory entry |
| `GET` | `/v1/memory/{hash}` | Get memory by hash |
| `POST` | `/v1/chat` | Chat with agent (gateway proxy) |

### Live Feed (issue #5)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/feed/agents` | SSE stream of agent status |
| `WS` | `/v1/ws/agents` | WebSocket agent status feed |

### Railway Integration (issue #2)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/railway/services` | List Railway services + status |
| `POST` | `/v1/railway/deploy` | Trigger deployment |
| `GET` | `/v1/railway/logs/{serviceId}` | Tail service logs |
| `GET` | `/v1/railway/health` | Aggregate health |

### GitHub Integration (issue #3)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/github/repos` | List org repos with latest commit |
| `GET` | `/v1/github/actions/{repo}` | Workflow execution status |
| `POST` | `/v1/github/issues` | Create issue |
| `GET` | `/v1/github/prs` | List open pull requests |

### RoadChain Ledger (issue #4)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/roadchain/transactions` | Submit signed transaction |
| `GET` | `/v1/roadchain/transactions` | Query ledger |
| `GET` | `/v1/roadchain/transactions/{id}` | Get transaction |
| `GET` | `/v1/roadchain/audit` | Audit trail |

### Cloudflare Integration (issue #6)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/cloudflare/workers` | List Workers + deploy status |
| `GET` | `/v1/cloudflare/pages` | Pages deployments |
| `GET` | `/v1/cloudflare/r2` | R2 storage buckets |
| `GET` | `/v1/cloudflare/health` | CF API connectivity |

### DigitalOcean Integration (issue #7)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/digitalocean/droplets` | List droplets |
| `GET` | `/v1/digitalocean/droplets/{id}` | Get droplet details |
| `POST` | `/v1/digitalocean/droplets/{id}/snapshot` | Snapshot droplet |
| `GET` | `/v1/digitalocean/snapshots` | List snapshots |

Swagger UI: `/docs` — ReDoc: `/redoc`

## Authentication (issue #1)

The API supports two authentication methods:

1. **JWT Bearer token** — Pass `Authorization: Bearer <token>` header
2. **API key** — Pass `X-BR-KEY: <key>` header

In development mode (`NODE_ENV=development`), unauthenticated access is allowed.

Rate limiting is enforced at 100 requests/minute per API key or IP address.

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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Production | Secret for JWT token signing |
| `API_KEYS` | No | Comma-separated API keys for X-BR-KEY auth |
| `RAILWAY_TOKEN` | For Railway integration | Railway API token |
| `GITHUB_TOKEN` | For GitHub integration | GitHub personal access token |
| `GITHUB_ORG` | No | GitHub organization (default: BlackRoad-OS-Inc) |
| `CLOUDFLARE_API_TOKEN` | For CF integration | Cloudflare API token |
| `CLOUDFLARE_ACCOUNT_ID` | For CF integration | Cloudflare account ID |
| `DIGITALOCEAN_TOKEN` | For DO integration | DigitalOcean API token |
| `BLACKROAD_GATEWAY_URL` | No | Gateway URL (default: http://127.0.0.1:8787) |
| `BLACKROAD_DB` | No | SQLite path (default: ./blackroad.db) |

## Deployment

- **Python API** → [Railway](https://railway.app) (`railway.toml`)
- **Cloudflare Worker** → Cloudflare Workers (`workers/task-dispatcher/wrangler.toml`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

© BlackRoad OS, Inc. — Your AI. Your Hardware. Your Rules.
