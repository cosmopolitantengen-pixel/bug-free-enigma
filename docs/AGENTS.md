# AGENTS

## Agent Definition

An Agent is an AI job role. It can reason, plan, delegate, request approvals, call registered Skills, and write audit events. It cannot exceed its permissions.

Agents can also leave stored messages and meeting records for other Agents. These communication records are audited and persisted; they do not grant new permissions or bypass approval requirements.

Task handoffs are stored as explicit records from one Agent to another. A handoff validates internal-write permission and risk policy, then creates a linked `handoff` message for the receiving Agent.

Agent broadcasts let one Agent publish an internal event to multiple Agents. Broadcasts validate internal-write permission and risk policy, then write an auditable event stream entry for the audience.

Agent conflicts let Agents record disagreement instead of making unsafe unilateral decisions. A conflict captures participant positions and a priority area, then Human Root or an authorized Agent records the resolution.

## Required Agent Fields

- `agent_id`
- `name`
- `department`
- `role`
- `permissions`
- `forbidden`
- `allowed_skills`
- `allowed_tools`
- `reports_to`
- `risk_level`
- `version`
- `enabled`

## V1 Agents

- CEO Agent
- Project Manager Agent
- Document Agent
- Product Agent
- Tech Agent
- Data Agent
- Risk Agent
- Legal / Compliance Agent
- Finance Assistant Agent
- Quality Check Agent
- Memory Agent
- Skill Manager Agent
- Workflow Agent
- Audit Agent
- Capability Gap Detector Agent
- Agent Factory Agent
- Skill Factory Agent

## Factory Rule

New Agents are proposals first. A new Agent must receive:

- Generated identity configuration
- Permission boundary
- Allowed Skill list
- Allowed Tool list
- Sandbox test result
- Risk assessment
- Approval decision before enablement

Human Root remains the final authority.

## Current Implementation

`POST /agents/missing` creates a stored Agent proposal and links it to an approval request. The proposal must pass `POST /agents/proposals/{proposal_id}/sandbox` and receive Human Root approval before it can be registered through `POST /agents/proposals/{proposal_id}/register`.

All 17 V1 roles are registered at bootstrap with scoped permissions, forbidden actions, Skills, Tools, reporting lines, and risk levels. Catalog validation rejects unknown Skill, Tool, or manager references, rejects asymmetric Agent/Skill authorization, and continues to prohibit `L5_ROOT` for every Agent.

Formal Agent registrations are audited, stored in SQLite, included in backup snapshots, and restored transactionally. Default catalog entries remain code-defined; approved or Human Root-created additions survive process restarts.
