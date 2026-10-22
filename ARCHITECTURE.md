# Chronos Architecture Specification

## 1. Design Principles

1. **Zero Intrusion:** Integrating Chronos should require minimal changes to user code.
2. **Local-First & Offline:** SQLite is the default storage engine. Everything runs locally on the developer's machine with zero external services required.
3. **Content-Addressable Determinism:** Checkpoints are identified by a cryptographic hash of their upstream causal history + current step parameters.
4. **Transparent Replay:** Replaying a cached step returns the exact recorded output without invoking the remote model API or triggering real-world side effects.

---

## 2. Core Data Model

```
                    ┌─────────────────────────┐
                    │       ChronosRun        │
                    │   (run_id, root_branch) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Branch (main)      │
                    │ (branch_id, parent_chk) │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
┌───────────────────────┐                   ┌───────────────────────┐
│     Checkpoint 1      │                   │     Checkpoint 2      │
│  - Step: 1            │                   │  - Step: 2            │
│  - Parent: Root       │ ◄──────────────── │  - Parent: Chk 1      │
│  - Event: LLM / Tool  │                   │  - Event: LLM / Tool  │
└───────────────────────┘                   └───────────┬───────────┘
                                                        │
                                                        ▼ (Fork / Branch)
                                            ┌───────────────────────┐
                                            │  Branch (fix-prompt)  │
                                            │  - Parent: Chk 2      │
                                            └───────────┬───────────┘
                                                        │
                                                        ▼
                                            ┌───────────────────────┐
                                            │  Checkpoint 3 (v2)    │
                                            │  - Patched inputs     │
                                            └───────────────────────┘
```

### Models

* **`StepEvent`**: The atomic execution event (either an `LLM_CALL`, `TOOL_CALL`, or `STATE_SNAPSHOT`).
  * `event_type`: `"llm" | "tool" | "custom"`
  * `name`: identifier (e.g. model name or tool function name)
  * `inputs`: Dict of input arguments (messages, tools, temperature, kwargs)
  * `outputs`: Dict or value returned
  * `error`: Optional error string / traceback if the step failed
  * `duration_ms`: Execution latency
  * `cost_estimate`: Estimated token cost

* **`Checkpoint`**:
  * `checkpoint_id`: Content hash derived from `hash(parent_id, event_type, inputs)`
  * `run_id`: The session/run ID
  * `branch_id`: The branch ID (default: `"main"`)
  * `step_index`: Sequential integer index within the branch
  * `parent_id`: Hash of the preceding checkpoint (or `None` for root)
  * `event`: `StepEvent`
  * `created_at`: ISO timestamp

---

## 3. Storage Layer (`storage.py`)

A light SQLite schema with WAL mode enabled:
* `runs`: `(run_id TEXT PRIMARY KEY, name TEXT, created_at TEXT, metadata JSON)`
* `branches`: `(branch_id TEXT PRIMARY KEY, run_id TEXT, parent_checkpoint_id TEXT, name TEXT)`
* `checkpoints`: `(checkpoint_id TEXT PRIMARY KEY, run_id TEXT, branch_id TEXT, step_index INT, parent_id TEXT, event_type TEXT, name TEXT, inputs JSON, outputs JSON, error TEXT, duration_ms REAL, created_at TEXT)`

Indices:
* Index on `(run_id, branch_id, step_index)`
* Index on `parent_id`

---

## 4. Execution Modes in `ChronosSession`

1. **`RECORD` (Normal Run):**
   * Executes LLM and tool calls normally.
   * Hashes step arguments and writes checkpoints to SQLite in real time.
2. **`REPLAY` (Deterministic Time-Travel):**
   * Moves sequential pointer forward.
   * Matches current step against cached checkpoint.
   * If a match exists in the active branch: **bypasses live API call**, instantly returns cached outputs.
   * If no match exists or user mutated parameters: transitions automatically to `RECORD` mode on a new branch.
