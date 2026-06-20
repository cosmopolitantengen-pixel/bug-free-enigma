from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app.core.models import MemoryRecord
from app.safety.risk import FORBIDDEN_ACTIONS, HIGH_RISK_ACTIONS, MEDIUM_RISK_ACTIONS
from app.services.serializers import to_plain


class SkillRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class SkillRuntimeContext:
    company_os: Any


def validate_skill_input(schema: dict[str, str], payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise SkillRuntimeError("skill input must be an object")
    validators: dict[str, Callable[[Any], bool]] = {
        "string": lambda value: isinstance(value, str),
        "array": lambda value: isinstance(value, list),
        "object": lambda value: isinstance(value, dict),
        "boolean": lambda value: isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    }
    for key, type_name in schema.items():
        if key not in payload:
            raise SkillRuntimeError(f"missing required skill input: {key}")
        validator = validators.get(type_name)
        if validator is None:
            raise SkillRuntimeError(f"unsupported skill schema type: {type_name}")
        if not validator(payload[key]):
            raise SkillRuntimeError(f"skill input {key} must be {type_name}")


def execute_skill_adapter(skill_id: str, payload: dict[str, Any], context: SkillRuntimeContext) -> dict[str, Any]:
    validate_skill_input(context.company_os.skills.get(skill_id).input_schema, payload)
    adapters = {
        "task_planning_skill_v1": _task_plan,
        "document_writer_skill_v1": _document,
        "summary_skill_v1": _summary,
        "risk_check_skill_v1": _risk_check,
        "quality_check_skill_v1": _quality_check,
        "rewrite_skill_v1": _rewrite,
        "data_cleanup_skill_v1": _data_cleanup,
        "spreadsheet_generation_skill_v1": _spreadsheet,
        "code_generation_skill_v1": _code_generation,
        "code_review_skill_v1": _code_review,
        "github_project_analysis_skill_v1": _github_analysis,
        "approval_request_skill_v1": _approval_request,
        "audit_logging_skill_v1": _audit_event,
        "memory_write_skill_v1": _memory_write,
        "knowledge_search_skill_v1": _knowledge_search,
        "skill_search_skill_v1": _skill_search,
        "skill_composition_skill_v1": _skill_composition,
        "temporary_skill_creation_skill_v1": _temporary_skill,
    }
    adapter = adapters.get(skill_id)
    if adapter is None:
        raise SkillRuntimeError(f"no runtime adapter registered for skill: {skill_id}")
    return adapter(payload, context)


def _task_plan(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    goal = payload["goal"].strip()
    if not goal:
        raise SkillRuntimeError("goal must not be empty")
    return {"plan": f"1. Confirm scope for: {goal}\n2. Assign authorized Agents and Skills.\n3. Execute with risk, approval, quality, and audit checks."}


def _document(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    materials = "\n".join(f"- {item}" for item in payload["materials"]) or "- No source materials supplied."
    return {"markdown_document": f"# {payload['topic'].strip()}\n\n## Materials\n\n{materials}"}


def _summary(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    content = re.sub(r"\s+", " ", payload["content"]).strip()
    return {"summary": content if len(content) <= 240 else content[:237].rstrip() + "..."}


def _risk_check(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    action = payload["action"]
    if action in FORBIDDEN_ACTIONS:
        level, blocked = "forbidden", True
    elif action in HIGH_RISK_ACTIONS:
        level, blocked = "high", False
    elif action in MEDIUM_RISK_ACTIONS:
        level, blocked = "medium", False
    else:
        level, blocked = "low", False
    return {"risk_level": level, "blocked": blocked, "requires_approval": level in {"medium", "high", "forbidden"}}


def _quality_check(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    content = payload["content"].strip()
    issues = [] if len(content) >= 20 else ["content is too short for a meaningful quality review"]
    return {"passed": not issues, "issues": issues}


def _rewrite(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"rewritten_content": f"{payload['content'].strip()}\n\nRevision intent: {payload['instructions'].strip()}"}


def _data_cleanup(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    unique, seen, issues = [], set(), []
    for index, record in enumerate(payload["records"]):
        if not isinstance(record, dict):
            issues.append({"index": index, "issue": "record is not an object"})
            continue
        normalized = {str(key).strip(): value.strip() if isinstance(value, str) else value for key, value in record.items()}
        marker = repr(sorted(normalized.items()))
        if marker in seen:
            issues.append({"index": index, "issue": "duplicate record"})
            continue
        seen.add(marker)
        unique.append(normalized)
    return {"records": unique, "issues": issues, "rules_applied": payload["rules"]}


def _spreadsheet(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"workbook_spec": {"sheet": "Data", "columns": payload["columns"], "rows": payload["records"]}}


def _code_generation(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"source": f"# Draft {payload['language']} implementation\n# Requirements: {payload['requirements']}", "notes": "Draft only; execution is a separate Tool action."}


def _code_review(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    findings = []
    if "TODO" in payload["source"]:
        findings.append("Source contains unresolved TODO markers.")
    if not payload["source"].strip():
        findings.append("Source is empty.")
    return {"findings": findings, "context": payload["context"]}


def _github_analysis(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"analysis": {"repository": payload["repository"], "metadata_keys": sorted(payload["metadata"]), "trusted": False}}


def _approval_request(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"approval_id": None, "request": payload, "prepared": True}


def _audit_event(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    return {"event_id": None, "event": payload["event"], "prepared": True}


def _memory_write(payload: dict[str, Any], context: SkillRuntimeContext) -> dict[str, Any]:
    record = context.company_os.memory.write(MemoryRecord(task_id=payload["task_id"], content=payload["content"], memory_type="skill"))
    return {"record_id": record.record_id}


def _knowledge_search(payload: dict[str, Any], context: SkillRuntimeContext) -> dict[str, Any]:
    return {"documents": to_plain(context.company_os.knowledge.search(payload["query"]))}


def _skill_search(payload: dict[str, Any], context: SkillRuntimeContext) -> dict[str, Any]:
    return {"skills": to_plain(context.company_os.skills.search(payload["query"]))}


def _skill_composition(payload: dict[str, Any], context: SkillRuntimeContext) -> dict[str, Any]:
    skills = [context.company_os.skills.get(skill_id) for skill_id in payload["skill_ids"]]
    return {"composition": {"goal": payload["goal"], "steps": [{"sequence": index, "skill_id": skill.skill_id} for index, skill in enumerate(skills, 1)]}}


def _temporary_skill(payload: dict[str, Any], _: SkillRuntimeContext) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9]+", "_", payload["capability"].lower()).strip("_") or "temporary"
    return {"skill_proposal": {"skill_id": f"temporary_{slug}_skill_v1", "enabled": False, "requires_approval": True, "constraints": payload["constraints"]}}
