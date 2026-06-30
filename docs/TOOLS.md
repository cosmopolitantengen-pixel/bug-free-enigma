# TOOLS

## Tool Definition

A Tool is a registered capability an Agent can request. Tools are lower authority than Agents and Skills, and they must stay inside Human Root permission, approval, risk, and audit controls.

## Required Tool Fields

- `tool_id`
- `name`
- `type`
- `description`
- `action`
- `permission_level`
- `risk_level`
- `requires_approval`
- `input_schema`
- `output_schema`
- `version`
- `enabled`

## Current Default Tools

- `task_manager_tool`: enabled, low-risk internal task inspection and updates.
- `knowledge_base_tool`: enabled, low-risk internal knowledge base access.
- `audit_read_tool`: enabled, low-risk audit log reads.
- `database_read_tool`: enabled, low-risk aggregate database state reads without raw SQL access.
- `filesystem_read_tool`: enabled, low-risk workspace-only text file list/read/search.
- `workspace_patch_tool`: enabled, medium-risk exact text replacement with stale-file protection and mandatory approval.
- `workspace_command_tool`: enabled, high-risk allowlisted process execution with mandatory approval and sanitized environment.
- `git_read_tool`: enabled, low-risk Git status/diff/log inspection.
- `external_api_tool`: disabled by default, medium-risk external API preparation.
- `code_execution_tool`: disabled by default, high-risk sandbox code execution.

## Tool Run Rule

`POST /tools/runs/request` creates a controlled Tool Run request:

- Disabled Tools are blocked.
- Agents can only request Tools in their `allowed_tools`.
- Permission and Risk engines evaluate the Tool action before execution.
- Low-risk allowed internal Tool Runs execute deterministic adapters.
- Medium/high-risk or approval-required Tool Runs create approval-linked waiting runs.
- Waiting Tool Runs can be completed only after the linked approval is approved.
- Every Tool Run request writes an audit event.
- Completion writes a separate `tool_run_completed` audit event.

`POST /workflows/run` with `tool_call_v1` wraps the same Tool Runtime in a complete task process. Approval-request, risk, and audit Skills create task-linked Skill Runs; the actual Tool Run remains the execution source of truth. Approval-gated calls resume through `POST /tasks/{task_id}/resume`, or Human Root can record the decision and resume in one idempotent call through `POST /tasks/{task_id}/decision`. Both paths recheck live Agent enablement, Tool authorization, permission, and risk before execution. Rejected calls are closed without execution. Workflow and Tool evidence persist across SQLite restarts.

## Current Internal Adapters

The first implementation includes a small controlled adapter layer for safe internal tools:

- `task_manager_tool` returns task counts, status counts, recent tasks, or one task by ID.
- `knowledge_base_tool` lists, searches, or writes internal knowledge documents.
- `audit_read_tool` returns recent append-only audit events.
- `database_read_tool` returns aggregate state counts for core tables and stores, without accepting raw SQL.
- `filesystem_read_tool` lists directories, reads small text files, and searches allowed text files inside the workspace.
- `workspace_patch_tool` atomically applies one exact replacement, optionally checks the expected file SHA-256, and returns a unified diff.
- `workspace_command_tool` runs an argument array without a shell, limits executable names, workspace `cwd`, timeout, output size, and inherited environment variables.
- `git_read_tool` exposes read-only status, diff, and recent log operations without allowing arbitrary Git subcommands.

Adapter output is stored on the Tool Run as JSON. Invalid adapter input marks the Tool Run as `failed` and writes the failure into audit output.

Filesystem read/search output includes external-content inspection metadata. File contents are always marked untrusted and must be treated as source data, not executable instructions.

## Filesystem Read Boundaries

The filesystem read adapter is intentionally narrow:

- relative paths only
- resolved paths must stay inside the workspace
- hidden or sensitive paths such as `.git`, `.codex`, `.agents`, `.env`, virtualenvs, `node_modules`, and `__pycache__` are denied
- only common text extensions are readable/searchable
- file reads are capped at 64 KiB
- delete, upload, and external send operations remain unavailable

Workspace writes use a separate approval-gated patch tool. It only edits existing allowed text files, requires `old_text` to match exactly once, can reject stale `expected_sha256` state, writes atomically, and never exposes patch contents in approval metadata. The command tool always requires Human Root approval, executes without a shell, resolves approved executable names through the sanitized platform PATH, allows only development executables, strips provider keys and unrelated environment variables, caps output, and enforces a 120-second maximum timeout. A non-zero process exit marks the Tool Run as failed while retaining bounded stdout and stderr evidence.

Chat auto mode recognizes explicit workspace requests such as `git status`, `git diff`, `git log`, `搜索代码：...`, and `运行后端测试`. It creates a `tool_call_v1` proposal first; no tool executes until Human Root confirms the chat action. Command actions then show their risk, approval ID, and exact argument array inside chat. Human Root can reject or approve and continue without leaving the conversation, and the waiting approval card survives a browser reload.

Real browser, computer-control, or external API adapters should only be added after their permission boundaries, sandbox behavior, approval flow, and audit output are covered by tests.
