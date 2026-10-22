"""SQLite storage and content-addressable DAG persistence for Chronos."""

from __future__ import annotations
import sqlite3
import json
import hashlib
from typing import Any, Dict, List, Optional
from pathlib import Path
from chronos.models import Checkpoint, StepEvent, EventType, Run, Branch


def canonical_json_dump(obj: Any) -> str:
    """Deterministic JSON serialization for cryptographic content hashing."""
    try:
        return json.dumps(obj, sort_keys=True, default=str)
    except Exception:
        return json.dumps(str(obj), sort_keys=True)


def compute_checkpoint_id(
    parent_id: Optional[str],
    event_type: EventType,
    name: str,
    inputs: Dict[str, Any]
) -> str:
    """Compute a deterministic hash for a step given its parent and inputs."""
    hasher = hashlib.sha256()
    hasher.update((parent_id or "ROOT").encode("utf-8"))
    hasher.update(event_type.value.encode("utf-8"))
    hasher.update(name.encode("utf-8"))
    hasher.update(canonical_json_dump(inputs).encode("utf-8"))
    # Return first 16 characters for git-like clean identifiers
    return f"chk_{hasher.hexdigest()[:16]}"


class ChronosStore:
    def __init__(self, db_path: str = ".chronos.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency and fast local writes
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS branches (
                    branch_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    parent_id TEXT,
                    event_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    outputs TEXT,
                    error TEXT,
                    duration_ms REAL NOT NULL,
                    cost_estimate REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id),
                    FOREIGN KEY(branch_id) REFERENCES branches(branch_id)
                );

                CREATE INDEX IF NOT EXISTS idx_branch_steps 
                ON checkpoints(branch_id, step_index);

                CREATE INDEX IF NOT EXISTS idx_parent_id 
                ON checkpoints(parent_id);
            """)

    def save_run(self, run: Run):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, name, created_at, metadata) VALUES (?, ?, ?, ?)",
                (run.run_id, run.name, run.created_at, json.dumps(run.metadata))
            )

    def get_run(self, run_id: str) -> Optional[Run]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return Run(
                run_id=row["run_id"],
                name=row["name"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"])
            )

    def save_branch(self, branch: Branch):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO branches (branch_id, run_id, parent_checkpoint_id, name, created_at) VALUES (?, ?, ?, ?, ?)",
                (branch.branch_id, branch.run_id, branch.parent_checkpoint_id, branch.name, branch.created_at)
            )

    def get_branch(self, branch_id: str) -> Optional[Branch]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
            if not row:
                return None
            return Branch(
                branch_id=row["branch_id"],
                run_id=row["run_id"],
                parent_checkpoint_id=row["parent_checkpoint_id"],
                name=row["name"],
                created_at=row["created_at"]
            )

    def save_checkpoint(self, checkpoint: Checkpoint):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints (
                    checkpoint_id, run_id, branch_id, step_index, parent_id,
                    event_type, name, inputs, outputs, error, duration_ms, cost_estimate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.run_id,
                    checkpoint.branch_id,
                    checkpoint.step_index,
                    checkpoint.parent_id,
                    checkpoint.event.event_type.value,
                    checkpoint.event.name,
                    canonical_json_dump(checkpoint.event.inputs),
                    canonical_json_dump(checkpoint.event.outputs) if checkpoint.event.outputs is not None else None,
                    checkpoint.event.error,
                    checkpoint.event.duration_ms,
                    checkpoint.event.cost_estimate,
                    checkpoint.created_at
                )
            )

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)).fetchone()
            if not row:
                return None
            return self._row_to_checkpoint(row)

    def get_branch_checkpoints(self, branch_id: str) -> List[Checkpoint]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE branch_id = ? ORDER BY step_index ASC",
                (branch_id,)
            ).fetchall()
            return [self._row_to_checkpoint(r) for r in rows]

    def _row_to_checkpoint(self, row: sqlite3.Row) -> Checkpoint:
        outputs = json.loads(row["outputs"]) if row["outputs"] is not None else None
        return Checkpoint(
            checkpoint_id=row["checkpoint_id"],
            run_id=row["run_id"],
            branch_id=row["branch_id"],
            step_index=row["step_index"],
            parent_id=row["parent_id"],
            event=StepEvent(
                event_type=EventType(row["event_type"]),
                name=row["name"],
                inputs=json.loads(row["inputs"]),
                outputs=outputs,
                error=row["error"],
                duration_ms=row["duration_ms"],
                cost_estimate=row["cost_estimate"]
            ),
            created_at=row["created_at"]
        )
