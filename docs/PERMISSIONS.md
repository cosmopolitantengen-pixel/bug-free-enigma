# PERMISSIONS

## Authority Order

Human Root > AI Board > AI CEO > Department Agent > Agent > Skill > Tool

## Permission Levels

- `L0_READ`: read allowed internal or public data.
- `L1_DRAFT`: create drafts, plans, summaries, and internal generated content.
- `L2_INTERNAL_WRITE`: write internal task, memory, and knowledge records.
- `L3_EXTERNAL_PREPARE`: prepare external content or API calls, but require approval before sending.
- `L4_HIGH_RISK`: contracts, privacy, account, computer-control, code execution, or money-adjacent actions require Root approval.
- `L5_ROOT`: root settings, keys, audit deletion, risk shutdown, payment and refund actions are human-only.

## Hard Invariants

- AI cannot grant itself Root.
- AI cannot disable risk control.
- AI cannot delete or modify audit logs.
- AI cannot execute forbidden actions.
- AI cannot decide high-risk actions without Root approval.

The native Approval Workflow evaluates the request through registered Skills and core Permission/Risk controls, pauses at Human Root when required, and resumes only after a final decision. A rejected action is cancelled, while a forbidden action remains blocked and cannot be converted into approval.
