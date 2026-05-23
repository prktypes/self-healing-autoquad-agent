# Architecture and Workflow — self-healing-autoquad-agent

This document explains the architecture, runtime workflow, and core concepts implemented in the repository. It is intended to help maintainers and contributors understand how the pieces fit together and where to extend or harden the prototype.

Overview
--------
The project is a small prototype autonomous code-review and repair system. It combines:

- A PR monitoring / interactive entrypoint (`main.py`).
- A squad of specialized LLM-driven agents (`squad_logic.py`) implemented as nodes in a `langgraph` StateGraph.
- A local runtime tool that can execute PowerShell commands (`tools.py`).
- Ollama as the local LLM provider (accessible via the `ollama` Python package/API).

High-level flow
---------------

1. Input source
   - The system accepts two input modes:
     - Pull Request monitoring: `main.py` connects to GitHub, fetches open PRs, extracts the file diffs and feeds them to the reviewer logic.
     - Interactive agent prompts: a developer can type a prompt into `main.py` to start an autonomous agent session.

2. PR analysis / Squad invocation
   - For PR diffs: `main.analyze_pr` composes a prompt containing the diff and asks the model (via Ollama) for a code review.
   - For the Squad: `squad_logic` is designed around a shared-state `SquadState` TypedDict and several nodes:
     - `security_agent`: inspects diffs for vulnerabilities (OWASP, secrets, etc.).
     - `performance_agent`: finds performance anti-patterns.
     - `janitor_agent`: detects naming, formatting, and architectural debt.
     - `lead_engineer_node`: aggregates reports and decides if the PR is `READY` or `CRITICAL`.
     - `fixer_node`: attempts to apply fixes locally by issuing commands through `run_terminal_command`.

3. Orchestration and control flow
   - The system models the review process as a directed graph using `langgraph.graph.StateGraph`.
   - Pattern used:
     - Fan-out: from START, run `security`, `performance`, and `janitor` in parallel.
     - Fan-in: each expert sends outputs to the `lead_engineer` node.
     - Conditional routing: `lead_engineer` decides whether to finish (END) or route to `fixer`.
     - Loop: after `fixer` completes, the graph routes back to `security` to re-evaluate.

Shared state design
-------------------

SquadState (TypedDict) — the central shared memory shape used by nodes:

- messages: list[str] — appended conversation history (Annotated with `add_messages` so new messages are appended by langgraph).
- code_diff: str — the PR diff / code context that agents analyze.
- security_report: str — output from `security_agent`.
- performance_report: str — output from `performance_agent`.
- janitor_report: str — output from `janitor_agent`.
- is_code_safe: bool — boolean flag set by `security_agent` (true if the agent deems code safe).
- is_ready_to_push: bool — flag set by `lead_engineer_node` to decide routing.

Node contract and responsibilities
---------------------------------

- Each node receives the current `SquadState` and returns a partial update (a dict) containing only the keys it modifies. The StateGraph runtime merges node outputs into the shared state.
- Agents use Ollama to produce textual reports. The model outputs are treated as content rather than authoritative facts; the lead synthesizes and decides.

Tooling and side-effects
------------------------

- `run_terminal_command` in `tools.py` is the sanctioned side-effecting tool: it runs PowerShell commands and returns outputs.
- The `fixer_node` is intentionally designed to be able to call that tool. In the current prototype the implementation is a placeholder — it constructs a prompt and configures the tool for the LLM but the code that actually parses and executes returned tool calls needs more implementation.

Security and safety considerations
----------------------------------

- Executing model-suggested shell commands is high-risk. Considerations:
  - Run only in isolated sandboxes (ephemeral VMs or containers).
  - Enforce allow-lists for commands, or implement a dry-run that only prints proposed commands.
  - Add human approval steps before pushing changes or running destructive ops.

Operational concerns and limitations
----------------------------------

- Model dependency: Ollama and the `qwen2.5-coder:7b` model are core to behavior. If Ollama isn't present or is configured differently, features will fail.
- The GitHub monitor in `main.py` assumes `PyGithub` and environment variables; missing tokens or permission issues will stop PR processing.
- `langgraph`'s StateGraph is used as a lightweight orchestrator — the repo doesn't include installation or runtime checks for it.

Extensibility and next work items
---------------------------------

- Complete the `fixer_node`'s tool execution logic and add safety checks (command allowlist, dry-run, approval gating).
- Add unit and integration tests for the StateGraph flows (happy and failure paths).
- Add a `requirements.txt` or `pyproject.toml` to make dependencies reproducible.
- Add logging, metrics and retry/backoff around external calls (GitHub and Ollama).

Sequence diagram (conceptual)
-----------------------------

1. main.py fetches PR diff -> 2. create SquadState with code_diff -> 3. START triggers security/performance/janitor in parallel -> 4. each agent writes its report into SquadState -> 5. lead_engineer reads reports and writes decision -> 6a. If READY -> END (optionally comment on PR) OR 6b. If CRITICAL -> fixer_node runs -> 7. fixer runs commands locally -> 8. loop back to security to re-evaluate -> 9. repeat until READY or max attempts

Files and responsibilities (quick map)
-------------------------------------

- `main.py` — PR monitoring, top-level interactive loop, simple reviewer integration using Ollama.
- `squad_logic.py` — Stateful squad nodes, orchestration graph, state shape.
- `tools.py` — local executor for PowerShell commands.

Summary
-------
This project is a compact prototype showing how to combine an LLM, a small orchestrator, and local tools to implement an autonomous code-review and repair loop. It emphasizes modular nodes that produce reports and a lead node that synthesizes decisions. Productionizing this requires safety gating, reproducible dependencies, and stronger error handling.
