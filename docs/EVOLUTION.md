# EVOLUTION

## Purpose

Evolution is the controlled path from observed work to proposed system improvement. In V1, the system can turn a task review into an auditable improvement proposal without automatically changing code, permissions, Agents, or Skills.

## Current Flow

1. Record a task review.
2. Create an improvement proposal from that review.
3. Route the proposal through approval.
4. Run deterministic sandbox checks.
5. Register the approved and sandbox-passed improvement as a knowledge record.

Missing Skill and Agent Workflows also use controlled evolution. They search registered capability first, run auditable planning and risk Skills, and create disabled proposals only when a real gap remains. Agent and Skill registration still requires separate Human Root approval and deterministic sandbox evidence.

## Safety Boundary

Improvement proposals are intentionally conservative:

- They are disabled by default.
- They require approval before registration.
- They require sandbox checks before registration.
- Registration records approved intent as knowledge.
- Registration does not automatically mutate runtime behavior.

This keeps self-improvement visible and reviewable while leaving future Agent, Skill, Workflow, or policy changes under Human Root control.
