from __future__ import annotations

from app.core.enums import PermissionLevel, RiskLevel
from app.core.models import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.tool_id in self._tools:
            raise ValueError(f"tool already registered: {tool.tool_id}")
        if tool.risk_level in {RiskLevel.HIGH, RiskLevel.FORBIDDEN} and not tool.requires_approval:
            raise ValueError("high or forbidden risk tools must require approval")
        if tool.risk_level == RiskLevel.FORBIDDEN and tool.enabled:
            raise ValueError("forbidden risk tools cannot be enabled")
        self._tools[tool.tool_id] = tool
        return tool

    def get(self, tool_id: str) -> Tool:
        return self._tools[tool_id]

    def list(self) -> list[Tool]:
        return list(self._tools.values())


def default_tools() -> list[Tool]:
    return [
        Tool(
            tool_id="task_manager_tool",
            name="Task Manager Tool",
            type="internal",
            description="Create, update, and inspect internal task state.",
            action="manage_task",
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"operation": "string", "task_id": "string"},
            output_schema={"result": "string"},
        ),
        Tool(
            tool_id="knowledge_base_tool",
            name="Knowledge Base Tool",
            type="internal",
            description="Read and write internal knowledge base records.",
            action="write_knowledge",
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"title": "string", "content": "string"},
            output_schema={"doc_id": "string"},
        ),
        Tool(
            tool_id="audit_read_tool",
            name="Audit Read Tool",
            type="internal",
            description="Read append-only audit log entries for review and quality checks.",
            action="read_audit_log",
            permission_level=PermissionLevel.L0_READ,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"limit": "integer"},
            output_schema={"events": "array"},
        ),
        Tool(
            tool_id="database_read_tool",
            name="Database Read Tool",
            type="internal",
            description="Read safe aggregate database state without raw SQL access.",
            action="read_database_state",
            permission_level=PermissionLevel.L0_READ,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"operation": "string"},
            output_schema={"tables": "object"},
        ),
        Tool(
            tool_id="filesystem_read_tool",
            name="Filesystem Read Tool",
            type="internal",
            description="Read or list small text files inside the workspace with path safety checks.",
            action="read_filesystem",
            permission_level=PermissionLevel.L0_READ,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"operation": "string", "path": "string", "query": "string"},
            output_schema={"result": "object"},
        ),
        Tool(
            tool_id="workspace_patch_tool",
            name="Workspace Patch Tool",
            type="workspace",
            description="Apply one exact, concurrency-checked text replacement inside the workspace.",
            action="modify_workspace",
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema={"path": "string", "old_text": "string", "new_text": "string", "expected_sha256": "string"},
            output_schema={"path": "string", "diff": "string", "after_sha256": "string"},
        ),
        Tool(
            tool_id="workspace_command_tool",
            name="Workspace Command Tool",
            type="sandbox",
            description="Run an allowlisted process in a workspace directory after explicit approval.",
            action="execute_code",
            permission_level=PermissionLevel.L4_HIGH_RISK,
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema={"argv": "array", "cwd": "string", "timeout_seconds": "integer"},
            output_schema={"exit_code": "integer", "stdout": "string", "stderr": "string"},
        ),
        Tool(
            tool_id="git_read_tool",
            name="Git Read Tool",
            type="workspace",
            description="Inspect workspace Git status, diff, or recent history without changing repository state.",
            action="read_git_state",
            permission_level=PermissionLevel.L0_READ,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            input_schema={"operation": "string", "path": "string", "limit": "integer"},
            output_schema={"output": "string"},
        ),
        Tool(
            tool_id="external_api_tool",
            name="External API Tool",
            type="external",
            description="Prepare an outbound API call for Human Root review.",
            action="call_external_api",
            permission_level=PermissionLevel.L3_EXTERNAL_PREPARE,
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema={"url": "string", "method": "string"},
            output_schema={"approval_id": "string"},
            enabled=False,
        ),
        Tool(
            tool_id="code_execution_tool",
            name="Code Execution Tool",
            type="sandbox",
            description="Run code in a controlled sandbox after explicit approval.",
            action="execute_code",
            permission_level=PermissionLevel.L4_HIGH_RISK,
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema={"language": "string", "source": "string"},
            output_schema={"stdout": "string", "stderr": "string"},
            enabled=False,
        ),
    ]
