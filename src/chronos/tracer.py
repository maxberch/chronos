"""Tracer, execution interceptor, and branching session manager."""

from __future__ import annotations
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from chronos.models import EventType, StepEvent, Checkpoint, Run, Branch
from chronos.storage import ChronosStore, compute_checkpoint_id


class ChronosSession:
    """Manages an active agent session, recording steps, replaying cached state, and branching."""

    def __init__(
        self,
        run_name: str = "agent-run",
        run_id: Optional[str] = None,
        branch_id: str = "main",
        store: Optional[ChronosStore] = None,
        db_path: str = ".chronos.db"
    ):
        self.store = store or ChronosStore(db_path=db_path)
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.branch_id = branch_id
        self.step_counter = 0
        self.parent_checkpoint_id: Optional[str] = None

        # Mode: "RECORD" or "REPLAY"
        self.mode = "RECORD"
        self.replay_queue: List[Checkpoint] = []

        # Initialize Run and Branch records
        existing_run = self.store.get_run(self.run_id)
        if not existing_run:
            self.store.save_run(Run(run_id=self.run_id, name=run_name))

        existing_branch = self.store.get_branch(self.branch_id)
        if not existing_branch:
            self.store.save_branch(Branch(branch_id=self.branch_id, run_id=self.run_id, name=branch_id))

    @classmethod
    def fork(
        cls,
        parent_checkpoint_id: str,
        new_branch_name: Optional[str] = None,
        db_path: str = ".chronos.db"
    ) -> ChronosSession:
        """Fork execution from an existing checkpoint, enabling replay up to that point."""
        store = ChronosStore(db_path=db_path)
        target_chk = store.get_checkpoint(parent_checkpoint_id)
        if not target_chk:
            raise ValueError(f"Checkpoint '{parent_checkpoint_id}' not found.")

        # Reconstruct the historical chain up to target_chk
        history: List[Checkpoint] = []
        curr = target_chk
        while curr:
            history.insert(0, curr)
            if curr.parent_id:
                curr = store.get_checkpoint(curr.parent_id)
            else:
                break

        new_branch_id = f"br_{uuid.uuid4().hex[:8]}"
        branch_name = new_branch_name or f"fork-from-{parent_checkpoint_id[:8]}"

        # Save the new branch record
        store.save_branch(
            Branch(
                branch_id=new_branch_id,
                run_id=target_chk.run_id,
                parent_checkpoint_id=parent_checkpoint_id,
                name=branch_name
            )
        )

        session = cls(
            run_id=target_chk.run_id,
            branch_id=new_branch_id,
            store=store,
            db_path=db_path
        )
        session.mode = "REPLAY"
        session.replay_queue = history
        return session

    def step(
        self,
        name: str,
        event_type: EventType,
        inputs: Dict[str, Any],
        fn: Callable[[], Any]
    ) -> Any:
        """The core execution primitive. Replays if cached and valid; executes and records otherwise."""
        chk_id = compute_checkpoint_id(
            parent_id=self.parent_checkpoint_id,
            event_type=event_type,
            name=name,
            inputs=inputs
        )

        # Check if we can replay from queue
        if self.mode == "REPLAY" and self.replay_queue:
            next_cached = self.replay_queue[0]
            if next_cached.checkpoint_id == chk_id:
                # Match found! Fast-forward with zero latency & zero API call
                self.replay_queue.pop(0)
                self.step_counter += 1
                self.parent_checkpoint_id = chk_id
                print(f"[Chronos] ⚡ Cache Hit: Replaying '{name}' [step {self.step_counter}] (0.00ms, $0.00)")
                return next_cached.event.outputs
            else:
                # Mismatch! Inputs or causal history diverged.
                print(f"[Chronos] 🔀 Branch Diverged at '{name}' [step {self.step_counter + 1}]. Transitioning to LIVE RECORD.")
                self.mode = "RECORD"
                self.replay_queue.clear()

        # Execute Live and Record
        start_time = time.perf_counter()
        error_msg: Optional[str] = None
        output: Any = None

        try:
            output = fn()
            return output
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.step_counter += 1

            event = StepEvent(
                event_type=event_type,
                name=name,
                inputs=inputs,
                outputs=output,
                error=error_msg,
                duration_ms=duration_ms
            )

            checkpoint = Checkpoint(
                checkpoint_id=chk_id,
                run_id=self.run_id,
                branch_id=self.branch_id,
                step_index=self.step_counter,
                parent_id=self.parent_checkpoint_id,
                event=event
            )

            self.store.save_checkpoint(checkpoint)
            self.parent_checkpoint_id = chk_id
            status = "❌ FAILED" if error_msg else "✅ DONE"
            print(f"[Chronos] ⏺️  Recorded: '{name}' [step {self.step_counter}] -> {status} ({duration_ms:.1f}ms)")

    def tool(self, name: Optional[str] = None):
        """Decorator to instrument tool functions."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            def wrapper(*args, **kwargs):
                inputs = {"args": args, "kwargs": kwargs}
                return self.step(
                    name=tool_name,
                    event_type=EventType.TOOL,
                    inputs=inputs,
                    fn=lambda: func(*args, **kwargs)
                )
            return wrapper
        return decorator

    def llm(self, model_name: str):
        """Context or wrapper for an LLM query."""
        def call(inputs: Dict[str, Any], generate_fn: Callable[[], Any]) -> Any:
            return self.step(
                name=model_name,
                event_type=EventType.LLM,
                inputs=inputs,
                fn=generate_fn
            )
        return call
