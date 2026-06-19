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

## Current Internal Adapters

The first implementation includes a small controlled adapter layer for safe internal tools:

- `task_manager_tool` returns task counts, status counts, recent tasks, or one task by ID.
- `knowledge_base_tool` lists, searches, or writes internal knowledge documents.
- `audit_read_tool` returns recent append-only audit events.
- `database_read_tool` returns aggregate state counts for core tables and stores, without accepting raw SQL.
- `filesystem_read_tool` lists directories, reads small text files, and searches allowed text files inside the workspace.

Adapter output is stored on the Tool Run as JSON. Invalid adapter input marks the Tool Run as `failed` and writes the failure into audit output.

Filesystem read/search output includes external-content inspection metadata. File contents are always marked untrusted and must be treated as source data, not executable instructions.

## Filesystem Read Boundaries

The filesystem adapter is read-only and intentionally narrow:

- relative paths only
- resolved paths must stay inside the workspace
- hidden or sensitive paths such as `.git`, `.codex`, `.agents`, `.env`, virtualenvs, `node_modules`, and `__pycache__` are denied
- only common text extensions are readable/searchable
- file reads are capped at 64 KiB
- write, delete, execute, upload, and external send operations are not implemented

Real browser, GitHub, computer-control, or external API adapters should only be added after their permission boundaries, sandbox behavior, approval flow, and audit output are covered by tests.
