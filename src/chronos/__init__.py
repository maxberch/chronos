"""Chronos: Time-Travel and Branching Debugger for Stochastic AI Agents."""

from typing import Optional
from chronos.models import EventType, StepEvent, Checkpoint, Run, Branch
from chronos.storage import ChronosStore
from chronos.tracer import ChronosSession

__version__ = "0.1.0"
__all__ = [
    "EventType",
    "StepEvent",
    "Checkpoint",
    "Run",
    "Branch",
    "ChronosStore",
    "ChronosSession",
    "init",
    "fork",
]


def init(name: str = "agent-run", db_path: str = ".chronos.db") -> ChronosSession:
    """Initialize a fresh Chronos recording session."""
    return ChronosSession(run_name=name, db_path=db_path)


def fork(
    checkpoint_id: Optional[str] = None,
    parent_checkpoint_id: Optional[str] = None,
    new_branch_name: Optional[str] = None,
    db_path: str = ".chronos.db"
) -> ChronosSession:
    """Fork an existing execution from a historical checkpoint for time-travel replay."""
    target_id = checkpoint_id or parent_checkpoint_id
    if not target_id:
        raise ValueError("Must provide either checkpoint_id or parent_checkpoint_id.")
    return ChronosSession.fork(
        parent_checkpoint_id=target_id,
        new_branch_name=new_branch_name,
        db_path=db_path
    )
