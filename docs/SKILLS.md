# SKILLS

## Skill Definition

A Skill is a registered capability that an Agent may call. Skills are narrower than Agents and should have explicit input, output, risk, and approval metadata.

## Required Skill Fields

- `skill_id`
- `name`
- `type`
- `description`
- `input_schema`
- `output_schema`
- `allowed_agents`
- `risk_level`
- `requires_approval`
- `version`
- `enabled`

## V1 Skills

- Task planning Skill
- Document writing Skill
- Summary Skill
- Rewrite Skill
- Risk check Skill
- Quality check Skill
- Data cleanup Skill
- Spreadsheet generation Skill
- Code generation Skill
- Code review Skill
- GitHub project analysis Skill
- Approval request Skill
- Audit logging Skill
- Memory write Skill
- Knowledge search Skill
- Skill search Skill
- Skill composition Skill
- Temporary Skill creation Skill

## Missing Skill Policy

Missing Skills do not fail silently. The system should:

1. Search existing Skills.
2. Substitute if a safe equivalent exists.
3. Compose safe existing Skills if possible.
4. Create a temporary low-risk Skill when allowed.
5. Generate a formal Skill proposal for repeated use.
6. Block or escalate high-risk capability requests.

## Current Implementation

`POST /skills/missing` creates a stored Skill proposal and links it to an approval request. The proposal must pass `POST /skills/proposals/{proposal_id}/sandbox` and receive Human Root approval before it can be registered through `POST /skills/proposals/{proposal_id}/register`.

All 18 V1 Skills are registered at bootstrap with input/output schemas, allowed Agent sets, risk levels, approval requirements, and enabled state. Catalog validation rejects Skill definitions that reference unknown Agents. Accepted Human Root or Factory registrations update both the Skill's allowed-Agent set and the Agent's allowed-Skill set so the capability is callable under the existing two-sided authorization check.

Formal Skill registrations are audited, stored in SQLite, included in backup snapshots, and restored transactionally. Code generation, GitHub analysis, and temporary Skill creation remain approval-gated capabilities; registering metadata does not execute code or external content.
