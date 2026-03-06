"""RoadChain ledger API — blockchain infrastructure endpoints (issue #4).

Provides transaction submission, ledger queries, and audit trail
for the RoadChain distributed ledger.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_db

router = APIRouter(prefix="/roadchain", tags=["roadchain"])


# ── Schema ───────────────────────────────────────────────────────────────────


class TransactionCreate(BaseModel):
    """RoadChain transaction payload."""
    type: str = Field(..., description="Transaction type: transfer, audit, governance")
    sender: str = Field(..., min_length=1)
    receiver: str = ""
    payload: dict = Field(default_factory=dict)
    signature: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _init_ledger_table() -> None:
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS roadchain_ledger (
        tx_id       TEXT PRIMARY KEY,
        block_hash  TEXT NOT NULL,
        prev_hash   TEXT NOT NULL,
        type        TEXT NOT NULL,
        sender      TEXT NOT NULL,
        receiver    TEXT DEFAULT '',
        payload     TEXT DEFAULT '{}',
        signature   TEXT DEFAULT '',
        timestamp   INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS roadchain_audit (
        id          TEXT PRIMARY KEY,
        tx_id       TEXT NOT NULL,
        action      TEXT NOT NULL,
        actor       TEXT NOT NULL,
        detail      TEXT DEFAULT '',
        timestamp   INTEGER NOT NULL
    );
    """)
    db.commit()


def _last_block_hash() -> str:
    db = get_db()
    row = db.execute(
        "SELECT block_hash FROM roadchain_ledger ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    return row["block_hash"] if row else "GENESIS"


def _compute_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/transactions", status_code=201)
async def submit_transaction(tx: TransactionCreate) -> dict:
    """Submit a signed transaction to the RoadChain ledger."""
    _init_ledger_table()
    db = get_db()
    tx_id = f"tx_{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    prev = _last_block_hash()
    block_hash = _compute_hash(f"{prev}:{tx.sender}:{tx.type}:{json.dumps(tx.payload)}:{now}")

    db.execute(
        """INSERT INTO roadchain_ledger
           (tx_id, block_hash, prev_hash, type, sender, receiver, payload, signature, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [tx_id, block_hash, prev, tx.type, tx.sender, tx.receiver,
         json.dumps(tx.payload), tx.signature, now],
    )
    # Record audit entry
    audit_id = f"audit_{uuid.uuid4().hex[:8]}"
    db.execute(
        """INSERT INTO roadchain_audit (id, tx_id, action, actor, detail, timestamp)
           VALUES (?, ?, 'submit', ?, ?, ?)""",
        [audit_id, tx_id, tx.sender, f"Transaction type: {tx.type}", now],
    )
    db.commit()
    return {"tx_id": tx_id, "block_hash": block_hash, "prev_hash": prev, "timestamp": now}


@router.get("/transactions")
async def list_transactions(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    type: str | None = Query(None),
    sender: str | None = Query(None),
) -> dict:
    """Query the RoadChain ledger."""
    _init_ledger_table()
    db = get_db()
    query = "SELECT * FROM roadchain_ledger"
    params: list = []
    clauses = []
    if type:
        clauses.append("type = ?")
        params.append(type)
    if sender:
        clauses.append("sender = ?")
        params.append(sender)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = db.execute(query, params).fetchall()
    txs = []
    for r in rows:
        t = dict(r)
        t["payload"] = json.loads(t.get("payload") or "{}")
        txs.append(t)
    total = db.execute("SELECT COUNT(*) as n FROM roadchain_ledger").fetchone()["n"]
    return {"transactions": txs, "total": total}


@router.get("/transactions/{tx_id}")
async def get_transaction(tx_id: str) -> dict:
    """Get a single transaction by ID."""
    _init_ledger_table()
    db = get_db()
    row = db.execute("SELECT * FROM roadchain_ledger WHERE tx_id = ?", [tx_id]).fetchone()
    if not row:
        raise HTTPException(404, f"Transaction '{tx_id}' not found")
    t = dict(row)
    t["payload"] = json.loads(t.get("payload") or "{}")
    return t


@router.get("/audit")
async def get_audit_trail(
    tx_id: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    """Retrieve the audit trail for transactions."""
    _init_ledger_table()
    db = get_db()
    if tx_id:
        rows = db.execute(
            "SELECT * FROM roadchain_audit WHERE tx_id = ? ORDER BY timestamp DESC LIMIT ?",
            [tx_id, limit],
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM roadchain_audit ORDER BY timestamp DESC LIMIT ?",
            [limit],
        ).fetchall()
    return {"audit": [dict(r) for r in rows], "count": len(rows)}
