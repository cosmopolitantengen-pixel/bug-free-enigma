# GITHUB ABSORBER

## Purpose

GitHub Absorber is the controlled path for learning from open-source projects. The first implementation is metadata-only: Human Root or an Agent supplies repository URL, README text, license name, and maintenance signal.

It does not fetch repositories, execute code, install dependencies, enable Tools, create Skills, or mutate Workflows.

## Current Flow

```text
POST /github/absorptions/analyze
-> approval request
-> POST /github/absorptions/{proposal_id}/sandbox
-> Human Root approval
-> POST /github/absorptions/{proposal_id}/register
-> Knowledge document
```

## Safety Checks

- GitHub URL shape must be accepted.
- Requested Agent must exist.
- README is treated as untrusted external content.
- Prompt-injection-like content is flagged as source data, not instructions.
- Unknown, proprietary, or missing licenses fail sandbox.
- Copyleft licenses are treated as medium risk.
- Security-sensitive signals such as arbitrary code execution, captcha bypass, credential handling, token theft, and scraping fail sandbox.

## Registration Boundary

Registration writes a Knowledge document only. Unknown repository code never enters runtime, and no Skill, Tool, Agent, Workflow, dependency, or script is enabled automatically.
