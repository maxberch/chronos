<div align="center">

# ⏳ Chronos

### Time-Travel and Branching Debugger for Stochastic AI Agents
**Rewind, branch, and hot-patch multi-step AI execution without restarting from scratch.**

[![Tests](https://github.com/chronos-ai/chronos/actions/workflows/test.yml/badge.svg)](https://github.com/chronos-ai/chronos/actions)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](pyproject.toml)

</div>

---

## 💥 The "Step 18 Nightmare"

When building autonomous agents (researchers, coding assistants, multi-turn workflows), failure on Step 18 forces you to hit **Restart from Step 1**:
- 💸 **Wasted Money:** Re-running Steps 1–17 burns real money in tokens.
- ⏳ **Wasted Time:** Waiting 2 minutes for earlier steps to replay on every minor prompt tweak.
- 🎲 **Stochastic Drift:** Because LLMs are probabilistic, Step 4 might fail on the retry, masking the bug on Step 18.
- ⚠️ **Dangerous Side-Effects:** Real-world tool actions (APIs, database writes) get re-triggered unintentionally.

**Chronos** gives AI agents a deterministic **Quicksave & Rewind button**.

---

## ✨ Features

- **⚡ Instant Cache Hits ($0 Cost, 0.00ms):** Historical steps replay from a local cryptographic DAG without re-querying the model API.
- **🔀 Multiverse Branching:** Fork execution at any historical checkpoint, edit a prompt or parameter, and resume forward on an alternate branch.
- **🔌 Zero-Boilerplate Auto-Wrapper:** Wrap your existing Google GenAI or OpenAI clients with `client = session.wrap(client)`—no rewriting agent loops.
- **🖥️ Local Web UI (`chronos ui`):** An embedded, interactive visual tree showing branches, step latencies, error stack traces, and 1-click time-travel code snippets.
- **🪶 Zero Dependencies:** Core library runs on pure Python standard library (`sqlite3`, `dataclasses`, `http.server`). No heavy dependencies, fast startup.

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/your-org/chronos.git
cd chronos
pip install -e .
```

### 2. Wrap Your Existing LLM Client in 1 Line

```python
import chronos
from google import genai  # or: from openai import OpenAI

# Initialize session
session = chronos.init("market-researcher")

# Wrap your existing client
client = session.wrap(genai.Client())

# Make standard calls — Chronos automatically hashes and records checkpoints
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Extract financial metrics from 10-Q filing"
)

print(response.text)
```

### 3. Time-Travel & Branch on Failure

If Step 3 crashes, inspect the checkpoint and fork from Step 2:

```python
# Fork from Checkpoint 2 and apply your fix
fix_session = chronos.fork(
    checkpoint_id="chk_0e442be3d0f3",
    new_branch_name="fix-parser"
)

client = fix_session.wrap(genai.Client())

# Steps 1 & 2 replay in 0.00ms from cache for $0.00!
# Step 3 executes the patched prompt live:
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Extract metrics as clean numeric floats (no formatting)"
)
```

---

## 🖥️ Local Web Dashboard

Launch the visual branching tree with one command:

```bash
chronos ui --db demo_chronos.db
```

Open **[http://localhost:4040](http://localhost:4040)** to:
* Explore the interactive execution timeline and visual branches.
* Compare inputs and outputs side-by-side.
* Copy 1-click Python rewind code snippets.

---

## 🛠️ Architecture

```text
[Your Agent / Workflow]
         │
         ▼  (client = session.wrap(client))
┌────────────────────────────────────────────────────────┐
│                     Chronos Session                    │
│                                                        │
│  [Step Event] ──► [Cryptographic Content Hasher]       │
│                            │                           │
│              ┌─────────────┴─────────────┐             │
│              ▼                           ▼             │
│        [Replay Match?]             [Cache Miss / Fork] │
│              │                           │             │
│              ▼                           ▼             │
│       ⚡ 0.00ms Replay            ⏺️ Live Execution     │
│       ($0 API Cost)                (Records new node)  │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │  Local SQLite WAL Storage   │
              │   (Runs, Branches, DAG)     │
              └─────────────────────────────┘
```

---

## 🧪 Running Tests

Tests run out of the box with zero third-party packages:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

---

## 📄 License

Apache License 2.0. See [LICENSE](LICENSE) for details.
