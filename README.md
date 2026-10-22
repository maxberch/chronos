# Chronos ⏳

> **The Time-Travel & Branching Debugger for Stochastic AI Agents.**  
> *Rewind, branch, and hot-patch multi-step AI execution without restarting from scratch.*

---

## 🎯 The Core Problem

When an autonomous agent takes 20 steps and fails on step 18, debugging it today is agonizing:
- **Restarting from scratch** costs time and money ($$ in tokens) for steps 1–17 that already worked.
- **Stochastic variance** means step 4 might randomly fail on the retry, masking the real bug on step 18.
- **Uncontrolled side-effects** risk duplicate database writes, repeated emails, or unwanted state mutations.

**Chronos** provides a deterministic "Quicksave & Rewind" layer for AI applications.

---

## ⚡ Key Capabilities

1. **Git-Like Multiverse Tree (DAG):** Every LLM inference, tool execution, and state transition is hashed and stored in a local, content-addressable directed acyclic graph.
2. **Deterministic Replay Cache ($0 Cost):** Rewind to any historical checkpoint. Upstream steps replay in `0.00ms` with cached results and zero API fees.
3. **Alternate Reality Branching:** Fork execution at step $N$, edit the prompt, inject mock tool outputs, or tweak parameters, and resume forward.
4. **Tool Side-Effect Virtualization:** Automatically records tool inputs/outputs so replaying doesn't re-trigger external APIs.
5. **Framework-Agnostic:** Works with vanilla Python, raw OpenAI / Gemini SDKs, LangChain, AutoGen, CrewAI, or custom while-loops.

---

## 🚀 Quickstart (Coming in v0.1)

```python
import chronos
from google import genai

# 1. Initialize a Chronos session
session = chronos.init(project="market-researcher")

# 2. Wrap your model or agent loop
client = session.wrap(genai.Client())

# 3. If a step fails, rewind to a checkpoint and patch:
session.rewind(checkpoint="step_3", patch={"temperature": 0.2})
session.resume()
```
