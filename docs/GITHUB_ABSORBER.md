# GITHUB ABSORBER

## Purpose

GitHub Absorber is the controlled path for learning from open-source projects. Operators can supply repository metadata manually, or use the controlled GitHub connector to import repository metadata and README text from the GitHub API.

It does not clone repositories, execute code, install dependencies, enable Tools, create Skills, or mutate Workflows.

## Current Flow

The native end-to-end Workflow is:

```text
POST /workflows/run (github_project_analysis_v1)
-> one task-scoped Human Root approval
-> POST /tasks/{task_id}/resume
-> GitHub analysis Skill
-> risk Skill
-> absorption proposal and capability curation Skill
-> deterministic sandbox
-> Knowledge document, only when sandbox passed
```

The lower-level API remains available for operators that need to inspect and advance each proposal stage manually:

```text
POST /github/absorptions/analyze
or POST /github/absorptions/import
-> approval request
-> POST /github/absorptions/{proposal_id}/sandbox
-> Human Root approval
-> POST /github/absorptions/{proposal_id}/register
-> Knowledge document
```

## Safety Checks

- GitHub URL shape must be accepted.
- Connector imports accept only HTTPS `github.com/{owner}/{repo}` repository-root URLs.
- Requested Agent must exist.
- README is treated as untrusted external content.
- Optional `GITHUB_TOKEN` or `GITHUB_TOKEN_FILE` is used only as an outbound Authorization header and is never returned in API, Audit, or Knowledge records.
- Prompt-injection-like content is flagged as source data, not instructions.
- Unknown, proprietary, or missing licenses fail sandbox.
- Copyleft licenses are treated as medium risk.
- Security-sensitive signals such as arbitrary code execution, captcha bypass, credential handling, token theft, and scraping fail sandbox.

## Registration Boundary

Registration writes a Knowledge document only. Unknown repository code never enters runtime, and no Skill, Tool, Agent, Workflow, dependency, or script is enabled automatically.
