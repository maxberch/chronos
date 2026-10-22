"""Core data models for Chronos (Zero-dependency dataclasses)."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


class EventType(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    STATE = "state"


@dataclass
class StepEvent:
    """An atomic operation recorded by Chronos (e.g. an LLM query or tool execution)."""
    event_type: EventType
    name: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    cost_estimate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


@dataclass
class Checkpoint:
    """An immutable, content-addressed node in the execution graph."""
    checkpoint_id: str
    run_id: str
    branch_id: str
    step_index: int
    parent_id: Optional[str]
    event: StepEvent
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "run_id": self.run_id,
            "branch_id": self.branch_id,
            "step_index": self.step_index,
            "parent_id": self.parent_id,
            "event": self.event.to_dict(),
            "created_at": self.created_at,
        }


@dataclass
class Branch:
    """A lineage path within a Run."""
    branch_id: str
    run_id: str
    parent_checkpoint_id: Optional[str] = None
    name: str = "main"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Run:
    """A root session recording one or more branches of an agent execution."""
    run_id: str
    name: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

