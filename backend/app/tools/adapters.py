from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.models import KnowledgeDoc, Task, ToolRun
from app.safety.external_content import inspect_external_content
from app.services.serializers import to_plain

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
MAX_FILE_BYTES = 64 * 1024
MAX_EDIT_FILE_BYTES = 512 * 1024
MAX_COMMAND_OUTPUT_BYTES = 64 * 1024
TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SENSITIVE_PATH_PARTS = {
    ".agents",
    ".codex",
    ".env",
    ".git",
    ".venv",
    "__pycache__",
    "env",
    "node_modules",
    "venv",
}
ALLOWED_COMMANDS = {
    "node",
    "node.exe",
    "npm",
    "npm.cmd",
    "npx",
    "npx.cmd",
    "pnpm",
    "pnpm.cmd",
    "python",
    "python.exe",
    "pytest",
    "pytest.exe",
    "tsc",
    "tsc.cmd",
}
SAFE_ENVIRONMENT_KEYS = {
    "COMSPEC",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


@dataclass(frozen=True)
class ToolAdapterContext:
    company_os: Any
    tasks: dict[str, Task]
    tool_runs: dict[str, ToolRun]


class ToolAdapterError(ValueError):
    pass


def execute_tool_adapter(tool_id: str, input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any] | None:
    adapters = {
        "task_manager_tool": _task_manager_adapter,
        "knowledge_base_tool": _knowledge_base_adapter,
        "audit_read_tool": _audit_read_adapter,
        "database_read_tool": _database_read_adapter,
        "filesystem_read_tool": _filesystem_read_adapter,
        "workspace_patch_tool": _workspace_patch_adapter,
        "workspace_command_tool": _workspace_command_adapter,
        "git_read_tool": _git_read_adapter,
    }
    adapter = adapters.get(tool_id)
    if adapter is None:
        return None
    return adapter(input, context)


def _limit(input: dict[str, Any], default: int = 10, maximum: int = 50) -> int:
    raw = input.get("limit", default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ToolAdapterError("limit must be an integer") from exc
    if value < 1:
        raise ToolAdapterError("limit must be at least 1")
    return min(value, maximum)


def _task_manager_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    operation = input.get("operation", "inspect")
    tasks = list(context.tasks.values())
    if operation == "get":
        task_id = input.get("task_id")
        if not task_id:
            raise ToolAdapterError("task_id is required for get")
        task = context.tasks.get(task_id)
        if task is None:
            raise ToolAdapterError(f"task not found: {task_id}")
        return {"operation": operation, "task": to_plain(task)}
    if operation not in {"inspect", "list"}:
        raise ToolAdapterError(f"unsupported task operation: {operation}")

    status_counts: dict[str, int] = {}
    for task in tasks:
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
    return {
        "operation": operation,
        "task_count": len(tasks),
        "status_counts": status_counts,
        "recent_tasks": to_plain(tasks[-_limit(input):]),
    }


def _knowledge_base_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    operation = input.get("operation", "search" if input.get("query") else "list")
    if operation == "write":
        title = str(input.get("title", "")).strip()
        content = str(input.get("content", "")).strip()
        if not title or not content:
            raise ToolAdapterError("title and content are required for write")
        doc = context.company_os.knowledge.write(KnowledgeDoc(title=title, content=content, source_task_id=input.get("task_id")))
        return {"operation": operation, "doc": to_plain(doc)}
    if operation == "search":
        query = str(input.get("query", "")).strip()
        if not query:
            raise ToolAdapterError("query is required for search")
        docs = context.company_os.knowledge.search(query)
    elif operation == "list":
        docs = list(context.company_os.knowledge.list())
    else:
        raise ToolAdapterError(f"unsupported knowledge operation: {operation}")
    return {"operation": operation, "doc_count": len(docs), "docs": to_plain(docs[-_limit(input):])}


def _audit_read_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    events = list(context.company_os.audit.list())
    return {
        "operation": "read",
        "event_count": len(events),
        "events": to_plain(events[-_limit(input):]),
    }


def _database_read_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    return {
        "operation": input.get("operation", "summary"),
        "tables": {
            "tasks": len(context.tasks),
            "approvals": len(context.company_os.approvals.list()),
            "audit_logs": len(context.company_os.audit.list()),
            "memory_records": len(context.company_os.memory.list()),
            "knowledge_docs": len(context.company_os.knowledge.list()),
            "tools": len(context.company_os.tools.list()),
            "tool_runs": len(context.tool_runs),
            "workflow_runs": len(context.company_os.traces.list_runs()),
            "workflow_steps": len(context.company_os.traces.list_steps()),
            "model_usage": len(context.company_os.models.list_usage()),
            "cost_logs": len(context.company_os.budget.list_cost_logs()),
            "incidents": len(context.company_os.incidents.list()),
            "backups": len(context.company_os.backups.list()),
            "strategic_goals": len(context.company_os.goals.list()),
        },
    }


def _filesystem_read_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    operation = input.get("operation", "list")
    path = _resolve_workspace_path(input.get("path", "."))
    if operation == "list":
        if not path.is_dir():
            raise ToolAdapterError("path must be a directory for list")
        entries = []
        for entry in sorted(path.iterdir(), key=lambda item: item.name.lower()):
            if _is_sensitive_path(entry):
                continue
            entries.append(
                {
                    "name": entry.name,
                    "relative_path": _relative_path(entry),
                    "kind": "directory" if entry.is_dir() else "file",
                    "size_bytes": entry.stat().st_size if entry.is_file() else None,
                }
            )
            if len(entries) >= _limit(input, default=25, maximum=100):
                break
        return {"operation": operation, "path": _relative_path(path), "entries": entries}
    if operation == "read":
        _ensure_readable_text_file(path)
        content = path.read_text(encoding="utf-8")
        inspection = inspect_external_content(content, _relative_path(path), "filesystem")
        return {
            "operation": operation,
            "path": _relative_path(path),
            "size_bytes": path.stat().st_size,
            "content": content,
            "external_content_inspection": to_plain(inspection),
        }
    if operation == "search":
        if not path.is_dir():
            raise ToolAdapterError("path must be a directory for search")
        query = str(input.get("query", "")).strip()
        if not query:
            raise ToolAdapterError("query is required for search")
        matches = []
        scanned_files = 0
        flagged_files = []
        for entry in path.rglob("*"):
            if len(matches) >= _limit(input, default=25, maximum=100):
                break
            if _is_sensitive_path(entry) or not entry.is_file() or entry.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if entry.stat().st_size > MAX_FILE_BYTES:
                continue
            content = entry.read_text(encoding="utf-8", errors="ignore")
            scanned_files += 1
            inspection = inspect_external_content(content, _relative_path(entry), "filesystem")
            if inspection.instruction_risk:
                flagged_files.append({"path": _relative_path(entry), "risk_level": inspection.risk_level.value, "findings": inspection.findings})
            if query.lower() in content.lower():
                lines = content.splitlines()
                for line_number, line in enumerate(lines, start=1):
                    if query.lower() not in line.lower():
                        continue
                    matches.append(
                        {
                            "path": _relative_path(entry),
                            "line": line_number,
                            "snippet": line.strip()[:240],
                        }
                    )
                    if len(matches) >= _limit(input, default=25, maximum=100):
                        break
        return {
            "operation": operation,
            "path": _relative_path(path),
            "query": query,
            "matches": matches,
            "external_content_inspection": {
                "trusted": False,
                "scanned_files": scanned_files,
                "flagged_files": flagged_files,
            },
        }
    raise ToolAdapterError(f"unsupported filesystem operation: {operation}")


def _workspace_patch_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    path = _resolve_workspace_path(input.get("path", ""))
    _ensure_editable_text_file(path)
    old_text = input.get("old_text")
    new_text = input.get("new_text")
    if not isinstance(old_text, str) or not old_text:
        raise ToolAdapterError("old_text is required for workspace patch")
    if not isinstance(new_text, str):
        raise ToolAdapterError("new_text must be a string")

    raw_content = path.read_bytes()
    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolAdapterError("file is not valid UTF-8 text") from exc
    before_sha256 = hashlib.sha256(raw_content).hexdigest()
    expected_sha256 = str(input.get("expected_sha256", "")).strip()
    if expected_sha256 and expected_sha256 != before_sha256:
        raise ToolAdapterError("file changed since the patch was prepared")
    occurrences = content.count(old_text)
    if occurrences != 1:
        raise ToolAdapterError("old_text must match exactly once")
    updated = content.replace(old_text, new_text, 1)
    encoded = updated.encode("utf-8")
    if len(encoded) > MAX_EDIT_FILE_BYTES:
        raise ToolAdapterError("patched file is too large")

    temporary_path = None
    original_mode = path.stat().st_mode
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(updated)
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, path)
    except OSError as exc:
        raise ToolAdapterError(f"workspace patch failed: {exc.__class__.__name__}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass

    diff_lines = list(
        difflib.unified_diff(
            content.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{_relative_path(path)}",
            tofile=f"b/{_relative_path(path)}",
            lineterm="",
        )
    )
    return {
        "operation": "patch",
        "path": _relative_path(path),
        "before_sha256": before_sha256,
        "after_sha256": hashlib.sha256(encoded).hexdigest(),
        "diff": "\n".join(diff_lines)[:MAX_COMMAND_OUTPUT_BYTES],
    }


def _workspace_command_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    argv = input.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and value for value in argv):
        raise ToolAdapterError("argv must be a non-empty string array")
    if len(argv) > 32 or any(len(value) > 2000 for value in argv):
        raise ToolAdapterError("command arguments exceed the allowed size")
    executable = Path(argv[0]).name.lower()
    if executable not in ALLOWED_COMMANDS:
        raise ToolAdapterError(f"command is not allowlisted: {executable}")
    cwd = _resolve_workspace_path(input.get("cwd", "."))
    if not cwd.is_dir():
        raise ToolAdapterError("command cwd must be a workspace directory")
    try:
        timeout_seconds = min(max(int(input.get("timeout_seconds", 30)), 1), 120)
    except (TypeError, ValueError) as exc:
        raise ToolAdapterError("timeout_seconds must be an integer") from exc
    environment = {key: value for key, value in os.environ.items() if key.upper() in SAFE_ENVIRONMENT_KEYS}
    resolved_executable = shutil.which(argv[0], path=environment.get("PATH"))
    execution_argv = [resolved_executable, *argv[1:]] if resolved_executable else argv
    try:
        completed = subprocess.run(
            execution_argv,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolAdapterError(f"command failed to start: {exc.__class__.__name__}") from exc
    return {
        "operation": "command",
        "argv": argv,
        "cwd": _relative_path(cwd),
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-MAX_COMMAND_OUTPUT_BYTES:],
        "stderr": completed.stderr[-MAX_COMMAND_OUTPUT_BYTES:],
        "truncated": len(completed.stdout) > MAX_COMMAND_OUTPUT_BYTES or len(completed.stderr) > MAX_COMMAND_OUTPUT_BYTES,
    }


def _git_read_adapter(input: dict[str, Any], context: ToolAdapterContext) -> dict[str, Any]:
    operation = str(input.get("operation", "status")).strip().lower()
    base = ["git", "-c", f"safe.directory={WORKSPACE_ROOT.as_posix()}"]
    if operation == "status":
        argv = [*base, "status", "--short", "--branch"]
    elif operation == "diff":
        argv = [*base, "diff", "--no-ext-diff"]
        path_value = str(input.get("path", "")).strip()
        if path_value:
            path = _resolve_workspace_path(path_value)
            argv.extend(["--", _relative_path(path)])
    elif operation == "log":
        limit = _limit(input, default=10, maximum=50)
        argv = [*base, "log", f"-{limit}", "--oneline", "--decorate"]
    else:
        raise ToolAdapterError(f"unsupported git read operation: {operation}")
    try:
        completed = subprocess.run(
            argv,
            cwd=WORKSPACE_ROOT,
            env={key: value for key, value in os.environ.items() if key.upper() in SAFE_ENVIRONMENT_KEYS},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolAdapterError(f"git command failed to start: {exc.__class__.__name__}") from exc
    if completed.returncode != 0:
        raise ToolAdapterError(completed.stderr.strip() or "git command failed")
    return {
        "operation": operation,
        "exit_code": completed.returncode,
        "output": completed.stdout[-MAX_COMMAND_OUTPUT_BYTES:],
        "truncated": len(completed.stdout) > MAX_COMMAND_OUTPUT_BYTES,
    }


def _resolve_workspace_path(raw_path: Any) -> Path:
    requested = Path(str(raw_path or "."))
    if requested.is_absolute():
        raise ToolAdapterError("absolute paths are not allowed")
    resolved = (WORKSPACE_ROOT / requested).resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ToolAdapterError("path must stay inside the workspace") from exc
    if _is_sensitive_path(resolved):
        raise ToolAdapterError("path is sensitive or hidden")
    return resolved


def _relative_path(path: Path) -> str:
    return path.relative_to(WORKSPACE_ROOT).as_posix() or "."


def _is_sensitive_path(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(WORKSPACE_ROOT)
    except ValueError:
        return True
    return any(part in SENSITIVE_PATH_PARTS or part.startswith(".") for part in relative.parts)


def _ensure_readable_text_file(path: Path) -> None:
    if not path.is_file():
        raise ToolAdapterError("path must be a file for read")
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ToolAdapterError("file extension is not allowed for text read")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ToolAdapterError("file is too large for tool read")


def _ensure_editable_text_file(path: Path) -> None:
    if not path.is_file():
        raise ToolAdapterError("path must be an existing file for patch")
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ToolAdapterError("file extension is not allowed for patch")
    if path.stat().st_size > MAX_EDIT_FILE_BYTES:
        raise ToolAdapterError("file is too large for patch")
