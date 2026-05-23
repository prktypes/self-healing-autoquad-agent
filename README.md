# self-healing-autoquad-agent

Lightweight autonomous "squad" that reviews, assesses and (optionally) attempts to fix code changes in a repository using a local LLM (Ollama), GitHub integration and a small orchestration layer.

This repository contains a small prototype agent that demonstrates several ideas:

- Automated PR analysis via a model-driven reviewer.
- A "squad" of specialized agents (security, performance, janitor) coordinated by a lead node.
- A fixer agent that can run PowerShell commands locally to attempt repairs.
- A simple shared-state orchestration implemented with `langgraph`'s StateGraph and a TypedDict-based shared memory.

Contents
--------
- `main.py` — entrypoints: PR monitoring (GitHub) and an interactive autonomous-agent loop.
- `squad_logic.py` — squad definitions: state shape, agent nodes, orchestration graph (fan-out / fan-in / conditional routing).
- `tools.py` — small utility to run PowerShell commands locally and capture output.

High-level usage
-----------------
1. Install dependencies (see below).
2. Create a `.env` file with `GITHUB_TOKEN` and `REPO_NAME` if you intend to use the PR monitor.
3. Ensure Ollama is installed and the required model (`qwen2.5-coder:7b`) is available locally.
4. Run `main.py` interactively to try the autonomous-agent loop, or enable the PR monitor in `main()`.

Quick start (example)
---------------------
Install dependencies (recommended in a venv):

```powershell
python -m pip install -r requirements.txt  # or manually install the packages listed below
```

Set environment variables (Windows PowerShell example):

```powershell
$env:GITHUB_TOKEN = 'ghp_...'
$env:REPO_NAME = 'owner/repo'
```

Run interactive loop:

```powershell
python main.py
```

What each file does
--------------------
- `main.py`:
  - Connects to GitHub using `PyGithub` and reads PR diffs.
  - Builds prompts for the Ollama model to produce code-review style analysis and posts comments back to PRs.
  - Contains `autonomous_agent_loop` which runs an LLM-driven agent that may call the `run_terminal_command` tool to execute PowerShell commands locally.

- `squad_logic.py`:
  - Defines the shared state shape using `TypedDict` (`SquadState`), including fields like `code_diff`, `security_report`, and boolean flags.
  - Implements specialized agents (security, performance, janitor) which call Ollama to generate reports.
  - Implements a `lead_engineer_node` that synthesizes expert reports and decides if fixes are required.
  - Implements a `fixer_node` that is intended to use `run_terminal_command` to apply repairs.
  - Uses `langgraph.graph.StateGraph` to orchestrate nodes. The graph demonstrates a fan-out (run experts in parallel), fan-in (lead collects reports), conditional routing to the fixer, and loops back to re-run the security node after fixes.

- `tools.py`:
  - Provides `run_terminal_command(command: str)` which runs a PowerShell command and returns stdout/stderr.

Dependencies
------------
The prototype assumes these (not exhaustive) packages:

- `ollama` — local LLM client
- `langgraph` — orchestration primitives (StateGraph)
- `PyGithub` — GitHub API client
- `python-dotenv` — load `.env` files

If you don't have a `requirements.txt` in the repo, create one with these packages and pinned versions appropriate for your environment.

Security and safety notes
------------------------
- The `fixer_node` and `run_terminal_command` are powerful and dangerous: they execute shell commands on the host.
  - Only run this code in a controlled environment.
  - Limit the lifetime and scope of `GITHUB_TOKEN` and follow the principle of least privilege.
- The system executes untrusted, model-generated commands in the local shell. Treat outputs and effects as untrusted until verified.

Next steps and suggestions
-------------------------
- Add a `requirements.txt` and test harness.
- Add explicit authentication and permission checks before running any fixer actions.
- Implement dry-run and staged-apply modes for fixes.
- Add unit tests for orchestration and basic liveness checks.

Contact / Iteration
-------------------
This README is intentionally short — we'll expand it as the project evolves. If you want, I can:

- Add a `requirements.txt` and reproducible dev environment.
- Add example `.env` and a safe mode to prevent any terminal execution.
- Add unit tests and CI configuration.
